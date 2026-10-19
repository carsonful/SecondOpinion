from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from starlette.concurrency import run_in_threadpool

from app.models.assessment import StudyAssessment
from app.services.findings import AssessmentOutputError, assess_abstract
from app.models.claims import ClaimRequest, ClaimResponse
from app.routers.pubmed import PubMedDep
from app.services.assessment import assess_metadata
from app.services.normalization import (
    ClaimNormalizationError, FoundryUnavailableError, normalize_claim,
)

router = APIRouter(prefix="/claims", tags=["claims"])


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
    evidence = await client.search(normalized.query, 20)
    search_scope = "claim"
    if evidence.total_results == 0:
        # Normalization has already validated this term. Broaden retrieval only;
        # assessments still receive the user's complete original claim.
        broader_query = f"({normalized.intervention})"
        if broader_query != normalized.query:
            evidence = await client.search(broader_query, 20)
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
