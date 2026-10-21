import json
from unittest.mock import AsyncMock, Mock

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.full_text import FullTextRecord, Section
from app.routers import claims
from app.routers.pubmed import get_pubmed_client
from app.services.findings import AssessmentOutputError, assess_abstract
from app.services.full_text import abstract_record
from app.services.study_payload import TRUNCATION_MARK, build_study_payload, coverage_summary
from tests.test_assessment import article
from tests.test_findings import OUTPUT
from tests.test_normalization import settings

PAPER = article(["Randomized Controlled Trial"], pmc_id="PMC456", doi="10.5555/x")


def record(tier="pmc_fulltext", sections=None, pmid="123", **overrides):
    if sections is None:
        sections = [
            Section(type="abstract", heading="Abstract", text="Example abstract."),
            Section(type="introduction", heading="Introduction", text="Background."),
            Section(type="methods", heading="Methods", text="We randomized 120 adults."),
            Section(type="results", heading="Results", text="There was no clear difference."),
            Section(type="discussion", heading="Discussion", text="Interpretation."),
            Section(type="limitations", heading="Limitations", text="Small sample."),
        ]
    values = dict(pmid=pmid, pmcid="PMC456", doi="10.5555/x", title="Example", year=2024, journal="J",
                  publication_types=["Randomized Controlled Trial"], source_tier=tier, license="cc-by",
                  sections=sections)
    return FullTextRecord(**(values | overrides))


def test_payload_sends_only_graded_sections_with_metadata():
    payload = build_study_payload(record(), token_budget=6000)

    assert payload.content["source_tier"] == "pmc_fulltext"
    assert payload.content["publication_types"] == ["Randomized Controlled Trial"]
    assert list(payload.content["sections"]) == ["abstract", "methods", "results", "limitations"]
    assert payload.content["sections"]["methods"] == "Methods\nWe randomized 120 adults."
    assert "truncated_sections" not in payload.content
    assert "Background." not in payload.source_text
    assert "Interpretation." not in payload.source_text


def test_same_type_sections_are_combined():
    sections = [Section(type="methods", heading="Design", text="A."), Section(type="methods", heading="Analysis", text="B.")]
    payload = build_study_payload(record(sections=sections), token_budget=6000)
    assert payload.content["sections"] == {"methods": "Design\nA.\n\nAnalysis\nB."}


def test_budget_truncates_lowest_priority_sections_first():
    long = "x" * 4000
    sections = [Section(type=t, heading=None, text=long) for t in ("abstract", "methods", "results", "limitations")]
    # Room for roughly two and a half sections.
    payload = build_study_payload(record(sections=sections), token_budget=2600)
    sent = payload.content["sections"]

    assert "limitations" not in sent  # dropped entirely: too little left to be useful
    assert sent["methods"].endswith(TRUNCATION_MARK) and len(sent["methods"]) < 4000
    assert sent["results"] == long and sent["abstract"] == long
    assert payload.truncated == ["limitations", "methods"]
    assert payload.content["truncated_sections"] == ["limitations", "methods"]
    assert len(json.dumps(payload.content)) <= 2600 * 4 + 200


def test_abstract_is_cut_only_as_last_resort():
    sections = [Section(type="abstract", heading=None, text="a" * 5000), Section(type="results", heading=None, text="r" * 5000)]
    payload = build_study_payload(record(sections=sections), token_budget=600)
    assert list(payload.content["sections"]) == ["abstract"]
    assert payload.content["sections"]["abstract"].endswith(TRUNCATION_MARK)


def test_all_tiers_produce_the_same_shape():
    shapes = {
        tier: set(build_study_payload(record(tier=tier), 6000).content)
        for tier in ("pmc_fulltext", "oa_pdf", "abstract_only")
    }
    assert shapes["pmc_fulltext"] == shapes["oa_pdf"] == shapes["abstract_only"]


@pytest.mark.parametrize("tiers,expected", [
    (["pmc_fulltext", "pmc_fulltext", "oa_pdf", "abstract_only", "abstract_only"],
     "3 of 5 studies were read in full text (2 PMC, 1 open-access PDF); 2 were abstract only."),
    (["abstract_only"], "0 of 1 study was read in full text; 1 was abstract only."),
    (["oa_pdf", "abstract_only"], "1 of 2 studies were read in full text (1 open-access PDF); 1 was abstract only."),
])
def test_coverage_summary(tiers, expected):
    assert coverage_summary([record(tier=t) for t in tiers]) == expected


def test_coverage_counts_studies_with_no_text():
    records = [record(), record(tier="abstract_only", sections=[])]
    assert coverage_summary(records) == (
        "1 of 2 studies were read in full text (1 PMC); 0 were abstract only; 1 had no study text."
    )
    assert coverage_summary([]) == "No studies were retrieved."


def capture(output=OUTPUT):
    seen = {}

    def handler(request):
        body = json.loads(request.content)
        seen["system"] = body["messages"][0]["content"]
        seen["user"] = json.loads(body["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}]})

    return seen, httpx.MockTransport(handler)


def test_full_text_record_is_sent_as_sections_with_coverage():
    seen, transport = capture(OUTPUT | {"supporting_passages": ["We randomized 120 adults."]})
    coverage = "3 of 5 studies were read in full text (3 PMC); 2 were abstract only."

    result = assess_abstract("raw milk is better", PAPER, record=record(), coverage=coverage,
                             settings=settings(), transport=transport)

    assert seen["user"]["claim"] == "raw milk is better"
    assert seen["user"]["study"]["source_tier"] == "pmc_fulltext"
    assert seen["user"]["study"]["publication_types"] == ["Randomized Controlled Trial"]
    assert set(seen["user"]["study"]["sections"]) == {"abstract", "methods", "results", "limitations"}
    assert seen["user"]["evidence_coverage"] == coverage
    assert "evidence_coverage" in seen["system"]
    assert "labeled sections" in seen["system"]
    assert result.assessment_basis == "full_text"
    assert result.source_tier == "pmc_fulltext"
    assert result.source_kind == "pmc"
    assert result.license == "cc-by"
    assert result.source_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC456/"
    assert result.effective_weight == 0


def test_quotes_from_unsent_sections_are_rejected():
    _, transport = capture(OUTPUT | {"supporting_passages": ["Interpretation."]})
    with pytest.raises(AssessmentOutputError):
        assess_abstract("claim", PAPER, record=record(), settings=settings(), transport=transport)


def test_oa_pdf_record_links_the_doi():
    _, transport = capture()
    result = assess_abstract("claim", PAPER, record=record(tier="oa_pdf", license="cc-by-nc"),
                             settings=settings(), transport=transport)
    assert result.source_kind == "downloaded_pdf"
    assert result.source_url == "https://doi.org/10.5555/x"


def test_abstract_only_keeps_abstract_prompt_and_adds_metadata():
    seen, transport = capture()
    result = assess_abstract("claim", PAPER, record=abstract_record(PAPER), settings=settings(), transport=transport)

    assert seen["user"]["abstract"] == "Example abstract."
    assert seen["user"]["publication_types"] == ["Randomized Controlled Trial"]
    assert seen["user"]["source_tier"] == "abstract_only"
    assert "evidence_coverage" not in seen["user"]
    assert "labeled sections" not in seen["system"]
    assert result.assessment_basis == "abstract"
    assert result.source_tier == "abstract_only"
    assert result.source_url == PAPER.url


def test_no_text_makes_no_model_call():
    transport = httpx.MockTransport(lambda _: pytest.fail("no model call expected"))
    paper = PAPER.model_copy(update={"abstract": None})
    result = assess_abstract("claim", paper, record=abstract_record(paper), settings=settings(), transport=transport)
    assert result.assessment_status == "unavailable"


@pytest.fixture
def pubmed():
    client = AsyncMock()
    client.get_article.return_value = PAPER
    app.dependency_overrides[get_pubmed_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_pubmed_client, None)


def test_assess_route_sends_record_and_claim_coverage(pubmed, full_text_retriever, monkeypatch):
    full_text_retriever.records = {"123": record(), "456": record(tier="abstract_only", pmid="456")}
    assessor = Mock(return_value=claims.assess_metadata(PAPER))
    monkeypatch.setattr(claims, "assess_abstract", assessor)

    response = TestClient(app).post("/api/claims/articles/123/assess",
                                    json={"claim": "claim", "study_pmids": ["123", "456"]})

    assert response.status_code == 200
    assessor.assert_called_once_with(
        "claim", PAPER, record=full_text_retriever.records["123"],
        coverage="1 of 2 studies were read in full text (1 PMC); 1 was abstract only.",
    )


@pytest.mark.parametrize("pmids", [["abc"], [str(n) for n in range(21)]])
def test_assess_route_validates_study_pmids(pubmed, pmids):
    response = TestClient(app).post("/api/claims/articles/123/assess", json={"claim": "claim", "study_pmids": pmids})
    assert response.status_code == 422


@pytest.mark.parametrize("mode", ["full_text", "abstract_only", "retracted"])
def test_full_text_route(pubmed, full_text_retriever, monkeypatch, mode):
    if mode == "retracted":
        pubmed.get_article.return_value = PAPER.model_copy(update={"retracted": True})
    full_text_retriever.records = {"123": record(tier="abstract_only" if mode == "abstract_only" else "pmc_fulltext")}
    assessor = Mock(return_value=claims.assess_metadata(PAPER).model_copy(update={"assessment_status": "completed"}))
    monkeypatch.setattr(claims, "assess_abstract", assessor)

    response = TestClient(app).post("/api/claims/articles/123/assess-full-text", json={"claim": "claim"})

    assert response.status_code == 200
    status = response.json()["assessment_status"]
    assert status == {"full_text": "completed", "abstract_only": "unavailable", "retracted": "skipped"}[mode]
    if mode == "full_text":
        assessor.assert_called_once_with("claim", PAPER, record=full_text_retriever.records["123"], coverage=None)
    else:
        assessor.assert_not_called()
    if mode == "abstract_only":
        assert "upload" in response.json()["coverage_note"]
