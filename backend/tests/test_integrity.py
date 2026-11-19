import json
from collections.abc import Sequence
from typing import Literal
from uuid import UUID, uuid4

import pytest

from app import evidence_workflow
from app.config import Settings
from app.evidence_models import Claim, EvidenceScore
from app.models.crossref import IntegrityReport
from app.services import integrity
from app.services.crossref import build_report
from app.services.integrity import (
    AdmittedEvidence,
    IntegrityAssessment,
    apply_integrity_gate,
    assess_integrity,
    require_admitted,
)
from tests.helpers import load_fixture

Finding = Literal["supports", "contradicts"]

CLAIM_ID = uuid4()


def crossref_report(fixture: str) -> IntegrityReport:
    """Build a report from a recorded Crossref response, as CrossrefClient.check would."""
    message = json.loads(load_fixture(f"crossref/{fixture}"))["message"]
    return build_report(message["DOI"].lower(), message.get("updated-by", []))


NOT_FOUND = IntegrityReport(
    doi="10.9999/unknown", found=False, retracted=None,
    has_expression_of_concern=None, has_correction=None, notices=[],
)


def scored(weight: float) -> EvidenceScore:
    return EvidenceScore(
        claim_id=CLAIM_ID,
        study_id=uuid4(),
        component_scores={"base_weight": weight},
        final_weight=weight,
        weight_version="base_weights_v0.1",
    )


def stand_in_verdict(
    evidence: Sequence[AdmittedEvidence], findings: dict[UUID, Finding]
) -> str:
    """Deliberately naive weighted vote, standing in for #20's verdict rules.

    If even this can't be swung by a retracted study, the gate is doing its job,
    whatever rules #20 ends up using.
    """
    require_admitted(evidence)
    support = sum(e.score.final_weight for e in evidence if findings[e.score.study_id] == "supports")
    against = sum(e.score.final_weight for e in evidence if findings[e.score.study_id] == "contradicts")
    return "supported" if support > against else "refuted"


# --- assess_integrity -------------------------------------------------------------


def test_retracted_paper_is_excluded_with_its_notice_link() -> None:
    assessment = assess_integrity(crossref_report("work_wakefield_retracted.json"))

    assert assessment.status == "retracted"
    assert assessment.contributes is False
    assert assessment.label == "Retracted"
    assert assessment.notice_urls == ["https://doi.org/10.1016/s0140-6736(10)60175-4"]


def test_retraction_outranks_concern_and_corrections() -> None:
    assessment = assess_integrity(crossref_report("work_surgisphere_retracted.json"))

    assert assessment.status == "retracted"
    assert {n.category for n in assessment.notices} == {"retraction"}


def test_expression_of_concern_is_withheld() -> None:
    assessment = assess_integrity(crossref_report("work_concern_only.json"))

    assert assessment.status == "expression_of_concern"
    assert assessment.contributes is False
    assert assessment.notice_urls == ["https://doi.org/10.1016/j.lungcan.2026.109332"]


def test_correction_is_included_without_a_deduction() -> None:
    assessment = assess_integrity(crossref_report("work_correction_only.json"))

    assert assessment.status == "corrected"
    assert assessment.contributes is True
    assert assessment.label == "Correction issued"


def test_clean_paper_is_no_notice_found_not_verified() -> None:
    assessment = assess_integrity(crossref_report("work_cochrane_clean.json"))

    assert assessment.status == "no_notice_found"
    assert assessment.contributes is True
    assert assessment.notices == ()


@pytest.mark.parametrize("crossref", [None, NOT_FOUND])
def test_without_a_crossref_record_the_study_is_unchecked(crossref: IntegrityReport | None) -> None:
    assert assess_integrity(crossref).status == "unchecked"
    assert assess_integrity(crossref, pubmed_retracted=False).status == "unchecked"


@pytest.mark.parametrize("crossref", [None, NOT_FOUND])
def test_pubmed_retraction_marker_alone_excludes(crossref: IntegrityReport | None) -> None:
    assert assess_integrity(crossref, pubmed_retracted=True).status == "retracted"


def test_pubmed_retraction_marker_overrides_a_clean_crossref_record() -> None:
    clean = crossref_report("work_cochrane_clean.json")

    assert assess_integrity(clean, pubmed_retracted=True).status == "retracted"


# --- apply_integrity_gate --------------------------------------------------------


def test_gate_splits_studies_and_zeroes_blocked_weights() -> None:
    retracted, concern, corrected, clean = scored(8), scored(5), scored(4), scored(3)

    result = apply_integrity_gate([
        (retracted, assess_integrity(crossref_report("work_wakefield_retracted.json"))),
        (concern, assess_integrity(crossref_report("work_concern_only.json"))),
        (corrected, assess_integrity(crossref_report("work_correction_only.json"))),
        (clean, assess_integrity(crossref_report("work_cochrane_clean.json"))),
    ])

    assert [e.score.study_id for e in result.admitted] == [corrected.study_id, clean.study_id]
    assert [e.score.final_weight for e in result.admitted] == [4, 3]

    (excluded,) = result.excluded
    assert excluded.score.study_id == retracted.study_id
    assert excluded.score.final_weight == 0.0
    # The recorded design weight is preserved; only the contribution is zeroed.
    assert excluded.score.component_scores == {"base_weight": 8}
    assert excluded.score.eligibility_reason == "Excluded: the study has been retracted."

    (withheld,) = result.withheld
    assert withheld.score.study_id == concern.study_id
    assert withheld.score.final_weight == 0.0
    assert "expression of concern" in withheld.score.eligibility_reason


def test_gate_does_not_modify_the_original_scores() -> None:
    score = scored(8)

    apply_integrity_gate([(score, IntegrityAssessment("retracted"))])

    assert score.final_weight == 8
    assert score.eligibility_reason is None


def test_evidence_table_still_shows_blocked_studies_with_notice_links() -> None:
    result = apply_integrity_gate([
        (scored(8), assess_integrity(crossref_report("work_wakefield_retracted.json"))),
        (scored(3), assess_integrity(crossref_report("work_cochrane_clean.json"))),
    ])

    rows = {row.integrity.label: row for row in result.evidence_table}
    assert set(rows) == {"Retracted", "No notice found"}
    assert rows["Retracted"].integrity.notice_urls == [
        "https://doi.org/10.1016/s0140-6736(10)60175-4"
    ]


# --- The #19 guarantee ------------------------------------------------------------


@pytest.mark.parametrize("meta_analysis_weight", [8, 10, 1000])
@pytest.mark.parametrize(
    "retraction_source",
    [
        {"crossref": "work_wakefield_retracted.json", "pubmed_retracted": False},
        {"crossref": None, "pubmed_retracted": True},
    ],
    ids=["crossref", "pubmed"],
)
def test_retracted_meta_analysis_cannot_flip_a_verdict_to_supported(
    meta_analysis_weight: float, retraction_source: dict
) -> None:
    trial_a, trial_b = scored(8), scored(8)
    meta_analysis = scored(meta_analysis_weight)
    findings: dict[UUID, Finding] = {
        trial_a.study_id: "contradicts",
        trial_b.study_id: "contradicts",
        meta_analysis.study_id: "supports",
    }
    clean = assess_integrity(crossref_report("work_cochrane_clean.json"))
    crossref = retraction_source["crossref"]
    retracted = assess_integrity(
        crossref_report(crossref) if crossref else None,
        pubmed_retracted=retraction_source["pubmed_retracted"],
    )

    result = apply_integrity_gate([(trial_a, clean), (trial_b, clean), (meta_analysis, retracted)])

    assert stand_in_verdict(result.admitted, findings) == "refuted"
    assert meta_analysis.study_id not in {e.score.study_id for e in result.admitted}


def test_the_scenario_would_flip_without_the_gate() -> None:
    """Shows the guarantee test is meaningful: ungated, the retracted study wins."""
    trial_a, trial_b, meta_analysis = scored(8), scored(8), scored(1000)
    findings: dict[UUID, Finding] = {
        trial_a.study_id: "contradicts",
        trial_b.study_id: "contradicts",
        meta_analysis.study_id: "supports",
    }
    no_notice = IntegrityAssessment("no_notice_found")

    result = apply_integrity_gate([(s, no_notice) for s in (trial_a, trial_b, meta_analysis)])

    assert stand_in_verdict(result.admitted, findings) == "supported"


def test_admitted_evidence_cannot_be_created_outside_the_gate() -> None:
    with pytest.raises(TypeError, match="apply_integrity_gate"):
        AdmittedEvidence(scored(8), IntegrityAssessment("no_notice_found"))


def test_admitted_evidence_refuses_retracted_studies_even_with_the_gate_token() -> None:
    with pytest.raises(ValueError):
        AdmittedEvidence(scored(8), IntegrityAssessment("retracted"), _token=integrity._GATE_TOKEN)


@pytest.mark.parametrize("item", [scored(8), "not evidence"])
def test_verdict_code_rejects_evidence_that_skipped_the_gate(item: object) -> None:
    with pytest.raises(TypeError, match="apply_integrity_gate"):
        require_admitted([item])


def test_generate_verdict_rejects_ungated_scores_before_anything_else() -> None:
    claim = Claim(raw_text="zinc cures colds", id=CLAIM_ID)

    with pytest.raises(TypeError, match="apply_integrity_gate"):
        evidence_workflow.generate_verdict(claim, [scored(8)])

    gated = apply_integrity_gate([(scored(8), IntegrityAssessment("no_notice_found"))])
    with pytest.raises(NotImplementedError):
        evidence_workflow.generate_verdict(claim, gated.admitted)


def test_no_setting_can_disable_the_exclusion() -> None:
    risky = ("retract", "integrity", "exclu", "gate", "concern")
    fields = [name for name in Settings.model_fields if any(word in name for word in risky)]

    assert fields == []
