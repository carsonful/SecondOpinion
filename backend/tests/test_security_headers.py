"""Check browser policies on actual ASGI responses and CORS preflights."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.config import Settings


@pytest.mark.parametrize("origin", [
    "*", "https://*.example.com", "https://example.com/path",
    "https://user:password@example.com", "https://example.com:99999",
])
def test_cors_configuration_rejects_wildcards_and_non_origins(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(
        _env_file=None, database_url=None, cache_database_url=None,
        cors_origins=["http://localhost:5173"],
    ))
    return main.create_app()


@pytest.mark.parametrize("path,status", [
    ("/api/health", 200),
    ("/api/not-a-route", 404),
    ("/openapi.json", 200),
])
def test_api_responses_have_restrictive_browser_headers(api, path, status):
    response = TestClient(api).get(path)
    assert response.status_code == status
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_hsts_depends_on_server_scheme_not_untrusted_forwarding_header(api):
    client = TestClient(api)
    response = client.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert "Strict-Transport-Security" not in response.headers
    response = TestClient(api, base_url="https://testserver").get("/api/health")
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_validation_and_rate_limit_errors_keep_browser_headers(api):
    client = TestClient(api)
    response = client.post("/api/claims/normalize", json={})
    assert response.status_code == 422
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    api.state.inference_limiter.requests = 1
    api.state.inference_limiter._clients.clear()
    assert client.post("/api/claims/overview/missing").status_code == 410
    response = client.post("/api/claims/overview/missing")
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_unexpected_server_errors_keep_security_headers(api):
    @api.get("/api/test-unexpected-error")
    async def unexpected():
        raise RuntimeError("private exception details")

    response = TestClient(api, raise_server_exceptions=False).get("/api/test-unexpected-error")
    assert response.status_code == 500
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "private exception details" not in response.text


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_api_documentation_is_not_blocked_by_json_only_csp(api, path):
    response = TestClient(api).get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" not in response.headers


@pytest.mark.parametrize("method", ["GET", "POST", "OPTIONS"])
def test_local_frontend_preflight_still_works(api, method):
    response = TestClient(api).options("/api/claims", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.parametrize("overrides", [
    {"Origin": "https://untrusted.example"},
    {"Access-Control-Request-Method": "DELETE"},
    {"Access-Control-Request-Headers": "x-unexpected-header"},
])
def test_unapproved_origins_methods_and_headers_fail_preflight(api, overrides):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
        **overrides,
    }
    response = TestClient(api).options("/api/claims", headers=headers)
    assert response.status_code == 400
    assert response.headers["X-Content-Type-Options"] == "nosniff"
