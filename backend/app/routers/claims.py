from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models.assessment import StudyAssessment
from app.models.pubmed import PubMedArticle
from app.services.findings import AssessmentOutputError, assess_abstract
from app.models.claims import ClaimRequest, ClaimResponse
from app.routers.pubmed import PubMedDep
from app.services.assessment import assess_metadata
from app.services.full_text import FullTextUnavailable
from app.services.study_retrieval import retrieve_study_document
from app.services.study_documents import StudyDocument, extract_pdf, MAX_DOCUMENT_BYTES
from app.services.normalization import (
    ClaimNormalizationError, FoundryUnavailableError, normalize_claim,
)

router = APIRouter(prefix="/claims", tags=["claims"])

# Keep the prototype review set small to limit on-demand assessment spending.
CLAIM_STUDY_LIMIT = 5


@router.post("", response_model=ClaimResponse)
async def check_claim(request: ClaimRequest, client: PubMedDep) -> ClaimResponse:
    claim = request.claim.strip()
    try:
        # Foundry uses a synchronous client; keep it off the API event loop.
        normalized = await run_in_threadpool(normalize_claim, claim)
    except ClaimNormalizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FoundryUnavailableError:
        raise HTTPException(status_code=503, detail="Claim processing is unavailable. Try again shortly.") from None
    evidence = await client.search(normalized.query, CLAIM_STUDY_LIMIT)
    search_scope = "claim"
    if evidence.total_results == 0:
        # Normalization has already validated this term. Broaden retrieval only;
        # assessments still receive the user's complete original claim.
        broader_query = f"({normalized.intervention})"
        if broader_query != normalized.query:
            evidence = await client.search(broader_query, CLAIM_STUDY_LIMIT)
            search_scope = "intervention_only"
    return ClaimResponse(
        claim=claim, normalized=normalized, evidence=evidence, search_scope=search_scope,
        assessments=[assess_metadata(article) for article in evidence.articles],
    )


@router.post("/articles/{pmid}/assess", response_model=StudyAssessment)
async def assess_article(
    request: ClaimRequest, client: PubMedDep,
    pmid: Annotated[str, Path(pattern=r"^\d{1,9}$")],
) -> StudyAssessment:
    claim = request.claim.strip()
    if not claim:
        raise HTTPException(status_code=422, detail="Enter one clear health claim")
    article = await client.get_article(pmid)
    if article is None:
        raise HTTPException(status_code=404, detail="PubMed article not found")
    try:
        return await run_in_threadpool(assess_abstract, claim, article)
    except AssessmentOutputError:
        raise HTTPException(status_code=502, detail="The generated assessment could not be verified against the abstract. Please retry.") from None
    except FoundryUnavailableError:
        raise HTTPException(status_code=503, detail="Abstract assessment is unavailable. Please try again.") from None


@router.post("/articles/{pmid}/assess-full-text", response_model=StudyAssessment)
async def assess_full_article(
    request: ClaimRequest, client: PubMedDep,
    pmid: Annotated[str, Path(pattern=r"^\d{1,9}$")],
) -> StudyAssessment:
    claim = request.claim.strip()
    if not claim:
        raise HTTPException(status_code=422, detail="Enter one clear health claim")
    article = await client.get_article(pmid)
    if article is None:
        raise HTTPException(status_code=404, detail="PubMed article not found")
    preliminary = assess_metadata(article)
    if preliminary.eligibility == "excluded" or any("Integrity notice" in flag for flag in preliminary.flags):
        return preliminary.model_copy(update={"assessment_status": "skipped"})
    try:
        document = await retrieve_study_document(client, article)
    except FullTextUnavailable as exc:
        return preliminary.model_copy(update={
            "assessment_status": "unavailable", "coverage_note": str(exc),
        })
    return await assess_document(claim, article, document)


async def assess_document(claim: str, article: PubMedArticle, document: StudyDocument) -> StudyAssessment:
    try:
        result = await run_in_threadpool(assess_abstract, claim, article, full_text=document.text)
        return result.model_copy(update={
            "source_url": document.source_url, "source_kind": document.source_kind,
            "coverage_note": document.coverage_note,
        })
    except AssessmentOutputError:
        raise HTTPException(status_code=502, detail="The study assessment could not be verified against the source text. Please retry.") from None
    except FoundryUnavailableError:
        raise HTTPException(status_code=503, detail="Study assessment is unavailable. Please try again.") from None


@router.post("/articles/{pmid}/assess-pdf", response_model=StudyAssessment)
async def assess_uploaded_pdf(
    client: PubMedDep,
    pmid: Annotated[str, Path(pattern=r"^\d{1,9}$")],
    claim: Annotated[str, Form(min_length=1, max_length=2000)],
    file: Annotated[UploadFile, File()],
) -> StudyAssessment:
    try:
        if not claim.strip():
            raise HTTPException(status_code=422, detail="Enter one clear health claim")
        content = await file.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds the 10 MB upload limit.")
        article = await client.get_article(pmid)
        if article is None:
            raise HTTPException(status_code=404, detail="PubMed article not found")
        preliminary = assess_metadata(article)
        if preliminary.eligibility == "excluded" or any("Integrity notice" in flag for flag in preliminary.flags):
            return preliminary.model_copy(update={"assessment_status": "skipped"})
        try:
            document = await run_in_threadpool(extract_pdf, content, article)
        except FullTextUnavailable as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return await assess_document(claim.strip(), article, document)
    finally:
        await file.close()
