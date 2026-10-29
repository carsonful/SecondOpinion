"""Retrieve eligible PMC text through NCBI's documented BioC service only.

No publisher scraping, subscription sessions, arbitrary URLs, or PDF downloads.
Retrieval failures preserve the PubMed record and do not become quality scores.
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2 as httpx

from app.models.full_text import FullTextAccess, PMCDocument, RetrievalResult, TextSection
from app.models.pubmed import PubMedArticle
from app.services.cache import TTLCache
from app.services.rate_limiter import RateLimiter

BIOC_BASE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json"
MAX_BYTES = 3_000_000
MAX_TEXT = 600_000
PMC_ID = re.compile(r"^PMC[1-9]\d{0,9}$")
_EXCLUDED = {"TITLE", "ABSTRACT", "REF", "REFERENCES", "ACK_FUND", "AUTH_CONT", "COMP_INT", "SUPPL"}
# BioC rate-limits bursts with 429s, so back off a few times before giving up.
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_DELAYS = (1.0, 2.0, 4.0)
MAX_RETRY_AFTER = 8.0
# For articles outside the open-access set BioC answers 200 with this text, not a 404.
NO_RESULT_PREFIX = b"[Error] : No result can be found"


def unavailable(article: PubMedArticle, reason: str, detail: str) -> RetrievalResult:
    pmc_id = article.pmc_id if article.pmc_id and PMC_ID.fullmatch(article.pmc_id) else None
    return RetrievalResult(access=FullTextAccess(
        level="abstract_only" if article.abstract else "metadata_only",
        reason=reason, detail=detail, pmc_id=pmc_id,
        source_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/" if pmc_id else None,
    ))


def _retry_delay(response: httpx.Response, default: float) -> float:
    try:
        return min(max(float(response.headers["Retry-After"]), 0.0), MAX_RETRY_AFTER)
    except (KeyError, ValueError):
        return default


def _pmc_number(value: Any) -> str:
    """BioC writes PMC IDs both as "PMC6768751" and "6768751"."""
    return str(value or "").strip().upper().removeprefix("PMC")


def parse_bioc(data: Any, pmc_id: str, expected_pmid: str) -> PMCDocument:
    collections = data if isinstance(data, list) else [data]
    documents = [
        document
        for collection in collections if isinstance(collection, dict)
        for document in collection.get("documents", []) if isinstance(document, dict)
    ]
    for document in documents:
        # Some documents come back with id "unknown"; one on its own can still be
        # identified by the PMID check below, but never alongside other documents.
        id_matches = _pmc_number(document.get("id")) == _pmc_number(pmc_id)
        if not id_matches and not (len(documents) == 1 and document.get("id") in (None, "", "unknown")):
            continue
        sections = []
        license_text, pmid = None, None
        pmc_confirmed = id_matches
        total = 0
        for passage in document.get("passages", []):
            info = passage.get("infons", {})
            license_text = license_text or info.get("license")
            pmid = pmid or info.get("article-id_pmid")
            passage_pmc = info.get("article-id_pmc")
            if passage_pmc:
                if _pmc_number(passage_pmc) != _pmc_number(pmc_id):
                    raise ValueError("PMC identifier mismatch")
                pmc_confirmed = True
            label = str(info.get("section_type", "")).upper()
            kind = str(info.get("type", "")).lower()
            if label in _EXCLUDED or kind in ("front", "ref", "footnote") or "abstract" in kind:
                continue
            # BioC section headings alone do not constitute full article text.
            if "title" in kind:
                continue
            raw_text = passage.get("text")
            if not isinstance(raw_text, str):
                continue
            text = " ".join(raw_text.split())
            if not text:
                continue
            total += len(text)
            if total > MAX_TEXT:
                raise OverflowError("Article text exceeds supported size")
            sections.append(TextSection(id=f"s{len(sections) + 1}", label=label or "BODY", text=text))
        if pmid and str(pmid) != expected_pmid:
            raise ValueError("PubMed identifier mismatch")
        # PubMed gave us this PMC ID for this PMID, so a matching PMC ID is enough
        # when BioC leaves the PMID out. With neither ID confirmed, reject it.
        if not pmid and not pmc_confirmed:
            raise ValueError("Document identity could not be confirmed")
        if not sections:
            raise ValueError("No full-text body passages")
        return PMCDocument(
            pmc_id=pmc_id, pmid=expected_pmid,
            source_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/",
            license=license_text, sections=sections,
        )
    raise ValueError("No matching PMC document")


class PMCClient:
    def __init__(
        self, http: httpx.AsyncClient, limiter: RateLimiter,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._http = http
        self._limiter = limiter
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(3)
        self._documents: TTLCache[str, PMCDocument] = TTLCache(24 * 60 * 60, 64)

    async def retrieve(self, article: PubMedArticle, *, refresh: bool = False) -> RetrievalResult:
        pmc_id = article.pmc_id
        if not pmc_id or not PMC_ID.fullmatch(pmc_id):
            return unavailable(article, "no_pmc_id", "No valid PMC identifier was supplied by PubMed; full text was not retrieved.")
        cached = None if refresh else self._documents.get(pmc_id)
        if cached is not None and cached.pmid == article.pmid:
            return self._available(cached)
        try:
            async with asyncio.timeout(25), self._semaphore:
                for attempt in range(len(RETRY_DELAYS) + 1):
                    await self._limiter.acquire()
                    async with self._http.stream("GET", f"{BIOC_BASE}/{pmc_id}/unicode", follow_redirects=False) as response:
                        if response.status_code in (404, 410):
                            return self._not_available(article)
                        if response.status_code in RETRY_STATUSES and attempt < len(RETRY_DELAYS):
                            delay = _retry_delay(response, RETRY_DELAYS[attempt])
                            await response.aclose()
                            await self._sleep(delay)
                            continue
                        if response.status_code != 200:
                            return unavailable(article, "request_failed", "PMC retrieval failed; full-text availability is unknown. Try again later.")
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_BYTES:
                                return unavailable(article, "too_large", "The PMC response exceeds the supported size.")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        if body.lstrip().startswith(NO_RESULT_PREFIX):
                            return self._not_available(article)
                        data = json.loads(body)
                        document = parse_bioc(data, pmc_id, article.pmid)
                        self._documents.set(pmc_id, document)
                        return self._available(document)
        except (httpx.HTTPError, TimeoutError):
            return unavailable(article, "request_failed", "PMC retrieval timed out or failed; full-text availability is unknown. Try again later.")
        except OverflowError:
            return unavailable(article, "too_large", "The article exceeds the supported text size.")
        except (ValueError, KeyError, TypeError, AttributeError):
            return unavailable(article, "parse_failed", "The PMC response could not be verified as readable full text for this study.")
        return unavailable(article, "request_failed", "PMC retrieval did not complete.")

    @staticmethod
    def _not_available(article: PubMedArticle) -> RetrievalResult:
        return unavailable(article, "not_available", "Full text is not available through the supported PMC service; this does not establish that it is paywalled.")

    @staticmethod
    def _available(document: PMCDocument) -> RetrievalResult:
        return RetrievalResult(
            access=FullTextAccess(
                level="full_text", reason="retrieved", detail="Full-text body passages retrieved from the supported PMC collection.",
                pmc_id=document.pmc_id, source_url=document.source_url, license=document.license,
                sections=list(dict.fromkeys(section.label for section in document.sections)),
            ), document=document,
        )
