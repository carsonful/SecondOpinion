import asyncio
import os
from collections.abc import Callable, Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import cache_admin
from app.main import app
from app.config import Settings
from app.models.full_text import RetrievalResult
from app.models.normalization import NormalizedClaim
from app.models.pubmed import PubMedArticle
from app.routers.claims import get_claims_cache, get_pmc_client
from app.routers.pubmed import get_pubmed_client
from app.services import claims as claims_service
from app.services.cache import TTLCache
from app.services.claims import ClaimsCache
from app.services.durable_cache import PostgresClaimsCache
from app.services.pmc import unavailable
from tests.helpers import FakeClock, FakeNCBI, make_client

NORMALIZED = NormalizedClaim(
    query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
    relation="cures", negated=False,
)


def pmc_available(article: PubMedArticle) -> RetrievalResult:
    return unavailable(article, "not_available", "No PMC text in this test fixture")


class Calls:
    """Counts calls to each external service during a test."""

    def __init__(self) -> None:
        self.normalize = 0
        self.ncbi = FakeNCBI(FakeClock())
        self.pmc = 0

    @property
    def pubmed(self) -> int:
        return len(self.ncbi.requests)

    @property
    def external(self) -> int:
        return self.normalize + self.pubmed + self.pmc


@pytest.fixture
def calls() -> Calls:
    return Calls()


@pytest.fixture
def cache() -> ClaimsCache:
    return ClaimsCache(TTLCache(3600, 64), TTLCache(3600, 64))


@pytest.fixture
def api(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, cache: ClaimsCache
) -> Iterator[Callable[..., TestClient]]:
    def fake_normalize(claim: str) -> NormalizedClaim:
        calls.normalize += 1
        return NORMALIZED

    monkeypatch.setattr(claims_service, "normalize_claim", fake_normalize)

    def build(pmc_handler: Callable[[PubMedArticle], RetrievalResult] = pmc_available) -> TestClient:
        class CountedPMC:
            async def retrieve(self, article: PubMedArticle, *, refresh: bool = False) -> RetrievalResult:
                calls.pmc += 1
                return pmc_handler(article)

        app.dependency_overrides[get_pubmed_client] = lambda: make_client(calls.ncbi)
        app.dependency_overrides[get_pmc_client] = lambda: CountedPMC()
        app.dependency_overrides[get_claims_cache] = lambda: cache
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def access_reasons(response) -> dict[str, str]:
    return {c["article"]["pmid"]: c["access"]["reason"] for c in response.json()["candidates"]}


def test_pmc_outage_still_returns_candidates_with_access_failure(api) -> None:
    response = api(lambda article: unavailable(article, "request_failed", "PMC unavailable")).post(
        "/api/claims", json={"claim": "does zinc cure colds", "limit": 3}
    )

    assert response.status_code == 200
    assert access_reasons(response) == {
        "38719213": "request_failed",
        "31478634": "request_failed",
        "32342851": "request_failed",
    }


def test_one_failed_pmc_lookup_only_affects_that_study(api) -> None:
    def mixed_access(article: PubMedArticle) -> RetrievalResult:
        if article.pmid == "38719213":
            return pmc_available(article)
        return unavailable(article, "request_failed", "PMC unavailable")

    response = api(mixed_access).post(
        "/api/claims", json={"claim": "does zinc cure colds", "limit": 3}
    )

    assert response.status_code == 200
    assert access_reasons(response) == {
        "38719213": "not_available",
        "31478634": "request_failed",
        "32342851": "request_failed",
    }


# --- Caching (#15) ----------------------------------------------------------------

ZINC = {"claim": "does zinc cure colds", "limit": 3}


def test_repeat_claim_makes_no_external_calls(api, calls: Calls) -> None:
    client = api()
    first = client.post("/api/claims", json=ZINC)
    calls_after_first = calls.external

    second = client.post("/api/claims", json=ZINC)

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls_after_first > 0
    assert calls.external == calls_after_first
    assert second.json()["candidates"] == first.json()["candidates"]


def test_case_and_spacing_do_not_matter_for_a_repeat(api, calls: Calls) -> None:
    client = api()
    client.post("/api/claims", json=ZINC)

    response = client.post("/api/claims", json={"claim": "  Does   ZINC cure colds ", "limit": 3})

    assert response.json()["cached"] is True
    assert calls.normalize == 1


def test_different_wording_with_the_same_query_shares_results(api, calls: Calls) -> None:
    client = api()
    client.post("/api/claims", json=ZINC)
    pubmed_calls = calls.pubmed

    response = client.post("/api/claims", json={"claim": "zinc cures the common cold", "limit": 3})

    body = response.json()
    assert body["cached"] is True
    assert body["claim"] == "zinc cures the common cold"
    assert calls.normalize == 2  # new wording still has to be normalized once
    assert calls.pubmed == pubmed_calls


def test_refresh_skips_the_cache(api, calls: Calls) -> None:
    client = api()
    client.post("/api/claims", json=ZINC)
    calls_after_first = calls.external

    response = client.post("/api/claims", params={"refresh": "true"}, json=ZINC)

    assert response.json()["cached"] is False
    assert calls.normalize == 2
    assert calls.external > calls_after_first


def test_different_limits_are_cached_separately(api, calls: Calls) -> None:
    client = api()
    client.post("/api/claims", json=ZINC)

    response = client.post("/api/claims", json={**ZINC, "limit": 2})

    assert response.json()["cached"] is False


def test_results_with_a_failed_pmc_lookup_are_not_cached(api, calls: Calls) -> None:
    client = api(lambda article: unavailable(article, "request_failed", "PMC unavailable"))
    client.post("/api/claims", json=ZINC)
    pubmed_calls = calls.pubmed

    response = client.post("/api/claims", json=ZINC)

    assert response.json()["cached"] is False
    assert calls.pubmed > pubmed_calls


def test_cache_can_be_turned_off(api, calls: Calls, cache: ClaimsCache) -> None:
    cache.normalized.ttl_seconds = cache.results.ttl_seconds = 0
    client = api()
    client.post("/api/claims", json=ZINC)

    response = client.post("/api/claims", json=ZINC)

    assert response.json()["cached"] is False
    assert calls.normalize == 2


def test_persistent_cache_is_opt_in_and_uses_a_separate_database() -> None:
    assert ClaimsCache.from_settings(Settings(_env_file=None)).persistent is None

    configured = Settings(
        _env_file=None,
        cache_database_url="postgresql://localhost/cache_test",
        database_url="postgresql://localhost/examples_test",
    )
    assert ClaimsCache.from_settings(configured).persistent is not None

    with pytest.raises(ValueError, match="separate database"):
        ClaimsCache.from_settings(Settings(
            _env_file=None,
            cache_database_url="postgresql://cache_user:secret@localhost/same_db",
            database_url="postgresql://examples_user:secret@localhost/same_db",
        ))

    disabled = Settings(
        _env_file=None,
        cache_database_url="postgresql://localhost/cache_test",
        claims_cache_ttl_seconds=0,
    )
    assert ClaimsCache.from_settings(disabled).persistent is None


def test_cache_database_failure_falls_back_to_live_retrieval(api, calls: Calls, cache: ClaimsCache):
    class FailingStore:
        async def get_normalized(self, _key):
            raise psycopg.OperationalError("cache database unavailable")

    cache.persistent = FailingStore()
    response = api().post("/api/claims", json=ZINC)

    assert response.status_code == 200
    assert response.json()["cached"] is False
    assert calls.external > 0
    assert cache.persistent is None


@pytest.mark.skipif(not os.getenv("TEST_CACHE_DATABASE_URL"), reason="requires test PostgreSQL")
def test_manual_postgres_entry_survives_new_cache_and_skips_external_calls(
    api, calls: Calls, cache: ClaimsCache, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    url = os.environ["TEST_CACHE_DATABASE_URL"]
    store = PostgresClaimsCache(SecretStr(url), ttl_seconds=3600)
    asyncio.run(store.initialize())
    with psycopg.connect(url) as connection:
        connection.execute("TRUNCATE claim_cache_entries")

    client = api()
    live = client.post("/api/claims", json=ZINC)
    assert live.status_code == 200
    assert live.json()["cached"] is False
    assert calls.external > 0

    payload = tmp_path / "result.json"
    payload.write_text(live.text, encoding="utf-8")
    monkeypatch.setattr(cache_admin, "get_settings", lambda: Settings(
        _env_file=None, cache_database_url=url,
        database_url="postgresql://localhost/separate_examples_test",
    ))
    assert asyncio.run(cache_admin.run(["put", str(payload), "--limit", "3"])) == 0

    fresh = ClaimsCache(TTLCache(3600, 64), TTLCache(3600, 64), store)
    app.dependency_overrides[get_claims_cache] = lambda: fresh
    before = calls.external
    cached = client.post("/api/claims", json=ZINC)

    assert cached.status_code == 200
    assert cached.json()["cached"] is True
    assert cached.json()["candidates"] == live.json()["candidates"]
    assert calls.external == before

    refreshed = client.post("/api/claims", params={"refresh": "true"}, json=ZINC)
    assert refreshed.status_code == 200
    assert refreshed.json()["cached"] is False
    assert calls.external > before
