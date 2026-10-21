from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.assessment import StudyAssessment
from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedSearchResponse


class ClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)


class AssessRequest(ClaimRequest):
    # The claim's ranked studies, so the prompt can say how many were read in full text.
    study_pmids: list[Annotated[str, Field(pattern=r"^\d{1,9}$")]] = Field(default_factory=list, max_length=20)


class ClaimResponse(BaseModel):
    claim: str
    normalized: NormalizedClaim
    evidence: PubMedSearchResponse
    search_scope: Literal["claim", "intervention_only"] = "claim"
    assessments: list[StudyAssessment] = Field(default_factory=list)
    assessment_status: Literal["pending"] = "pending"
    # e.g. "3 of 5 studies were read in full text (2 PMC, 1 open-access PDF); 2 were abstract only."
    full_text_coverage: str | None = None
