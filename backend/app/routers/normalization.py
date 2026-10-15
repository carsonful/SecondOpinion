from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.normalization import NormalizedClaim
from app.services.foundry_normalization import FoundryUnavailableError, normalize_claim
from app.services.normalization import ClaimNormalizationError

router = APIRouter(prefix="/claims", tags=["claims"])


class NormalizeRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=2000)


@router.post("/normalize")
def normalize(request: NormalizeRequest) -> NormalizedClaim:
    try:
        return normalize_claim(request.raw_text)
    except ClaimNormalizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except FoundryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
