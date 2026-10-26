"""Connect normalization, retrieval and integrity lookup without assigning verdicts."""

from starlette.concurrency import run_in_threadpool

from app.models.claims import CandidateIntegrity, CandidateStudy, ClaimCandidates
from app.models.pubmed import PubMedArticle
from app.models.metadata import CandidateWeight
from app.evidence_models import Claim, Study
from app.evidence_workflow import score_study
from app.services.crossref import CrossrefClient, InvalidDoiError, normalize_doi
from app.services.integrity import apply_integrity_gate, assess_integrity
from app.services.metadata import extract_metadata
from app.services.normalization import normalize_claim
from app.services.pubmed import PubMedClient


def article_doi(article: PubMedArticle) -> str | None:
    if article.doi:
        try:
            return normalize_doi(article.doi)
        except InvalidDoiError:
            pass
    return None


async def retrieve_candidates(
    claim: str, limit: int, pubmed: PubMedClient, crossref: CrossrefClient,
) -> ClaimCandidates:
    normalized = await run_in_threadpool(normalize_claim, claim)
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
    reports = await crossref.check_many(
        doi for article in articles if (doi := article_doi(article)) is not None
    )
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
    return ClaimCandidates(
        claim=claim, normalized=normalized, query_translation=results.query_translation,
        total_results=results.total_results, candidates=candidates,
    )
