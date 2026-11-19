"""Inbound controls must reject requests before any provider work starts."""

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.routers import claims, normalization
from app.routers.crossref import get_crossref_client
from app.routers.pubmed import get_pubmed_client
from app.services.inference_limits import InferenceLimiter
from app.services.normalization import ClaimNormalizationError, FoundryUnavailableError, normalize_claim


def test_token_bucket_refills_and_separates_clients():
    now = [0.0]
    limiter = InferenceLimiter(2, 60, 10, clock=lambda: now[0])
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") == 30
    assert limiter.retry_after("b") is None
    now[0] = 15
    assert limiter.retry_after("a") == 15
    now[0] = 30
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") == 30


def test_bucket_storage_is_bounded_without_resetting_active_clients():
    now = [0.0]
    limiter = InferenceLimiter(1, 60, 1, clock=lambda: now[0])
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("b") == 60
    assert limiter.retry_after("a") == 60
    now[0] = 60
    assert limiter.retry_after("b") is None
    assert len(limiter._clients) == 1


def test_concurrent_calls_cannot_overspend_bucket():
    limiter = InferenceLimiter(3, 60, 10, clock=lambda: 0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(limiter.retry_after, ["a"] * 20))
    assert results.count(None) == 3


@pytest.fixture
def limited_app(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(
        _env_file=None, inference_rate_limit_requests=1,
        inference_rate_limit_window_seconds=60,
        inference_rate_limit_enabled=True,
        database_url=None, cache_database_url=None,
    ))
    app = main.create_app()
    app.state.inference_limiter.clock = lambda: 0
    return app


@pytest.mark.parametrize("path,payload", [
    ("/api/claims", {"claim": "zinc cures colds"}),
    ("/api/claims/normalize", {"raw_text": "zinc cures colds"}),
    ("/api/claims/overview/unknown", None),
])
def test_all_model_routes_share_limit_and_do_not_trust_headers(limited_app, monkeypatch, path, payload):
    calls = []

    def fail(raw):
        calls.append(raw)
        raise FoundryUnavailableError("internal details")

    monkeypatch.setattr(normalization, "normalize_claim", fail)
    client = TestClient(limited_app)
    assert client.post("/api/claims/normalize", json={"raw_text": "first claim"}).status_code == 503
    response = client.post(path, json=payload, headers={
        "X-Forwarded-For": "203.0.113.2", "X-Real-IP": "203.0.113.3",
        "Origin": "http://localhost:5173",
    })
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Access-Control-Expose-Headers"] == "Retry-After"
    assert calls == ["first claim"]
    assert client.get("/api/health").status_code == 200
    preflight = client.options(path, headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
    })
    assert preflight.status_code == 200


def test_disabled_limit_allows_repeated_requests(limited_app, monkeypatch):
    limited_app.state.inference_limiter.enabled = False
    calls = []

    def fail(raw):
        calls.append(raw)
        raise FoundryUnavailableError("private")

    monkeypatch.setattr(normalization, "normalize_claim", fail)
    client = TestClient(limited_app)
    for _ in range(3):
        assert client.post("/api/claims/normalize", json={"raw_text": "claim"}).status_code == 503
    assert len(calls) == 3


@pytest.mark.parametrize("error,status,detail", [
    (FoundryUnavailableError("AZURE_INFERENCE_API_KEY https://private.example/secret"), 503,
     "Inference service unavailable. Try again shortly."),
    (ClaimNormalizationError("private provider detail"), 422, "Enter one clear health-effect claim"),
])
@pytest.mark.parametrize("path", ["/api/claims", "/api/claims/normalize"])
def test_provider_errors_never_escape_api(limited_app, monkeypatch, error, status, detail, path):
    def fail(*args, **kwargs):
        raise error

    async def fail_async(*args, **kwargs):
        raise error

    monkeypatch.setattr(normalization, "normalize_claim", fail)
    monkeypatch.setattr(claims, "retrieve_candidates", fail_async)
    limited_app.dependency_overrides[claims.get_pmc_client] = lambda: None
    limited_app.dependency_overrides[get_crossref_client] = lambda: None
    limited_app.dependency_overrides[get_pubmed_client] = lambda: None
    payload = {"claim": "private claim"} if path == "/api/claims" else {"raw_text": "private claim"}
    response = TestClient(limited_app).post(path, json=payload)
    assert response.status_code == status
    assert response.json() == {"detail": detail}


def test_unconfigured_normalization_logs_only_operational_fields(caplog):
    private_claim = "My private symptom and medication question"
    with caplog.at_level(logging.INFO), pytest.raises(FoundryUnavailableError):
        normalize_claim(private_claim, settings=Settings(_env_file=None))
    record = next(r for r in caplog.records if r.msg == "claim_normalization")
    assert record.success is False
    assert record.error_type == "FoundryUnavailableError"
    assert record.provider == "azure_foundry"
    assert private_claim not in str(record.__dict__)
    assert "AZURE_" not in str(record.__dict__)
