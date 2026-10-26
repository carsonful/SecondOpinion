from collections.abc import Callable, Iterator

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.normalization import NormalizedClaim
from app.routers.crossref import get_crossref_client
from app.routers.pubmed import get_pubmed_client
from app.services import claims as claims_service
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


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., TestClient]]:
    monkeypatch.setattr(claims_service, "normalize_claim", lambda claim: NORMALIZED)

    def build(crossref_handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
        app.dependency_overrides[get_pubmed_client] = lambda: make_client(FakeNCBI(FakeClock()))
        app.dependency_overrides[get_crossref_client] = lambda: crossref_client(crossref_handler)
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
