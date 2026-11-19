"""Integrity screen for notices attached to retrieved studies (#19).

- Retracted (per Crossref or PubMed): excluded from a future synthesis.
- Unresolved expression of concern: withheld from a future synthesis.
- Correction / erratum: flagged for review; no automatic quality judgment.
- No notice found, or not checked: included. "No notice found" is not a
  guarantee, and "not checked" is shown as such.

Retraction is a notice status, not a score adjustment. There is deliberately
no setting to turn this off: verdict code only accepts AdmittedEvidence, and
AdmittedEvidence can only be created here, for studies that passed the gate.
Excluded and withheld studies are still returned so the evidence table can show
them with their notice links.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from app.evidence_models import EvidenceScore
from app.models.crossref import IntegrityNotice, IntegrityReport

IntegrityStatus = Literal["retracted", "expression_of_concern", "corrected", "no_notice_found", "unchecked"]

STATUS_LABELS: dict[IntegrityStatus, str] = {
    "retracted": "Retracted",
    "expression_of_concern": "Expression of concern",
    "corrected": "Correction issued",
    "no_notice_found": "No notice found",
    "unchecked": "Integrity not checked",
}

_ELIGIBILITY_REASONS: dict[IntegrityStatus, str] = {
    "retracted": "Excluded: the study has been retracted.",
    "expression_of_concern": "Withheld: unresolved expression of concern.",
    "corrected": "Included: a correction was issued; no fixed deduction.",
    "no_notice_found": "Included: no integrity notice found.",
    "unchecked": "Included: integrity could not be checked.",
}

_CONTRIBUTES: dict[IntegrityStatus, bool] = {
    "retracted": False,
    "expression_of_concern": False,
    "corrected": True,
    "no_notice_found": True,
    "unchecked": True,
}

# Proof that an AdmittedEvidence was created by this module's gate.
_GATE_TOKEN = object()


@dataclass(frozen=True)
class IntegrityAssessment:
    status: IntegrityStatus
    notices: tuple[IntegrityNotice, ...] = ()

    @property
    def contributes(self) -> bool:
        return _CONTRIBUTES[self.status]

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]

    @property
    def eligibility_reason(self) -> str:
        return _ELIGIBILITY_REASONS[self.status]

    @property
    def notice_urls(self) -> list[str]:
        return [n.notice_url for n in self.notices if n.notice_url]


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


class AdmittedEvidence:
    """A scored study that passed the integrity gate. Only `apply_integrity_gate` creates these."""

    __slots__ = ("score", "integrity")

    def __init__(self, score: EvidenceScore, integrity: IntegrityAssessment, *, _token: object = None):
        if _token is not _GATE_TOKEN:
            raise TypeError("AdmittedEvidence can only be created by apply_integrity_gate()")
        if not integrity.contributes:
            raise ValueError(f"{integrity.label} evidence cannot be admitted to a verdict")
        self.score = score
        self.integrity = integrity

    def __repr__(self) -> str:
        return f"AdmittedEvidence(study_id={self.score.study_id}, status={self.integrity.status!r})"


@dataclass(frozen=True)
class GatedEvidence:
    """A scored study as it should appear in the evidence table, with its integrity status."""

    score: EvidenceScore
    integrity: IntegrityAssessment


@dataclass(frozen=True)
class GateResult:
    # Only this list may reach verdict computation.
    admitted: list[AdmittedEvidence] = field(default_factory=list)
    # Shown in the evidence table, clearly marked, but contributing nothing.
    excluded: list[GatedEvidence] = field(default_factory=list)
    withheld: list[GatedEvidence] = field(default_factory=list)

    @property
    def evidence_table(self) -> list[GatedEvidence]:
        """Every study, admitted or not, for display."""
        admitted = [GatedEvidence(item.score, item.integrity) for item in self.admitted]
        return admitted + self.excluded + self.withheld


def apply_integrity_gate(
    scored: Iterable[tuple[EvidenceScore, IntegrityAssessment]],
) -> GateResult:
    """Split scored studies into those allowed into the verdict and those that are not.

    The scored workflow retains exclusion reasons and separates blocked records
    from admitted records.
    """
    result = GateResult()
    for score, integrity in scored:
        if integrity.contributes:
            admitted_score = replace(score, eligibility_reason=integrity.eligibility_reason)
            result.admitted.append(AdmittedEvidence(admitted_score, integrity, _token=_GATE_TOKEN))
            continue

        blocked = GatedEvidence(
            replace(score, final_weight=0.0, eligibility_reason=integrity.eligibility_reason),
            integrity,
        )
        if integrity.status == "retracted":
            result.excluded.append(blocked)
        else:
            result.withheld.append(blocked)
    return result


def require_admitted(evidence: Sequence[object]) -> Sequence[AdmittedEvidence]:
    """Guard for verdict code: refuse anything that did not come through the gate."""
    for item in evidence:
        if not isinstance(item, AdmittedEvidence):
            raise TypeError(
                "Verdicts only accept evidence from apply_integrity_gate(); "
                f"got {type(item).__name__}"
            )
    return evidence  # type: ignore[return-value]
