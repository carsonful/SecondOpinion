from typing import Literal

from pydantic import BaseModel, Field

from app.models.assessment import StudyAssessment
from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedSearchResponse


class ClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)


class ClaimResponse(BaseModel):
    claim: str
    normalized: NormalizedClaim
    evidence: PubMedSearchResponse
    search_scope: Literal["claim", "intervention_only"] = "claim"
    assessments: list[StudyAssessment] = Field(default_factory=list)
    assessment_status: Literal["pending"] = "pending"
