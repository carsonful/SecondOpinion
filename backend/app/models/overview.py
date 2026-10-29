"""Abstract-based explanations and cited observations; no quality grades."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PassageStatement(Structured):
    text: str = Field(min_length=1, max_length=1200)
    passage: str = Field(min_length=1, max_length=1800)


class StudyExplanation(Structured):
    summary: PassageStatement
    relevance: Literal["direct", "related", "not_addressed", "unclear"]
    relationship: PassageStatement
    gaps: list[str] = Field(max_length=3)


class CitedObservation(Structured):
    text: str = Field(min_length=1, max_length=1200)
    pmids: list[str] = Field(min_length=1, max_length=20)


class Synthesis(Structured):
    observations: list[CitedObservation] = Field(min_length=1, max_length=2)
    qualifications: list[CitedObservation] = Field(max_length=3)


class StudyReading(BaseModel):
    pmid: str
    status: Literal["analyzed", "no_abstract", "withheld", "failed", "outside_limit"]
    reason: str | None = None
    explanation: StudyExplanation | None = None


class OverviewCoverage(BaseModel):
    retrieved: int
    analyzed: int
    direct: int
    related: int
    not_addressed: int
    unclear: int
    no_abstract: int
    withheld: int
    failed: int
    outside_limit: int
    excluded_retracted: int


class ResearchOverview(BaseModel):
    basis: Literal["abstracts"] = "abstracts"
    status: Literal["complete", "partial", "unavailable", "insufficient_information"]
    coverage: OverviewCoverage
    studies: list[StudyReading]
    synthesis: Synthesis | None
    cached: bool = False
