from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.normalization import NormalizedClaim
from app.services.inference_limits import require_inference_budget
from app.services.normalization import (
    ClaimNormalizationError, FoundryUnavailableError, normalize_claim,
)

router = APIRouter(prefix="/claims", tags=["claims"], dependencies=[Depends(require_inference_budget)])


class NormalizeRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=2000)


@router.post("/normalize", responses={
    429: {"description": "Request limit exceeded; retry after Retry-After seconds"},
    503: {"description": "Inference service unavailable"},
})
def normalize(request: NormalizeRequest) -> NormalizedClaim:
    try:
        return normalize_claim(request.raw_text)
    except ClaimNormalizationError:
        raise HTTPException(status_code=422, detail="Enter one clear health-effect claim") from None
    except FoundryUnavailableError:
        raise HTTPException(status_code=503, detail="Inference service unavailable. Try again shortly.") from None
