from collections.abc import Callable, Iterator

import httpx2 as httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.models.normalization import NormalizedClaim
from app.routers.claims import get_claims_cache
from app.routers.crossref import get_crossref_client
from app.routers.pubmed import get_pubmed_client
from app.services import claims as claims_service
from app.services.cache import TTLCache
from app.services.claims import ClaimsCache
from app.services.crossref import CrossrefClient
from app.services.rate_limiter import RateLimiter
from tests.helpers import FakeClock, FakeNCBI, load_fixture, make_client

# The recorded zinc search returns three articles. Two have DOIs.
COCHRANE_DOI = "10.1002/14651858.cd014914.pub2"
AJTMH_DOI = "10.4269/ajtmh.19-0718"

NORMALIZED = NormalizedClaim(
    query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
    relation="cures", negated=False,
)


def crossref_client(handler: Callable[[httpx.Request], httpx.Response]) -> CrossrefClient:
    clock = FakeClock()
    return CrossrefClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        mailto="team@example.com",
        rate_limiter=RateLimiter(8, clock=clock, sleep=clock.sleep),
        sleep=clock.sleep,
    )


def cochrane_ok_others_down(request: httpx.Request) -> httpx.Response:
    if "14651858" in request.url.raw_path.decode():
        return httpx.Response(200, content=load_fixture("crossref/work_cochrane_clean.json"))
    return httpx.Response(503)


def all_ok(request: httpx.Request) -> httpx.Response:
    if "14651858" in request.url.raw_path.decode():
        return httpx.Response(200, content=load_fixture("crossref/work_cochrane_clean.json"))
    return httpx.Response(404, text="Resource not found.")


class Calls:
    """Counts calls to each external service during a test."""

    def __init__(self) -> None:
        self.normalize = 0
        self.ncbi = FakeNCBI(FakeClock())
        self.crossref = 0

    @property
    def pubmed(self) -> int:
        return len(self.ncbi.requests)

    @property
    def external(self) -> int:
        return self.normalize + self.pubmed + self.crossref


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

    def build(crossref_handler: Callable[[httpx.Request], httpx.Response] = all_ok) -> TestClient:
        def counted(request: httpx.Request) -> httpx.Response:
            calls.crossref += 1
            return crossref_handler(request)

        app.dependency_overrides[get_pubmed_client] = lambda: make_client(calls.ncbi)
        app.dependency_overrides[get_crossref_client] = lambda: crossref_client(counted)
        app.dependency_overrides[get_claims_cache] = lambda: cache
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def statuses(response) -> dict[str, str]:
    return {c["article"]["pmid"]: c["integrity"]["status"] for c in response.json()["candidates"]}


def test_crossref_outage_still_returns_candidates_marked_unchecked(api) -> None:
    response = api(lambda _: httpx.Response(503)).post(
        "/api/claims", json={"claim": "does zinc cure colds", "limit": 3}
    )

    assert response.status_code == 200
    assert statuses(response) == {
        "38719213": "unchecked",
        "31478634": "unchecked",
        "32342851": "unchecked",
    }


def test_one_failed_lookup_only_affects_that_study(api) -> None:
    response = api(cochrane_ok_others_down).post(
        "/api/claims", json={"claim": "does zinc cure colds", "limit": 3}
    )

    assert response.status_code == 200
    assert statuses(response) == {
        "38719213": "no_notice_found",  # Cochrane review, Crossref answered
        "31478634": "unchecked",  # no DOI
        "32342851": "unchecked",  # Crossref failed for this DOI
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


def test_results_with_a_failed_crossref_lookup_are_not_cached(api, calls: Calls) -> None:
    client = api(cochrane_ok_others_down)
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
            cache_database_url="postgresql://localhost/same_db",
            database_url="postgresql://localhost/same_db",
        ))


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
