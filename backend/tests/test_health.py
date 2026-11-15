import asyncio
import os
import time

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import __version__
from app.config import Settings
from app.main import app
from app.routers import health
from app.services import examples

client = TestClient(app)

UNREACHABLE_URL = "postgresql://user:hunter2@127.0.0.1:1/examples"


@pytest.fixture
def settings(monkeypatch):
    """Health reads settings fresh, so each test can describe its own deployment."""
    def use(**values) -> None:
        configured = Settings(_env_file=None, **values)
        monkeypatch.setattr(health, "get_settings", lambda: configured)

    use()
    monkeypatch.setattr(app.state.claims_cache, "persistent", None)
    return use


def dependencies() -> dict[str, str]:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    return response.json()["dependencies"]


def test_health_returns_status_and_version(settings) -> None:
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_nothing_configured_is_still_ok(settings) -> None:
    assert dependencies() == {
        "azure": "not_configured",
        "examples_db": "not_configured",
        "claim_cache": "not_configured",
    }


# --- Azure ----------------------------------------------------------------------------

def test_azure_is_configured_only_when_all_three_settings_are_set(settings) -> None:
    settings(azure_inference_endpoint="https://example.test", azure_model_deployment_name="model")
    assert dependencies()["azure"] == "not_configured"

    settings(
        azure_inference_endpoint="https://example.test",
        azure_model_deployment_name="model",
        azure_inference_api_key="secret-key",
    )
    assert dependencies()["azure"] == "configured"


def test_health_never_calls_azure(settings, monkeypatch) -> None:
    def no_azure(*args, **kwargs):
        raise AssertionError("health must not call Azure")

    monkeypatch.setattr("app.services.normalization._request_extraction", no_azure)
    settings(
        azure_inference_endpoint="https://example.test",
        azure_model_deployment_name="model",
        azure_inference_api_key="secret-key",
    )

    assert dependencies()["azure"] == "configured"


# --- Examples database ----------------------------------------------------------------

def test_examples_db_reachable(settings, monkeypatch) -> None:
    async def reachable(database_url, timeout=2):
        return True

    monkeypatch.setattr(examples, "examples_database_reachable", reachable)
    settings(database_url="postgresql://user:pass@db.example.test/examples")

    assert dependencies()["examples_db"] == "reachable"


def test_examples_db_unreachable(settings) -> None:
    settings(database_url=UNREACHABLE_URL)

    assert dependencies()["examples_db"] == "unreachable"


def test_examples_db_check_gives_up_quickly(monkeypatch) -> None:
    def hang(*args, **kwargs):
        time.sleep(3)

    monkeypatch.setattr(psycopg, "connect", hang)

    async def timed_check() -> tuple[bool, float]:
        started = time.monotonic()
        reachable = await examples.examples_database_reachable(SecretStr(UNREACHABLE_URL), timeout=0.1)
        return reachable, time.monotonic() - started

    # Timed inside the loop: asyncio.run also waits for the stuck thread on shutdown.
    reachable, elapsed = asyncio.run(timed_check())

    assert reachable is False
    assert elapsed < 1


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requires PostgreSQL test database")
def test_examples_db_reachable_against_postgres(settings) -> None:
    settings(database_url=os.environ["TEST_DATABASE_URL"])

    assert dependencies()["examples_db"] == "reachable"


# --- Claim cache ----------------------------------------------------------------------

def test_claim_cache_active(settings, monkeypatch) -> None:
    settings(cache_database_url="postgresql://user:pass@db.example.test/cache")
    monkeypatch.setattr(app.state.claims_cache, "persistent", object())

    assert dependencies()["claim_cache"] == "active"


def test_claim_cache_disabled_after_a_failure(settings) -> None:
    # The cache sets persistent to None when PostgreSQL fails.
    settings(cache_database_url="postgresql://user:pass@db.example.test/cache")

    assert dependencies()["claim_cache"] == "disabled"


# --- Privacy --------------------------------------------------------------------------

def test_health_does_not_leak_secrets_or_hosts(settings, monkeypatch) -> None:
    async def unreachable(database_url, timeout=2):
        return False

    monkeypatch.setattr(examples, "examples_database_reachable", unreachable)
    settings(
        azure_inference_endpoint="https://my-foundry.example.test",
        azure_model_deployment_name="model",
        azure_inference_api_key="secret-key",
        database_url=UNREACHABLE_URL,
        cache_database_url="postgresql://cacheuser:cachepass@cache.example.test/cache",
    )

    text = client.get("/api/health").text

    for secret in ("secret-key", "hunter2", "cachepass", "127.0.0.1", "example.test", "postgresql"):
        assert secret not in text
