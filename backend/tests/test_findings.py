import json

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import claims
from app.routers.pubmed import get_pubmed_client
from app.services.findings import assess_abstract
from app.services.normalization import FoundryUnavailableError
from tests.test_assessment import article
from tests.test_normalization import settings
from unittest.mock import AsyncMock


OUTPUT = dict(relevance="relevant", finding="inconclusive", summary="The abstract is inconclusive.",
              supporting_passages=["Example abstract."], sample_sizes=[], effect_estimates=[])


def transport(output=None, status=200, finish="stop"):
    return httpx.MockTransport(lambda _: httpx.Response(status, json={
        "choices": [{"finish_reason": finish, "message": {"content": json.dumps(OUTPUT if output is None else output)}}],
    }))


def test_assessment_preserves_claim_and_quotes():
    def handler(request):
        body = json.loads(request.content)
        assert json.loads(body["messages"][1]["content"])["claim"] == "zinc does not cure colds"
        assert body["response_format"]["json_schema"]["strict"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(OUTPUT)}}]})
    result = assess_abstract("zinc does not cure colds", article(["Randomized Controlled Trial"]),
                             settings=settings(), transport=httpx.MockTransport(handler))
    assert result.assessment_status == "completed"
    assert result.supporting_passages == ["Example abstract."]
    assert result.base_weight == 8
    assert result.effective_weight == 0
    assert result.eligibility == "withheld"


@pytest.mark.parametrize("updates", [
    {"supporting_passages": ["Invented quote"]},
    {"supporting_passages": []}, {"supporting_passages": ["   "]},
    {"supporting_passages": ["Example abstract."] * 4},
    {"summary": " "}, {"relevance": "not_relevant", "finding": "supports"},
    {"finding": "made_up"}, {"confidence": 99},
])
def test_invalid_outputs_rejected(updates):
    with pytest.raises(FoundryUnavailableError):
        assess_abstract("claim", article(), settings=settings(), transport=transport(OUTPUT | updates))


@pytest.mark.parametrize("status,finish", [(401, "stop"), (429, "stop"), (500, "stop"), (200, "length")])
def test_provider_failures(status, finish):
    with pytest.raises(FoundryUnavailableError):
        assess_abstract("claim", article(), settings=settings(), transport=transport(status=status, finish=finish))


@pytest.mark.parametrize("paper,state", [
    (article(abstract=None), "unavailable"), (article(retracted=True), "skipped"),
    (article(["Expression of Concern"]), "skipped"),
])
def test_unassessable_records_skip_foundry(paper, state):
    result = assess_abstract("claim", paper, settings=settings(azure_foundry_api_key=None))
    assert result.assessment_status == state
    assert result.finding == "not_assessed"


def test_irrelevant_excluded():
    result = assess_abstract("claim", article(), settings=settings(), transport=transport(
        OUTPUT | dict(relevance="not_relevant", finding="cannot_determine")))
    assert result.eligibility == "excluded"


def test_preprint_stays_separate():
    result = assess_abstract("claim", article(["Preprint"]), settings=settings(), transport=transport())
    assert result.eligibility == "separate"


@pytest.fixture
def api(monkeypatch):
    client = AsyncMock()
    client.get_article.return_value = article()
    app.dependency_overrides[get_pubmed_client] = lambda: client
    monkeypatch.setattr(claims, "assess_abstract", lambda claim, paper: assess_abstract(
        claim, paper, settings=settings(), transport=transport()))
    try:
        yield TestClient(app), client
    finally:
        app.dependency_overrides.clear()


def test_route(api):
    client, pubmed = api
    response = client.post("/api/claims/articles/123/assess", json={"claim": "test claim"})
    assert response.status_code == 200
    assert response.json()["assessment_status"] == "completed"
    pubmed.get_article.assert_awaited_once_with("123")


def test_route_unknown_article(api):
    client, pubmed = api
    pubmed.get_article.return_value = None
    assert client.post("/api/claims/articles/123/assess", json={"claim": "test"}).status_code == 404


@pytest.mark.parametrize("pmid,claim", [("bad", "claim"), ("123", "   "), ("123", "x" * 2001)])
def test_route_validation(api, pmid, claim):
    client, pubmed = api
    assert client.post(f"/api/claims/articles/{pmid}/assess", json={"claim": claim}).status_code == 422
    pubmed.get_article.assert_not_awaited()


def test_route_failure_preserves_private_details(api, monkeypatch):
    client, _ = api
    def fail(*args):
        raise FoundryUnavailableError("private provider response")
    monkeypatch.setattr(claims, "assess_abstract", fail)
    response = client.post("/api/claims/articles/123/assess", json={"claim": "test"})
    assert response.status_code == 503
    assert "private" not in response.text


MEASURE_ABSTRACT = (
    "We randomized 120 adults, 60 per group. "
    "At 12 weeks, pain was lower with treatment than placebo (mean difference -2 points; 95% CI -3 to -1)."
)


def test_reported_measures_preserve_context_and_uncertainty():
    output = OUTPUT | dict(
        supporting_passages=[MEASURE_ABSTRACT],
        sample_sizes=[dict(reported="120 adults", passage="We randomized 120 adults, 60 per group.")],
        effect_estimates=[dict(reported="mean difference -2 points; 95% CI -3 to -1", passage=MEASURE_ABSTRACT.split(". ", 1)[1])],
    )
    result = assess_abstract("claim", article(abstract=MEASURE_ABSTRACT), settings=settings(), transport=transport(output))
    assert result.sample_sizes[0].reported == "120 adults"
    assert "95% CI" in result.effect_estimates[0].reported
    assert result.effective_weight == 0


@pytest.mark.parametrize("field", ["sample_sizes", "effect_estimates"])
@pytest.mark.parametrize("measure", [
    dict(reported="240 adults", passage=MEASURE_ABSTRACT),
    dict(reported="120 adults", passage="We studied 120 adults in an invented trial."),
    dict(reported=" ", passage=MEASURE_ABSTRACT),
])
def test_invented_measurements_omitted(field, measure):
    output = OUTPUT | dict(supporting_passages=[MEASURE_ABSTRACT]) | {field: [measure]}
    result = assess_abstract("claim", article(abstract=MEASURE_ABSTRACT), settings=settings(), transport=transport(output))
    assert result.assessment_status == "completed"
    assert getattr(result, field) == []
    assert result.measurement_warnings
    assert result.supporting_passages == [MEASURE_ABSTRACT]


@pytest.mark.parametrize("relation", ["ErratumIn", "ExpressionOfConcernIn"])
def test_integrity_reason_survives_assessment(relation):
    paper = article(["Randomized Controlled Trial", "Preprint"], integrity_links=[dict(relation=relation, pmid="2")])
    result = assess_abstract("claim", paper, settings=settings(), transport=transport())
    assert result.eligibility == "withheld"
    assert "requires review" in result.eligibility_reason
    assert result.base_weight == 8
    assert result.effective_weight == 0


@pytest.mark.parametrize("relation", ["RetractionOf", "ErratumFor", "ExpressionOfConcernFor"])
def test_notice_records_skip_provider_without_publication_tag(relation):
    result = assess_abstract("claim", article(integrity_links=[dict(relation=relation)]),
                             settings=settings(azure_foundry_api_key=None))
    assert result.assessment_status == "skipped"


def test_absent_measurements_stay_empty():
    result = assess_abstract("claim", article(), settings=settings(), transport=transport())
    assert result.sample_sizes == result.effect_estimates == []


def test_invalid_output_route_is_502(api, monkeypatch):
    from app.services.findings import AssessmentOutputError
    client, _ = api
    def fail(*args):
        raise AssessmentOutputError("private output")
    monkeypatch.setattr(claims, "assess_abstract", fail)
    response = client.post("/api/claims/articles/123/assess", json={"claim": "test"})
    assert response.status_code == 502
    assert "could not be verified" in response.json()["detail"]
    assert "private" not in response.text


def test_validation_diagnostic_excludes_provider_content(caplog):
    result = assess_abstract("private claim", article(), settings=settings(),
                             transport=transport(OUTPUT | {"sample_sizes": [{"reported": "private value", "passage": "private quote"}]}))
    assert result.sample_sizes == []
    assert "field=sample_sizes count=1" in caplog.text
    assert "private" not in caplog.text
    assert "test-secret" not in caplog.text


def test_http_diagnostic_has_status_not_response_body(caplog):
    with pytest.raises(FoundryUnavailableError):
        assess_abstract("private claim", article(), settings=settings(),
                        transport=httpx.MockTransport(lambda _: httpx.Response(429, text="private secret")))
    assert "http_status=429" in caplog.text
    assert "private" not in caplog.text


def test_mixed_measurements_keep_only_verified_values():
    output = OUTPUT | dict(supporting_passages=[MEASURE_ABSTRACT], sample_sizes=[
        dict(reported="120 adults", passage=MEASURE_ABSTRACT),
        dict(reported="240 adults", passage=MEASURE_ABSTRACT),
    ])
    result = assess_abstract("claim", article(abstract=MEASURE_ABSTRACT), settings=settings(), transport=transport(output))
    assert [item.reported for item in result.sample_sizes] == ["120 adults"]
    assert len(result.measurement_warnings) == 1


def test_measurement_display_limit_does_not_fail_assessment():
    output = OUTPUT | dict(supporting_passages=[MEASURE_ABSTRACT], sample_sizes=[
        dict(reported="120 adults", passage=MEASURE_ABSTRACT),
    ] * 11)
    result = assess_abstract("claim", article(abstract=MEASURE_ABSTRACT), settings=settings(), transport=transport(output))
    assert len(result.sample_sizes) == 10
    assert result.measurement_warnings


def test_measurement_failure_returns_success_with_warning(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(claims, "assess_abstract", lambda claim, paper: assess_abstract(
        claim, paper, settings=settings(), transport=transport(OUTPUT | dict(
            effect_estimates=[dict(reported="invented effect", passage="Example abstract.")]))))
    response = client.post("/api/claims/articles/123/assess", json={"claim": "test"})
    assert response.status_code == 200
    assert response.json()["effect_estimates"] == []
    assert response.json()["measurement_warnings"]
