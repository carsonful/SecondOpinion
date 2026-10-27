"""Versioned starting weights for resolved study designs (issue #17).

This module does not classify publication tags, assess findings, or compute an
effective contribution. Callers must resolve a design first (#14).
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.metadata import StudyDesign


class WeightRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: Annotated[float, Field(strict=True, ge=0, le=10, allow_inf_nan=False)] | None
    rationale: str = Field(min_length=1)


class WeightConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    rules: dict[StudyDesign, WeightRule]

    @model_validator(mode="after")
    def complete_rules(self) -> "WeightConfig":
        if set(self.rules) != set(StudyDesign):
            raise ValueError("Weight configuration must include every study design")
        for design in (StudyDesign.UNKNOWN, StudyDesign.SYNTHESIS):
            if self.rules[design].weight is not None:
                raise ValueError("Unknown and unresolved synthesis weights must be null")
        return self


@lru_cache
def load_weight_config() -> WeightConfig:
    path = Path(__file__).resolve().parents[1] / "data" / "base_weights_v0.1.json"
    return WeightConfig.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class DesignWeight:
    resolved_design: StudyDesign
    # For a synthesis, identifies its established included design; otherwise the
    # same as resolved_design. None means no numeric design weight is available.
    weighted_design: StudyDesign | None
    base_weight: float | None
    version: str
    reason: str


def _resolved_design(value: str | None) -> StudyDesign:
    try:
        return StudyDesign(value)
    except (ValueError, TypeError):
        return StudyDesign.UNKNOWN


def get_design_weight(
    design: str | None, *, included_design: str | None = None,
    config: WeightConfig | None = None,
) -> DesignWeight:
    """Look up one resolved design, without inferring a design from raw tags.

    For a synthesis, included_design must describe an established homogeneous
    design or a separately reported group. Mixed/unresolved designs stay null.
    No review bonus or addition of overlapping publication-type weights applies.
    """
    config = config if config is not None else load_weight_config()
    resolved = _resolved_design(design)
    weighted = resolved
    reason = config.rules[resolved].rationale
    if resolved == StudyDesign.SYNTHESIS:
        weighted = _resolved_design(included_design)
        if weighted in (
            StudyDesign.UNKNOWN, StudyDesign.SYNTHESIS,
            StudyDesign.GENERAL_REVIEW, StudyDesign.COMMENTARY,
        ):
            weighted = StudyDesign.UNKNOWN
        else:
            reason = "Synthesis uses its established included design, without a review bonus. " + config.rules[weighted].rationale
    weight = config.rules[weighted].weight
    return DesignWeight(
        resolved_design=resolved,
        weighted_design=weighted if weight is not None else None,
        base_weight=weight, version=config.version, reason=reason,
    )
