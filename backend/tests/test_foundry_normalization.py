import json
import logging

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.foundry_normalization import FoundryUnavailableError, normalize_claim
from app.services.normalization import ClaimNormalizationError


EXTRACTED = dict(is_health_claim=True, intervention="zinc", outcome="common cold",
                 population=None, relation="cure", negated=False)


def settings(**overrides):
    return Settings(_env_file=None, **{
        "azure_foundry_endpoint": "https://example.services.ai.azure.com",
        "azure_foundry_deployment": "test-deployment",
        "azure_foundry_api_key": "test-secret", **overrides,
    })


def response(data=None, **choice_fields):
    return {"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps(EXTRACTED if data is None else data),
    }, **choice_fields}]}


def test_foundry_request_and_normalized_output(caplog):
    def handler(request):
        assert str(request.url) == "https://example.services.ai.azure.com/openai/v1/chat/completions"
        assert request.headers["api-key"] == "test-secret"
        body = json.loads(request.content)
        assert body["model"] == "test-deployment"
        assert body["messages"][1] == {"role": "user", "content": "does zinc cure colds lol"}
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False
        return httpx.Response(200, json=response())

    with caplog.at_level(logging.INFO):
        result = normalize_claim("does zinc cure colds lol", settings=settings(),
                                 transport=httpx.MockTransport(handler))
    assert result.query == '"zinc" AND "common cold"'
    assert result.version == "foundry-v1"
    assert result.population is None
    record = next(r for r in caplog.records if r.msg == "claim_normalization")
    assert record.normalized_output == result.model_dump()
    assert "test-secret" not in caplog.text


def test_negation_and_population():
    data = {**EXTRACTED, "negated": True, "population": "children"}
    result = normalize_claim("Zinc does not cure colds in children", settings=settings(),
                             transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response(data))))
    assert result.negated
    assert result.query == '"zinc" AND "common cold" AND "children"'


@pytest.mark.parametrize("body", [
    {}, {"choices": []}, response(finish_reason="length"),
    response(message={"refusal": "refused"}),
    response(message={"content": "invalid JSON"}),
    response({**EXTRACTED, "verdict": "supported"}),
    response({**EXTRACTED, "intervention": None}),
    response({**EXTRACTED, "outcome": 'colds OR cancer'}),
])
def test_invalid_provider_outputs(body):
    with pytest.raises(FoundryUnavailableError):
        normalize_claim("zinc cures colds", settings=settings(),
                        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_errors_are_sanitized(status):
    with pytest.raises(FoundryUnavailableError, match="Azure Foundry request failed"):
        normalize_claim("zinc cures colds", settings=settings(),
                        transport=httpx.MockTransport(lambda _: httpx.Response(status, text="private details")))


def test_rejection_is_logged(caplog):
    data = dict.fromkeys(EXTRACTED)
    data.update(is_health_claim=False, negated=False)
    with caplog.at_level(logging.INFO), pytest.raises(ClaimNormalizationError):
        normalize_claim("Who won the game?", settings=settings(),
                        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response(data))))
    record = next(r for r in caplog.records if r.msg == "claim_normalization")
    assert record.normalized_output is None
    assert record.error


def test_missing_configuration():
    with pytest.raises(FoundryUnavailableError, match="required"):
        normalize_claim("zinc cures colds", settings=settings(azure_foundry_api_key=None))


def test_timeout():
    def handler(request):
        raise httpx.ReadTimeout("private details", request=request)
    with pytest.raises(FoundryUnavailableError):
        normalize_claim("zinc cures colds", settings=settings(), transport=httpx.MockTransport(handler))


def test_route(monkeypatch):
    from app.routers import normalization
    def stub(raw):
        return normalize_claim(raw, settings=settings(), transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=response())))
    monkeypatch.setattr(normalization, "normalize_claim", stub)
    client = TestClient(app)
    result = client.post("/api/claims/normalize", json={"raw_text": "does zinc cure colds lol"})
    assert result.status_code == 200
    assert result.json()["version"] == "foundry-v1"
    assert client.post("/api/claims/normalize", json={"raw_text": ""}).status_code == 422


@pytest.mark.parametrize("error,status", [(ClaimNormalizationError("invalid"), 422),
                                         (FoundryUnavailableError("unavailable"), 503)])
def test_route_errors(monkeypatch, error, status):
    from app.routers import normalization
    def fail(raw):
        raise error
    monkeypatch.setattr(normalization, "normalize_claim", fail)
    assert TestClient(app).post("/api/claims/normalize", json={"raw_text": "hello"}).status_code == status
