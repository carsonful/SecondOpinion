"""Connect claim normalization, PubMed search and PMC access checks."""

import asyncio
from dataclasses import dataclass
import logging

import psycopg
from psycopg.conninfo import conninfo_to_dict

from starlette.concurrency import run_in_threadpool

from app.models.claims import CandidateIntegrity, CandidateStudy, ClaimCandidates
from app.models.full_text import EvidenceCoverage
from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedArticle
from app.config import Settings
from app.services.cache import TTLCache, canonical_claim_key
from app.services.crossref import CrossrefClient, InvalidDoiError, normalize_doi
from app.services.durable_cache import PostgresClaimsCache
from app.services.integrity import assess_integrity
from app.services.metadata import extract_metadata
from app.services.normalization import normalize_claim
from app.services.pubmed import PubMedClient
from app.services.pmc import PMCClient, unavailable

logger = logging.getLogger(__name__)


@dataclass
class ClaimsCache:
    """Two layers, so a repeated claim makes no external calls (#15).

    - normalized: raw claim text -> normalized claim, which skips the Azure call
    - results: (search query, limit) -> candidates, which skips PubMed and PMC.
      Keyed on the normalized query, so different wordings of one claim share it.
    """

    normalized: TTLCache[str, NormalizedClaim]
    results: TTLCache[tuple[str, int], ClaimCandidates]
    persistent: PostgresClaimsCache | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "ClaimsCache":
        ttl, size = settings.claims_cache_ttl_seconds, settings.claims_cache_max_entries
        database_url = settings.cache_database_url
        if database_url and settings.database_url:
            cache_db = conninfo_to_dict(database_url.get_secret_value()).get("dbname")
            examples_db = conninfo_to_dict(settings.database_url.get_secret_value()).get("dbname")
            if cache_db == examples_db:
                raise ValueError("CACHE_DATABASE_URL must use a separate database name")
        persistent = (
            PostgresClaimsCache(database_url, ttl)
            if database_url and ttl > 0 and size > 0 else None
        )
        # A short local lifetime lets manual edits in PostgreSQL become visible
        # without waiting for the full shared-cache TTL.
        local_ttl = min(ttl, 60) if persistent else ttl
        return cls(TTLCache(local_ttl, size), TTLCache(local_ttl, size), persistent)

    def clear(self) -> None:
        self.normalized.clear()
        self.results.clear()

    def _disable_persistent(self) -> None:
        logger.warning("persistent claim cache unavailable; using in-memory cache")
        self.persistent = None

    async def get_normalized(self, key: str) -> NormalizedClaim | None:
        value = self.normalized.get(key)
        if value is None and self.persistent:
            try:
                value = await self.persistent.get_normalized(key)
            except psycopg.Error:
                self._disable_persistent()
            if value is not None:
                self.normalized.set(key, value)
        return value

    async def put_normalized(self, key: str, value: NormalizedClaim) -> None:
        self.normalized.set(key, value)
        if self.persistent:
            try:
                await self.persistent.put_normalized(key, value)
            except psycopg.Error:
                self._disable_persistent()

    async def get_candidates(self, key: tuple[str, int]) -> ClaimCandidates | None:
        value = self.results.get(key)
        if value is None and self.persistent:
            try:
                value = await self.persistent.get_candidates(*key)
            except psycopg.Error:
                self._disable_persistent()
            if value is not None:
                self.results.set(key, value)
        return value

    async def put_candidates(self, key: tuple[str, int], value: ClaimCandidates) -> None:
        self.results.set(key, value)
        if self.persistent:
            try:
                await self.persistent.put_candidates(*key, value)
            except psycopg.Error:
                self._disable_persistent()


def article_doi(article: PubMedArticle) -> str | None:
    if article.doi:
        try:
            return normalize_doi(article.doi)
        except InvalidDoiError:
            pass
    return None


async def retrieve_candidates(
    claim: str, limit: int, pubmed: PubMedClient,
    cache: ClaimsCache | None = None, refresh: bool = False,
    pmc: PMCClient | None = None, crossref: CrossrefClient | None = None,
) -> ClaimCandidates:
    """With `refresh`, skip cached values but still store the fresh result."""
    raw_key = canonical_claim_key(claim)
    normalized = None if cache is None or refresh else await cache.get_normalized(raw_key)
    if normalized is None:
        normalized = await run_in_threadpool(normalize_claim, claim)
        if cache is not None:
            await cache.put_normalized(raw_key, normalized)

    results_key = (normalized.query, limit)
    cached = None if cache is None or refresh else await cache.get_candidates(results_key)
    if cached is not None:
        return cached.model_copy(update={"claim": claim, "normalized": normalized, "cached": True})

    retrieved = await _retrieve(claim, normalized, limit, pubmed, pmc, crossref, refresh)
    if cache is not None and retrieved.complete:
        await cache.put_candidates(results_key, retrieved.candidates)
    return retrieved.candidates


@dataclass
class _Retrieved:
    candidates: ClaimCandidates
    # Temporary PMC or Crossref failures aren't cached, so refresh or a later search
    # can retry instead of leaving studies "unchecked" until the cache expires.
    # parse_failed is cached: PMC returns the same document each time, so retrying
    # would fail the same way and the claim would never be cached at all.
    complete: bool


async def _retrieve(
    claim: str, normalized: NormalizedClaim, limit: int,
    pubmed: PubMedClient,
    pmc: PMCClient | None, crossref: CrossrefClient | None, refresh: bool,
) -> _Retrieved:
    results = await pubmed.search(normalized.query, limit)
    # Deduplicate PubMed aliases by PMID and DOI, keeping the first ranked record.
    seen_pmids: set[str] = set()
    seen_dois: set[str] = set()
    articles = []
    for article in results.articles:
        doi = article_doi(article)
        duplicate = article.pmid in seen_pmids or (doi is not None and doi in seen_dois)
        seen_pmids.add(article.pmid)
        if doi:
            seen_dois.add(doi)
        if not duplicate:
            articles.append(article)

    # Retrieval errors affect coverage, not whether the PubMed record is shown.
    async def retrieve_texts():
        if pmc is not None:
            return await asyncio.gather(*(
                pmc.retrieve(article, refresh=refresh) for article in articles
            ))
        return [
            unavailable(
                article, "request_failed",
                "Full-text retrieval is not initialized; access could not be checked.",
            )
            for article in articles
        ]

    # A failed Crossref lookup leaves that study "unchecked" instead of failing the search.
    requested_dois = {doi for article in articles if (doi := article_doi(article)) is not None}

    async def check_integrity():
        if crossref is None:
            return {}
        return await crossref.check_many(requested_dois)

    # PMC access and Crossref notices are independent, so check both at once.
    texts, reports = await asyncio.gather(retrieve_texts(), check_integrity())

    # A duplicate record must not erase a PubMed retraction marker.
    retracted_pmids = {a.pmid for a in results.articles if a.retracted}
    retracted_dois = {doi for a in results.articles if a.retracted and (doi := article_doi(a))}
    candidates, excluded = [], []
    for article, text in zip(articles, texts):
        doi = article_doi(article)
        retracted = article.pmid in retracted_pmids or (doi is not None and doi in retracted_dois)
        article = article.model_copy(update={"retracted": retracted})
        integrity = assess_integrity(reports.get(doi), retracted)
        study = CandidateStudy(
            article=article,
            metadata=extract_metadata(article),
            access=text.access,
            integrity=CandidateIntegrity(
                status=integrity.status, label=integrity.label, notices=list(integrity.notices),
            ),
        )
        # Retracted studies are kept out of the results but still reported, so the
        # response says what was removed and why.
        (excluded if integrity.status == "retracted" else candidates).append(study)
    return _Retrieved(
        ClaimCandidates(
            claim=claim, normalized=normalized, query_translation=results.query_translation,
            total_results=results.total_results, candidates=candidates,
            excluded_retracted=excluded,
            coverage=EvidenceCoverage(
                retrieved_studies=len(candidates),
                full_text_available=sum(c.access.level == "full_text" for c in candidates),
                abstract_only=sum(c.access.level == "abstract_only" for c in candidates),
                metadata_only=sum(c.access.level == "metadata_only" for c in candidates),
            ),
        ),
        complete=(
            (pmc is None or not any(text.access.reason == "request_failed" for text in texts))
            and (crossref is None or requested_dois <= reports.keys())
        ),
    )
