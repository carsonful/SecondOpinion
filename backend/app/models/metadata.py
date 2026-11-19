"""Conservative extraction of study design and participant metadata."""

from enum import StrEnum

from pydantic import BaseModel


class StudyDesign(StrEnum):
    RANDOMIZED_TRIAL = "randomized_controlled_trial"
    INTERVENTION = "intervention_randomization_unknown"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    OBSERVATIONAL = "observational_subtype_unknown"
    DESCRIPTIVE = "case_report_or_series"
    GENERAL_REVIEW = "general_review"
    COMMENTARY = "commentary"
    SYNTHESIS = "research_synthesis"
    UNKNOWN = "unknown"


class StudyMetadata(BaseModel):
    design: StudyDesign
