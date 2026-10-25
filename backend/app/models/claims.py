"""Candidate retrieval contract; assessment and verdicts are separate work."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.crossref import IntegrityNotice
from app.models.normalization import NormalizedClaim
from app.models.metadata import CandidateWeight, StudyMetadata
from app.models.pubmed import PubMedArticle
from app.services.integrity import IntegrityStatus


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(
        min_length=1, max_length=2000,
        description="One raw health-effect claim or question; surrounding whitespace is removed.",
        examples=["Does zinc help with the common cold?"],
    )
    limit: int = Field(
        default=20, ge=1, le=100,
        description="Maximum PubMed records to retrieve before deduplication; fewer candidates may be returned.",
    )

    @field_validator("claim")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter one health claim")
        return value.strip()


class CandidateIntegrity(BaseModel):
    status: IntegrityStatus
    notices: list[IntegrityNotice]


class CandidateStudy(BaseModel):
    article: PubMedArticle
    integrity: CandidateIntegrity
    metadata: StudyMetadata
    weight: CandidateWeight


class ClaimCandidates(BaseModel):
    status: Literal["candidates"] = "candidates"
    claim: str
    normalized: NormalizedClaim
    query_translation: str | None
    total_results: int = Field(description="Total PubMed search matches before the limit and deduplication.")
    # PubMed relevance order, after deduplication. Not a quality ranking.
    candidates: list[CandidateStudy] = Field(
        description="Deduplicated studies in PubMed relevance order, with extracted metadata and provisional base design weights. No verdict or confidence score is assigned.",
    )
