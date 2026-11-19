"""Combine Crossref notices and PubMed retraction markers for retrieved studies."""

from dataclasses import dataclass
from typing import Literal

from app.models.crossref import IntegrityNotice, IntegrityReport

IntegrityStatus = Literal["retracted", "expression_of_concern", "corrected", "no_notice_found", "unchecked"]

STATUS_LABELS: dict[IntegrityStatus, str] = {
    "retracted": "Retracted",
    "expression_of_concern": "Expression of concern",
    "corrected": "Correction issued",
    "no_notice_found": "No notice found",
    "unchecked": "Integrity not checked",
}


@dataclass(frozen=True)
class IntegrityAssessment:
    status: IntegrityStatus
    notices: tuple[IntegrityNotice, ...] = ()

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]


def assess_integrity(
    crossref: IntegrityReport | None, pubmed_retracted: bool | None = None
) -> IntegrityAssessment:
    """Combine Crossref's report and PubMed's retraction marker into one status.

    Either source reporting a retraction is enough to exclude the study.
    Precedence: retracted > expression of concern > corrected > no notice found.
    """
    found = crossref is not None and crossref.found
    notices = tuple(crossref.notices) if found else ()

    if pubmed_retracted or (found and crossref.retracted):
        relevant = tuple(n for n in notices if n.category == "retraction")
        return IntegrityAssessment("retracted", relevant)
    if found and crossref.has_expression_of_concern:
        relevant = tuple(n for n in notices if n.category == "expression_of_concern")
        return IntegrityAssessment("expression_of_concern", relevant)
    if found and crossref.has_correction:
        relevant = tuple(n for n in notices if n.category == "correction")
        return IntegrityAssessment("corrected", relevant)
    if found:
        return IntegrityAssessment("no_notice_found")
    # PubMed's marker lags behind and has no corrections or concerns, so a PubMed
    # "not retracted" alone does not count as checked.
    return IntegrityAssessment("unchecked")
