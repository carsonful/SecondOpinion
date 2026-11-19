import json

import pytest

from app.config import Settings
from app.models.crossref import IntegrityReport
from app.services.crossref import build_report
from app.services.integrity import assess_integrity
from tests.helpers import load_fixture

def crossref_report(fixture: str) -> IntegrityReport:
    """Build a report from a recorded Crossref response, as CrossrefClient.check would."""
    message = json.loads(load_fixture(f"crossref/{fixture}"))["message"]
    return build_report(message["DOI"].lower(), message.get("updated-by", []))


NOT_FOUND = IntegrityReport(
    doi="10.9999/unknown", found=False, retracted=None,
    has_expression_of_concern=None, has_correction=None, notices=[],
)


def test_retracted_paper_is_excluded_with_its_notice_link() -> None:
    assessment = assess_integrity(crossref_report("work_wakefield_retracted.json"))

    assert assessment.status == "retracted"
    assert assessment.label == "Retracted"
    assert [notice.notice_url for notice in assessment.notices] == ["https://doi.org/10.1016/s0140-6736(10)60175-4"]


def test_retraction_outranks_concern_and_corrections() -> None:
    assessment = assess_integrity(crossref_report("work_surgisphere_retracted.json"))

    assert assessment.status == "retracted"
    assert {n.category for n in assessment.notices} == {"retraction"}


def test_expression_of_concern_is_withheld() -> None:
    assessment = assess_integrity(crossref_report("work_concern_only.json"))

    assert assessment.status == "expression_of_concern"
    assert [notice.notice_url for notice in assessment.notices] == ["https://doi.org/10.1016/j.lungcan.2026.109332"]


def test_correction_is_labeled() -> None:
    assessment = assess_integrity(crossref_report("work_correction_only.json"))

    assert assessment.status == "corrected"
    assert assessment.label == "Correction issued"


def test_clean_paper_is_no_notice_found_not_verified() -> None:
    assessment = assess_integrity(crossref_report("work_cochrane_clean.json"))

    assert assessment.status == "no_notice_found"
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


def test_no_setting_can_disable_the_exclusion() -> None:
    risky = ("retract", "integrity", "exclu", "gate", "concern")
    fields = [name for name in Settings.model_fields if any(word in name for word in risky)]

    assert fields == []
