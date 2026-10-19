from typing import Literal

from pydantic import BaseModel, Field

from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedSearchResponse


class ClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)


class ClaimResponse(BaseModel):
    claim: str
    normalized: NormalizedClaim
    evidence: PubMedSearchResponse
    assessment_status: Literal["pending"] = "pending"
