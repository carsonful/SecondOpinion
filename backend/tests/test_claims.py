from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedSearchResponse
from app.routers import claims
from app.routers.pubmed import get_pubmed_client
from app.services.normalization import ClaimNormalizationError, FoundryUnavailableError
from app.services.pubmed import PubMedResponseError, PubMedUnavailableError
from tests.helpers import FakeClock, FakeNCBI, make_client


@pytest.fixture
def setup(monkeypatch):
    normalized = NormalizedClaim(
        query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
        relation="cures", negated=False,
    )
    seen = []

    def normalize(raw):
        seen.append(raw)
        return normalized

    monkeypatch.setattr(claims, "normalize_claim", normalize)
    client = make_client(FakeNCBI(FakeClock()))
    app.dependency_overrides[get_pubmed_client] = lambda: client
    try:
        yield TestClient(app), client, seen
    finally:
        app.dependency_overrides.clear()


def test_claim_retrieves_real_fixture_records(setup):
    api, client, seen = setup
    original_search = client.search
    client.search = AsyncMock(wraps=original_search)
    response = api.post("/api/claims", json={"claim": "  zinc cures colds  "})
    assert response.status_code == 200
    body = response.json()
    assert seen == ["zinc cures colds"]
    client.search.assert_awaited_once_with("(zinc) AND (common cold)", 20)
    assert body["claim"] == "zinc cures colds"
    assert body["assessment_status"] == "pending"
    assert body["evidence"]["articles"][0]["pmid"] == "38719213"
    assert [item["pmid"] for item in body["assessments"]] == [
        item["pmid"] for item in body["evidence"]["articles"]
    ]
    assert body["assessments"][0]["category"] == "Research synthesis"
    assert body["assessments"][0]["base_weight"] is None
    assert "verdict" not in body
    assert "confidence" not in body


def test_empty_results_are_success(setup):
    api, client, _ = setup
    client.search = AsyncMock(return_value=PubMedSearchResponse(
        query="(zinc) AND (common cold)", query_translation=None, total_results=0, articles=[],
    ))
    response = api.post("/api/claims", json={"claim": "zinc cures colds"})
    assert response.status_code == 200
    assert response.json()["evidence"]["articles"] == []
    assert response.json()["assessments"] == []


@pytest.mark.parametrize("payload", [{}, {"claim": ""}, {"claim": "x" * 2001}])
def test_invalid_request_skips_normalization(setup, payload):
    api, _, seen = setup
    assert api.post("/api/claims", json=payload).status_code == 422
    assert seen == []


@pytest.mark.parametrize("error,status", [
    (ClaimNormalizationError("Enter one clear health-effect claim"), 422),
    (FoundryUnavailableError("private provider details"), 503),
])
def test_normalization_errors_skip_retrieval(setup, monkeypatch, error, status):
    api, client, _ = setup
    client.search = AsyncMock()

    def fail(raw):
        raise error

    monkeypatch.setattr(claims, "normalize_claim", fail)
    response = api.post("/api/claims", json={"claim": "some claim"})
    assert response.status_code == status
    assert "private provider details" not in response.text
    client.search.assert_not_awaited()


def test_whitespace_rejected_by_normalizer(setup, monkeypatch):
    from app.services.normalization import normalize_claim
    api, client, _ = setup
    monkeypatch.setattr(claims, "normalize_claim", normalize_claim)
    client.search = AsyncMock()
    assert api.post("/api/claims", json={"claim": "   "}).status_code == 422
    client.search.assert_not_awaited()


@pytest.mark.parametrize("error,status", [
    (PubMedUnavailableError("unavailable"), 503),
    (PubMedResponseError("invalid response"), 502),
])
def test_pubmed_errors(setup, error, status):
    api, client, _ = setup
    client.search = AsyncMock(side_effect=error)
    assert api.post("/api/claims", json={"claim": "zinc cures colds"}).status_code == status


def test_empty_search_broadens_intervention_and_preserves_claim(setup):
    api, client, _ = setup
    client.search = AsyncMock(side_effect=[
        PubMedSearchResponse(query="(zinc) AND (common cold)", query_translation=None, total_results=0, articles=[]),
        PubMedSearchResponse(query="(zinc)", query_translation=None, total_results=5, articles=[]),
    ])
    response = api.post("/api/claims", json={"claim": "zinc cures colds"})
    assert response.status_code == 200
    body = response.json()
    assert body["search_scope"] == "intervention_only"
    assert body["normalized"]["query"] == "(zinc) AND (common cold)"
    assert body["evidence"]["query"] == "(zinc)"
    assert body["claim"] == "zinc cures colds"
    assert client.search.await_args_list[1].args == ("(zinc)", 20)


def test_broader_search_outage_is_not_an_empty_success(setup):
    api, client, _ = setup
    client.search = AsyncMock(side_effect=[
        PubMedSearchResponse(query="q", query_translation=None, total_results=0, articles=[]),
        PubMedUnavailableError("offline"),
    ])
    assert api.post("/api/claims", json={"claim": "zinc cures colds"}).status_code == 503
