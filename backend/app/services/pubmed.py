"""Client for the NCBI E-utilities API, used to search PubMed and fetch study records.

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2 as httpx

from app.config import Settings
from app.models.pubmed import PubMedArticle, PubMedSearchResponse
from app.services.rate_limiter import RateLimiter
from app.services.upstream import (
    UpstreamError,
    UpstreamResponseError,
    UpstreamUnavailableError,
    get_with_retries,
)

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# NCBI allows 3 requests/second without a key and 10 with one. We stay a little
# under each ceiling because network jitter can bunch requests up on arrival.
RATE_WITHOUT_KEY = 2.5
RATE_WITH_KEY = 9.0

# EFetch accepts long ID lists, but URLs get unwieldy past a couple hundred.
MAX_FETCH_BATCH = 200

_YEAR_PATTERN = re.compile(r"\b(\d{4})\b")


class PubMedError(UpstreamError):
    """Base class for PubMed client failures."""

    service = "PubMed"


class PubMedUnavailableError(PubMedError, UpstreamUnavailableError):
    """PubMed could not be reached, or kept failing after retries."""


class PubMedResponseError(PubMedError, UpstreamResponseError):
    """PubMed answered, but with something we could not use."""


class PubMedClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str | None = None,
        email: str | None = None,
        tool: str = "SecondOpinion",
        rate_limiter: RateLimiter | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http = http_client
        self._api_key = api_key
        self._email = email
        self._tool = tool
        self._limiter = rate_limiter or RateLimiter(RATE_WITH_KEY if api_key else RATE_WITHOUT_KEY)
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings, http_client: httpx.AsyncClient) -> "PubMedClient":
        return cls(
            http_client,
            api_key=settings.ncbi_api_key,
            email=settings.ncbi_email,
            tool=settings.ncbi_tool,
        )

    @property
    def rate_limiter(self) -> RateLimiter:
        """Share the NCBI request budget with PMC retrieval in this process."""
        return self._limiter

    async def search(self, query: str, limit: int = 20) -> PubMedSearchResponse:
        """Search PubMed and return full records for the top matches, in relevance order."""
        pmids, total, translation = await self.search_ids(query, limit)
        articles = await self.fetch_articles(pmids)
        return PubMedSearchResponse(
            query=query,
            query_translation=translation,
            total_results=total,
            articles=articles,
        )

    async def search_ids(self, query: str, limit: int = 20) -> tuple[list[str], int, str | None]:
        """Run an ESearch. Returns (PMIDs in relevance order, total match count, query translation)."""
        response = await self._get(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json", "sort": "relevance"},
        )
        try:
            result = response.json()["esearchresult"]
        except (ValueError, KeyError) as exc:
            raise PubMedResponseError("ESearch returned an unexpected response") from exc

        if "ERROR" in result:
            raise PubMedResponseError(f"ESearch rejected the query: {result['ERROR']}")

        return result.get("idlist", []), int(result.get("count", 0)), result.get("querytranslation")

    async def fetch_articles(self, pmids: list[str]) -> list[PubMedArticle]:
        """Run EFetch for the given PMIDs. Results keep the order of `pmids`; unknown IDs are skipped."""
        if not pmids:
            return []

        by_pmid: dict[str, PubMedArticle] = {}
        for start in range(0, len(pmids), MAX_FETCH_BATCH):
            batch = pmids[start : start + MAX_FETCH_BATCH]
            response = await self._get(
                "efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
            )
            for article in parse_efetch_xml(response.content):
                by_pmid[article.pmid] = article

        return [by_pmid[pmid] for pmid in pmids if pmid in by_pmid]

    async def get_article(self, pmid: str) -> PubMedArticle | None:
        articles = await self.fetch_articles([pmid])
        return articles[0] if articles else None

    async def _get(self, endpoint: str, params: dict[str, Any]) -> httpx.Response:
        params = {**params, "tool": self._tool}
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key

        response = await get_with_retries(
            self._http,
            f"{EUTILS_BASE_URL}/{endpoint}",
            params=params,
            limiter=self._limiter,
            sleep=self._sleep,
            unavailable_error=PubMedUnavailableError,
        )
        if response.is_error:
            raise PubMedResponseError(f"PubMed {endpoint} returned HTTP {response.status_code}")
        return response


def parse_efetch_xml(content: bytes) -> list[PubMedArticle]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise PubMedResponseError("EFetch returned malformed XML") from exc

    # Book chapters come back as PubmedBookArticle; we only grade journal articles.
    return [_parse_article(node) for node in root.iterfind("PubmedArticle")]


def _parse_article(node: ET.Element) -> PubMedArticle:
    citation = node.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    if citation is None or article is None:
        raise PubMedResponseError("EFetch article is missing its citation")

    pmid = _text(citation.find("PMID"))
    if not pmid:
        raise PubMedResponseError("EFetch article is missing a PMID")

    article_ids = {
        id_node.get("IdType"): _text(id_node)
        for id_node in node.iterfind("PubmedData/ArticleIdList/ArticleId")
    }
    doi = article_ids.get("doi") or next(
        (_text(loc) for loc in article.iterfind("ELocationID") if loc.get("EIdType") == "doi"),
        None,
    )

    publication_types = [_text(t) for t in article.iterfind("PublicationTypeList/PublicationType")]
    retraction_notices = [
        c for c in citation.iterfind("CommentsCorrectionsList/CommentsCorrections")
        if c.get("RefType") == "RetractionIn"
    ]

    return PubMedArticle(
        pmid=pmid,
        title=_text(article.find("ArticleTitle")),
        abstract=_parse_abstract(article),
        journal=_text(article.find("Journal/Title")) or None,
        year=_parse_year(article),
        authors=_parse_authors(article),
        doi=doi or None,
        pmc_id=article_ids.get("pmc") or None,
        publication_types=publication_types,
        mesh_terms=[_text(m) for m in citation.iterfind("MeshHeadingList/MeshHeading/DescriptorName")],
        retracted="Retracted Publication" in publication_types or bool(retraction_notices),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    )


def _parse_abstract(article: ET.Element) -> str | None:
    sections = []
    for part in article.iterfind("Abstract/AbstractText"):
        text = _text(part)
        if not text:
            continue
        label = part.get("Label")
        sections.append(f"{label}: {text}" if label else text)
    return "\n\n".join(sections) or None


def _parse_year(article: ET.Element) -> int | None:
    pub_date = article.find("Journal/JournalIssue/PubDate")
    candidates = [
        _text(pub_date.find("Year")) if pub_date is not None else "",
        # Older or seasonal issues use free text such as "1998 Dec-1999 Jan".
        _text(pub_date.find("MedlineDate")) if pub_date is not None else "",
        _text(article.find("ArticleDate/Year")),
    ]
    for candidate in candidates:
        match = _YEAR_PATTERN.search(candidate)
        if match:
            return int(match.group(1))
    return None


def _parse_authors(article: ET.Element) -> list[str]:
    authors = []
    for author in article.iterfind("AuthorList/Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        name = " ".join(filter(None, [_text(author.find("LastName")), _text(author.find("Initials"))]))
        if name:
            authors.append(name)
    return authors


def _text(node: ET.Element | None) -> str:
    """Element text including inline markup like <i> and <sup>, with whitespace collapsed."""
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())
