"""Connect normalization, retrieval and integrity lookup without assigning verdicts."""

from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from app.models.claims import CandidateIntegrity, CandidateStudy, ClaimCandidates
from app.models.pubmed import PubMedArticle
from app.models.metadata import CandidateWeight
from app.models.normalization import NormalizedClaim
from app.evidence_models import Claim, Study
from app.evidence_workflow import score_study
from app.config import Settings
from app.services.cache import TTLCache
from app.services.crossref import CrossrefClient, InvalidDoiError, normalize_doi
from app.services.integrity import apply_integrity_gate, assess_integrity
from app.services.metadata import extract_metadata
from app.services.normalization import normalize_claim
from app.services.pubmed import PubMedClient


@dataclass
class ClaimsCache:
    """Two layers, so a repeated claim makes no external calls (#15).

    - normalized: raw claim text -> normalized claim, which skips the Azure call
    - results: (search query, limit) -> candidates, which skips PubMed and Crossref.
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


def article_doi(article: PubMedArticle) -> str | None:
    if article.doi:
        try:
            return normalize_doi(article.doi)
        except InvalidDoiError:
            pass
    return None


async def retrieve_candidates(
    claim: str, limit: int, pubmed: PubMedClient, crossref: CrossrefClient,
    cache: ClaimsCache | None = None, refresh: bool = False,
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

    retrieved = await _retrieve(claim, normalized, limit, pubmed, crossref)
    if cache is not None and retrieved.complete:
        cache.results.set(results_key, retrieved.candidates)
    return retrieved.candidates


@dataclass
class _Retrieved:
    candidates: ClaimCandidates
    # False when a Crossref lookup failed. Those results are not cached, so a
    # temporary outage doesn't leave studies "unchecked" until the cache expires.
    complete: bool


async def _retrieve(
    claim: str, normalized: NormalizedClaim, limit: int,
    pubmed: PubMedClient, crossref: CrossrefClient,
) -> _Retrieved:
    results = await pubmed.search(normalized.query, limit)
    # Keep every marker seen, including markers on duplicates, to catch aliases.
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

    # One failed Crossref lookup must not fail the search; those studies stay "unchecked".
    requested_dois = {doi for article in articles if (doi := article_doi(article)) is not None}
    reports = await crossref.check_many(requested_dois)
    # A duplicate record must not erase a PubMed retraction marker.
    retracted_pmids = {a.pmid for a in results.articles if a.retracted}
    retracted_dois = {article_doi(a) for a in results.articles if a.retracted and article_doi(a)}
    candidates = []
    scoring_claim = Claim(raw_text=claim)
    for article in articles:
        doi = article_doi(article)
        retracted = article.pmid in retracted_pmids or doi in retracted_dois
        article = article.model_copy(update={"retracted": retracted})
        integrity = assess_integrity(reports.get(doi), retracted)
        metadata = extract_metadata(article)
        score = score_study(scoring_claim, Study(
            title=article.title, pmid=article.pmid, doi=article.doi,
            study_type=metadata.design, sample_size=metadata.sample_size,
            year=article.year, journal=article.journal,
        ))
        gated = apply_integrity_gate([(score, integrity)])
        gated_score = gated.evidence_table[0].score
        eligibility = (gated_score.eligibility_reason if not integrity.contributes else
                       "Pending relevance, findings, and eligibility assessment; final contribution is unknown.")
        candidates.append(CandidateStudy(
            article=article,
            integrity=CandidateIntegrity(status=integrity.status, notices=list(integrity.notices)),
            metadata=metadata,
            weight=CandidateWeight(
                base_weight=score.component_scores["base_weight"],
                final_weight=gated_score.final_weight,
                version=score.weight_version, reason=score.weight_reason,
                eligibility_reason=eligibility,
            ),
        ))
    return _Retrieved(
        ClaimCandidates(
            claim=claim, normalized=normalized, query_translation=results.query_translation,
            total_results=results.total_results, candidates=candidates,
        ),
        complete=requested_dois <= reports.keys(),
    )
