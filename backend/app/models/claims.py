"""Claim search response and candidate study metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.crossref import IntegrityNotice
from app.models.normalization import NormalizedClaim
from app.models.metadata import StudyMetadata
from app.models.full_text import EvidenceCoverage, FullTextAccess
from app.models.pubmed import PubMedArticle


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
    """Retraction, correction, and concern notices for one study, from Crossref and PubMed.

    A notice is a fact about the paper, not a grade. Retracted studies are left out
    of `candidates` and listed in `excluded_retracted` instead.
    """

    status: Literal["retracted", "expression_of_concern", "corrected", "no_notice_found", "unchecked"]
    label: str
    notices: list[IntegrityNotice]


class CandidateStudy(BaseModel):
    article: PubMedArticle
    metadata: StudyMetadata
    access: FullTextAccess
    integrity: CandidateIntegrity


class ClaimCandidates(BaseModel):
    status: Literal["candidates"] = "candidates"
    claim: str
    normalized: NormalizedClaim
    query_translation: str | None
    total_results: int = Field(description="Total PubMed search matches before the limit and deduplication.")
    cached: bool = Field(
        default=False,
        description="True when the studies came from the server's cache instead of new PubMed and PMC calls.",
    )
    coverage: EvidenceCoverage
    # PubMed relevance order, after deduplication. Not a quality ranking.
    candidates: list[CandidateStudy] = Field(
        description="Deduplicated studies in PubMed relevance order, with study-design metadata and full-text access details. No grades, scores, or verdicts are assigned.",
    )
    excluded_retracted: list[CandidateStudy] = Field(
        default_factory=list,
        description="Studies left out of candidates because Crossref or PubMed reports them retracted, with their notices.",
    )
