"""Preliminary metadata assessment, separate from findings and verdicts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportedMeasure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    # Exact reported text preserves denominators, units and uncertainty.
    reported: str
    passage: str


class StudyAssessment(BaseModel):
    pmid: str
    category: str
    base_weight: int | None
    weight_version: Literal["base_weights_v0.1"] = "base_weights_v0.1"
    eligibility: Literal["excluded", "withheld", "separate"]
    eligibility_reason: str
    effective_weight: int = 0
    flags: list[str]
    assessment_status: Literal["pending", "completed", "unavailable", "skipped"] = "pending"
    summary: str | None = None
    measurement_warnings: list[str] = Field(default_factory=list)
    sample_sizes: list[ReportedMeasure] = Field(default_factory=list)
    effect_estimates: list[ReportedMeasure] = Field(default_factory=list)
    supporting_passages: list[str] = Field(default_factory=list)
    relevance: Literal["not_assessed", "relevant", "not_relevant", "uncertain"] = "not_assessed"
    finding: Literal["not_assessed", "supports", "contradicts", "mixed", "inconclusive", "cannot_determine"] = "not_assessed"
