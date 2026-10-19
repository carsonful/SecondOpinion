from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.models.claims import ClaimRequest, ClaimResponse
from app.routers.pubmed import PubMedDep
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
    return ClaimResponse(claim=claim, normalized=normalized, evidence=evidence)
