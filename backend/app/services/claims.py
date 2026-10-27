"""Connect claim normalization, PubMed search and PMC access checks."""

from dataclasses import dataclass
import asyncio

from starlette.concurrency import run_in_threadpool

from app.models.claims import CandidateStudy, ClaimCandidates
from app.models.full_text import EvidenceCoverage
from app.models.normalization import NormalizedClaim
from app.config import Settings
from app.services.cache import TTLCache
from app.services.metadata import extract_metadata
from app.services.normalization import normalize_claim
from app.services.pubmed import PubMedClient
from app.services.pmc import PMCClient, unavailable


@dataclass
class ClaimsCache:
    """Two layers, so a repeated claim makes no external calls (#15).

    - normalized: raw claim text -> normalized claim, which skips the Azure call
    - results: (search query, limit) -> candidates, which skips PubMed and PMC.
      Keyed on the normalized query, so different wordings of one claim share it.
    """

    normalized: TTLCache[str, NormalizedClaim]
    results: TTLCache[tuple[str, int], ClaimCandidates]

    @classmethod
    def from_settings(cls, settings: Settings) -> "ClaimsCache":
        ttl, size = settings.claims_cache_ttl_seconds, settings.claims_cache_max_entries
        return cls(TTLCache(ttl, size), TTLCache(ttl, size))

    def clear(self) -> None:
        self.normalized.clear()
        self.results.clear()


def _raw_claim_key(claim: str) -> str:
    return " ".join(claim.lower().split())


async def retrieve_candidates(
    claim: str, limit: int, pubmed: PubMedClient,
    cache: ClaimsCache | None = None, refresh: bool = False,
    pmc: PMCClient | None = None,
) -> ClaimCandidates:
    """With `refresh`, skip cached values but still store the fresh result."""
    raw_key = _raw_claim_key(claim)
    normalized = None if cache is None or refresh else cache.normalized.get(raw_key)
    if normalized is None:
        normalized = await run_in_threadpool(normalize_claim, claim)
        if cache is not None:
            cache.normalized.set(raw_key, normalized)

    results_key = (normalized.query, limit)
    cached = None if cache is None or refresh else cache.results.get(results_key)
    if cached is not None:
        return cached.model_copy(update={"claim": claim, "normalized": normalized, "cached": True})

    retrieved = await _retrieve(claim, normalized, limit, pubmed, pmc, refresh)
    if cache is not None and retrieved.complete:
        cache.results.set(results_key, retrieved.candidates)
    return retrieved.candidates


@dataclass
class _Retrieved:
    candidates: ClaimCandidates
    # Failed PMC attempts aren't cached, so refresh or a later search can retry.
    complete: bool


async def _retrieve(
    claim: str, normalized: NormalizedClaim, limit: int,
    pubmed: PubMedClient,
    pmc: PMCClient | None, refresh: bool,
) -> _Retrieved:
    results = await pubmed.search(normalized.query, limit)
    # Deduplicate PubMed aliases by PMID and DOI, keeping the first ranked record.
    seen_pmids: set[str] = set()
    seen_dois: set[str] = set()
    articles = []
    for article in results.articles:
        doi = article.doi.casefold() if article.doi else None
        duplicate = article.pmid in seen_pmids or (doi is not None and doi in seen_dois)
        seen_pmids.add(article.pmid)
        if doi:
            seen_dois.add(doi)
        if not duplicate:
            articles.append(article)

    # Retrieval errors affect coverage, not whether the PubMed record is shown.
    texts = await asyncio.gather(*(pmc.retrieve(article, refresh=refresh) for article in articles)) if pmc else [
        unavailable(article, "request_failed", "Full-text retrieval is not initialized; access could not be checked.")
        for article in articles
    ]
    candidates = []
    for article, text in zip(articles, texts):
        metadata = extract_metadata(article)
        candidates.append(CandidateStudy(
            article=article,
            metadata=metadata,
            access=text.access,
        ))
    return _Retrieved(
        ClaimCandidates(
            claim=claim, normalized=normalized, query_translation=results.query_translation,
            total_results=results.total_results, candidates=candidates,
            coverage=EvidenceCoverage(
                retrieved_studies=len(candidates),
                full_text_available=sum(c.access.level == "full_text" for c in candidates),
                abstract_only=sum(c.access.level == "abstract_only" for c in candidates),
                metadata_only=sum(c.access.level == "metadata_only" for c in candidates),
            ),
        ),
        complete=pmc is None or not any(text.access.reason in ("request_failed", "parse_failed") for text in texts),
    )
