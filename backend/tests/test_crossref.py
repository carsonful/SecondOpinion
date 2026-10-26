import asyncio
from collections.abc import Callable, Iterator
from datetime import date
from urllib.parse import unquote

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.crossref import get_crossref_client
from app.services.crossref import (
    CrossrefClient,
    CrossrefResponseError,
    CrossrefUnavailableError,
    InvalidDoiError,
    build_report,
    normalize_doi,
)
from app.services.rate_limiter import RateLimiter
from app.services.upstream import MAX_RETRIES
from tests.helpers import FakeClock, load_fixture

WAKEFIELD = "10.1016/s0140-6736(97)11096-0"
SURGISPHERE = "10.1016/s0140-6736(20)31180-6"
CONCERN_ONLY = "10.1016/j.lungcan.2003.10.006"
CORRECTION_ONLY = "10.1088/1361-6595/aaebdb"
CLEAN = "10.1002/14651858.cd014914.pub2"

FIXTURES = {
    WAKEFIELD: "work_wakefield_retracted.json",
    SURGISPHERE: "work_surgisphere_retracted.json",
    CONCERN_ONLY: "work_concern_only.json",
    CORRECTION_ONLY: "work_correction_only.json",
    CLEAN: "work_cochrane_clean.json",
}


def recorded_crossref(request: httpx.Request) -> httpx.Response:
    """Serves recorded /works/{doi} responses; unknown DOIs get Crossref's real 404."""
    doi = unquote(request.url.raw_path.decode().split("/works/", 1)[1].split("?")[0]).lower()
    if doi in FIXTURES:
        return httpx.Response(200, content=load_fixture(f"crossref/{FIXTURES[doi]}"))
    return httpx.Response(404, text="Resource not found.")


def make_client(
    handler: Callable[[httpx.Request], httpx.Response] = recorded_crossref,
    mailto: str | None = "team@example.com",
    max_concurrency: int | None = None,
) -> CrossrefClient:
    clock = FakeClock()
    return CrossrefClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        mailto=mailto,
        rate_limiter=RateLimiter(8, clock=clock, sleep=clock.sleep),
        max_concurrency=max_concurrency,
        sleep=clock.sleep,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "10.1016/S0140-6736(97)11096-0",
        "https://doi.org/10.1016/s0140-6736(97)11096-0",
        "http://dx.doi.org/10.1016/s0140-6736(97)11096-0",
        "doi:10.1016/s0140-6736(97)11096-0",
        "  10.1016/s0140-6736(97)11096-0  ",
    ],
)
def test_normalize_doi_accepts_common_forms(raw: str) -> None:
    assert normalize_doi(raw) == WAKEFIELD


@pytest.mark.parametrize("raw", ["", "not a doi", "10.1016", "11.1016/abc", "38719213"])
def test_normalize_doi_rejects_non_dois(raw: str) -> None:
    with pytest.raises(InvalidDoiError):
        normalize_doi(raw)


@pytest.mark.anyio
async def test_flags_wakefield_retraction_with_a_link_to_the_notice() -> None:
    report = await make_client().check(WAKEFIELD)

    assert report.found is True
    assert report.retracted is True
    assert report.has_correction is True
    assert report.has_expression_of_concern is False
    retraction = next(n for n in report.notices if n.category == "retraction")
    assert retraction.notice_doi == "10.1016/s0140-6736(10)60175-4"
    assert retraction.notice_url == "https://doi.org/10.1016/s0140-6736(10)60175-4"
    assert retraction.published_on == date(2010, 2, 6)
    assert retraction.sources == ["retraction-watch"]


@pytest.mark.anyio
async def test_flags_surgisphere_retraction_concern_and_corrections_separately() -> None:
    report = await make_client().check(SURGISPHERE)

    assert report.retracted is True
    assert report.has_expression_of_concern is True
    assert report.has_correction is True
    by_category = {c: [n for n in report.notices if n.category == c] for c in ("retraction", "correction")}
    assert {n.notice_doi for n in by_category["retraction"]} == {
        "10.1016/s0140-6736(20)31174-0",
        "10.1016/s0140-6736(20)31324-6",
    }
    assert all(n.crossref_type in ("correction", "erratum") for n in by_category["correction"])


@pytest.mark.anyio
async def test_merges_the_same_notice_reported_by_publisher_and_retraction_watch() -> None:
    report = await make_client().check(SURGISPHERE)

    # Retraction Watch calls this notice a "correction" and the publisher an "erratum".
    (notice,) = [n for n in report.notices if n.notice_doi == "10.1016/s0140-6736(20)31249-6"]
    assert notice.category == "correction"
    assert notice.sources == ["publisher", "retraction-watch"]
    assert len({(n.category, n.notice_doi) for n in report.notices}) == len(report.notices)


@pytest.mark.anyio
async def test_expression_of_concern_alone_does_not_mark_a_paper_retracted() -> None:
    report = await make_client().check(CONCERN_ONLY)

    assert report.retracted is False
    assert report.has_expression_of_concern is True
    assert report.has_correction is False
    # Crossref lists this notice twice; it should only appear once.
    (notice,) = report.notices
    assert notice.notice_url == "https://doi.org/10.1016/j.lungcan.2026.109332"


@pytest.mark.anyio
async def test_correction_alone_is_flagged_as_a_correction() -> None:
    report = await make_client().check(CORRECTION_ONLY)

    assert report.retracted is False
    assert report.has_correction is True
    assert report.notices[0].notice_url == "https://doi.org/10.1088/1361-6595/ab245f"


@pytest.mark.anyio
async def test_paper_without_notices_is_checked_not_verified() -> None:
    report = await make_client().check(CLEAN)

    assert report.found is True
    assert report.retracted is False
    assert report.has_expression_of_concern is False
    assert report.has_correction is False
    assert report.notices == []


@pytest.mark.anyio
async def test_unknown_doi_is_reported_as_unchecked() -> None:
    report = await make_client().check("10.9999/does-not-exist")

    assert report.found is False
    assert report.retracted is None
    assert report.has_expression_of_concern is None
    assert report.has_correction is None


def test_unrecognized_notice_types_are_kept_but_never_flag() -> None:
    report = build_report(CLEAN, [{"DOI": "10.1/addendum", "type": "addendum", "source": "publisher"}])

    assert report.retracted is False
    assert report.has_correction is False
    assert report.notices[0].category == "other"


def test_partial_retraction_counts_as_a_retraction() -> None:
    report = build_report(CLEAN, [{"DOI": "10.1/partial", "type": "partial_retraction"}])

    assert report.retracted is True
    assert report.notices[0].crossref_type == "partial_retraction"


@pytest.mark.anyio
async def test_request_encodes_the_doi_and_identifies_us() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return recorded_crossref(request)

    await make_client(handler).check(WAKEFIELD)

    (request,) = requests
    assert request.url.raw_path.decode().startswith("/works/10.1016%2Fs0140-6736%2897%2911096-0")
    assert request.url.params["mailto"] == "team@example.com"
    assert "mailto:team@example.com" in request.headers["User-Agent"]


@pytest.mark.anyio
async def test_retries_throttling_then_succeeds() -> None:
    responses = iter([httpx.Response(429, headers={"Retry-After": "1"})])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses, None) or recorded_crossref(request)

    report = await make_client(handler).check(WAKEFIELD)

    assert report.retracted is True


@pytest.mark.anyio
async def test_gives_up_when_crossref_stays_down() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(CrossrefUnavailableError):
        await make_client(handler).check(WAKEFIELD)
    assert len(calls) == MAX_RETRIES + 1


@pytest.mark.parametrize(
    "response",
    [httpx.Response(400), httpx.Response(200, content=b"not json"), httpx.Response(200, json={})],
)
@pytest.mark.anyio
async def test_unusable_responses_raise(response: httpx.Response) -> None:
    with pytest.raises(CrossrefResponseError):
        await make_client(lambda _: response).check(WAKEFIELD)


@pytest.mark.anyio
async def test_check_many_dedupes_and_respects_the_concurrency_limit() -> None:
    in_flight = 0
    peak = 0
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak, calls
        calls += 1
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return recorded_crossref(request)

    dois = [WAKEFIELD, SURGISPHERE, CONCERN_ONLY, CORRECTION_ONLY, CLEAN, WAKEFIELD.upper()]
    reports = await make_client(handler, max_concurrency=2).check_many(dois)

    assert calls == 5
    assert peak <= 2
    assert reports[WAKEFIELD].retracted is True
    assert reports[CLEAN].retracted is False


@pytest.mark.anyio
async def test_check_many_can_fail_the_whole_batch_when_asked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "31180" in request.url.raw_path.decode():
            return httpx.Response(503)
        return recorded_crossref(request)

    with pytest.raises(CrossrefUnavailableError):
        await make_client(handler).check_many([WAKEFIELD, SURGISPHERE, CLEAN], skip_failures=False)


@pytest.mark.anyio
async def test_check_many_skips_failed_lookups_by_default() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if "31180" in path:
            return httpx.Response(503)
        if "lungcan" in path:
            return httpx.Response(200, content=b"not json")
        return recorded_crossref(request)

    reports = await make_client(handler).check_many([WAKEFIELD, SURGISPHERE, CONCERN_ONLY, CLEAN])

    assert set(reports) == {WAKEFIELD, CLEAN}
    assert reports[WAKEFIELD].retracted is True


@pytest.mark.anyio
async def test_check_many_with_crossref_down_returns_no_reports() -> None:
    reports = await make_client(lambda _: httpx.Response(503)).check_many([WAKEFIELD, CLEAN])

    assert reports == {}


@pytest.fixture
def api() -> Iterator[Callable[[Callable[[httpx.Request], httpx.Response]], TestClient]]:
    def build(handler: Callable[[httpx.Request], httpx.Response] = recorded_crossref) -> TestClient:
        app.dependency_overrides[get_crossref_client] = lambda: make_client(handler)
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def test_notices_route_accepts_doi_urls(api) -> None:
    response = api().get("/api/crossref/notices", params={"doi": f"https://doi.org/{WAKEFIELD}"})

    assert response.status_code == 200
    body = response.json()
    assert body["doi"] == WAKEFIELD
    assert body["retracted"] is True
    assert body["notices"][0]["notice_url"].startswith("https://doi.org/")


def test_notices_route_rejects_invalid_dois(api) -> None:
    assert api().get("/api/crossref/notices", params={"doi": "zinc"}).status_code == 422
    assert api().get("/api/crossref/notices").status_code == 422


def test_crossref_outage_is_503(api) -> None:
    response = api(lambda _: httpx.Response(503)).get("/api/crossref/notices", params={"doi": WAKEFIELD})

    assert response.status_code == 503
    assert response.json() == {"detail": "Crossref is unavailable, try again shortly"}
