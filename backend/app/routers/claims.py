from fastapi import APIRouter, HTTPException

from app.models.claims import ClaimCandidates, ClaimRequest
from app.routers.crossref import CrossrefDep
from app.routers.pubmed import PubMedDep
from app.services.claims import retrieve_candidates
from app.services.normalization import ClaimNormalizationError, FoundryUnavailableError

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", responses={
    422: {"description": "Invalid input or not one clear health claim"},
    502: {"description": "An evidence source returned an unusable response"},
    503: {"description": "Normalization or an evidence source is unavailable"},
})
async def search_claim(
    request: ClaimRequest, pubmed: PubMedDep, crossref: CrossrefDep,
) -> ClaimCandidates:
    """Return deduplicated candidate studies in PubMed relevance order.

    Includes retracted and withheld papers with integrity notices for display.
    Missing or invalid DOIs remain unchecked. Includes extracted metadata and
    provisional base design weights; no verdict or confidence score is computed.
    An empty search is a successful response with an empty candidates list.
    """
    try:
        return await retrieve_candidates(request.claim, request.limit, pubmed, crossref)
    except ClaimNormalizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FoundryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
