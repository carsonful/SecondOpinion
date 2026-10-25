"""Draft data contract for issue #3; these are not database tables yet.

Claim -> many EvidenceScores <- Study; Claim -> one current Verdict.
None means unknown or not assessed, never zero or false.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4


@dataclass
class Claim:
    raw_text: str
    id: UUID = field(default_factory=uuid4)
    normalized_query: str | None = None  # Not normalized yet.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["pending", "processing", "completed", "failed"] = "pending"


@dataclass
class Study:
    title: str
    id: UUID = field(default_factory=uuid4)
    pmid: str | None = None  # Source may only provide a DOI, or neither ID.
    doi: str | None = None
    journal: str | None = None  # Missing source metadata stays unknown.
    year: int | None = None
    study_type: str | None = None
    sample_size: int | None = None
    retracted: bool | None = None  # None = unchecked; False = checked, no notice found.
    # Canonical design for an established homogeneous synthesis or separately
    # reported design group. Never infer this from the review label alone.
    synthesis_included_design: str | None = None


@dataclass
class EvidenceScore:
    claim_id: UUID
    study_id: UUID
    # Draft components: add only rules the team has agreed to implement.
    component_scores: dict[str, float | None] = field(default_factory=dict)
    final_weight: float | None = None  # Not scored yet; 0 is a known non-contribution.
    weight_version: str | None = None  # Set when scoring rules are applied.
    eligibility_reason: str | None = None
    resolved_design: str | None = None
    weighted_design: str | None = None
    weight_reason: str | None = None


@dataclass
class Verdict:
    claim_id: UUID
    outcome: Literal["supported", "refuted", "unproven"]
    explanation: str
    # Qualitative confidence is a proposal for team review, not a probability.
    confidence: Literal["low", "moderate", "high"] | None = None
