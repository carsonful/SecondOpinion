from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.claims import ClaimCandidates, ClaimRequest
from app.routers.pubmed import PubMedDep
from app.services.pmc import PMCClient
from app.services.claims import ClaimsCache, retrieve_candidates
from app.services.normalization import ClaimNormalizationError, FoundryUnavailableError

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
    pmc: PMCDep,
    refresh: Annotated[bool, Query(description="Skip the cache and fetch fresh results.")] = False,
) -> ClaimCandidates:
    """Return deduplicated candidate studies in PubMed relevance order.

    Includes study-type metadata and full-text access details. No grades or
    verdicts are computed. An empty search is a successful response.
    Repeated claims are served from an in-memory cache; `cached` says when.
    """
    try:
        return await retrieve_candidates(
            request.claim, request.limit, pubmed, cache=cache, refresh=refresh, pmc=pmc,
        )
    except ClaimNormalizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FoundryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
