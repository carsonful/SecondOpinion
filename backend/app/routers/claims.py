import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.claims import ClaimCandidates, ClaimRequest
from app.routers.crossref import CrossrefDep
from app.routers.pubmed import PubMedDep
from app.services.pmc import PMCClient
from app.services.claims import ClaimsCache, retrieve_candidates
from app.services.normalization import ClaimNormalizationError, FoundryUnavailableError

from app.models.overview import ResearchOverview
from app.services.research_overview import register_snapshot, snapshots, shared_overview

router = APIRouter(prefix="/claims", tags=["claims"])


def get_pmc_client(request: Request) -> PMCClient | None:
    return getattr(request.app.state, "pmc_client", None)


PMCDep = Annotated[PMCClient | None, Depends(get_pmc_client)]


def get_claims_cache(request: Request) -> ClaimsCache:
    return request.app.state.claims_cache


@router.post("", responses={
    422: {"description": "Invalid input or not one clear health claim"},
    502: {"description": "An evidence source returned an unusable response"},
    503: {"description": "Normalization or an evidence source is unavailable"},
})
async def search_claim(
    request: ClaimRequest, pubmed: PubMedDep,
    cache: Annotated[ClaimsCache, Depends(get_claims_cache)],
    pmc: PMCDep, crossref: CrossrefDep,
    refresh: Annotated[bool, Query(description="Skip the cache and fetch fresh results.")] = False,
) -> ClaimCandidates:
    """Return deduplicated candidate studies in PubMed relevance order.

    Includes study-type metadata, full-text access details, and retraction,
    correction, and concern notices from Crossref and PubMed. Retracted studies
    are left out and listed in `excluded_retracted`. No grades or verdicts are computed. An empty search is a successful response.
    Repeated claims are served from an in-memory cache; `cached` says when.
    """
    try:
        result = await retrieve_candidates(
            request.claim, request.limit, pubmed, cache=cache, refresh=refresh, pmc=pmc,
            crossref=crossref,
        )
        return result.model_copy(update={"analysis_id": register_snapshot(result)})
    except ClaimNormalizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FoundryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/overview/{analysis_id}", response_model=ResearchOverview)
async def research_overview(analysis_id: str) -> ResearchOverview:
    snapshot = snapshots.get(analysis_id)
    if snapshot is None:
        raise HTTPException(status_code=410, detail="Search snapshot expired. Refresh the search.")
    try:
        async with asyncio.timeout(240):
            return await shared_overview(snapshot)
    except TimeoutError:
        raise HTTPException(status_code=503, detail="Overview took too long. Retry; your studies are still available.") from None
