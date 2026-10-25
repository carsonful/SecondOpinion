"""Conservative metadata extraction and provisional weighting contract."""

from pydantic import BaseModel

from app.services.weighting import StudyDesign


class StudyMetadata(BaseModel):
    design: StudyDesign
    design_reason: str
    design_evidence: str | None
    sample_size: int | None
    sample_size_evidence: str | None
    sample_size_reason: str
    animal_only: bool


class CandidateWeight(BaseModel):
    base_weight: float | None
    final_weight: float | None
    version: str
    reason: str
    eligibility_reason: str
