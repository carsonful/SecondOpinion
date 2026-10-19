import asyncio

import httpx2 as httpx
import pytest

from app.services.pubmed import (
    MAX_RETRIES,
    RATE_WITHOUT_KEY,
    PubMedResponseError,
    PubMedUnavailableError,
)
from tests.helpers import (
    EMPTY_EFETCH,
    FakeClock,
    FakeNCBI,
    esearch_response,
    load_fixture,
    make_client,
)


@pytest.mark.anyio
async def test_search_returns_structured_articles() -> None:
    ncbi = FakeNCBI(FakeClock())

    result = await make_client(ncbi).search("zinc common cold", limit=3)

    assert result.query == "zinc common cold"
    assert result.total_results == 278
    assert result.query_translation is not None
    assert [a.pmid for a in result.articles] == ["38719213", "31478634", "32342851"]
    assert result.articles[0].title == "Zinc for prevention and treatment of the common cold."


@pytest.mark.anyio
async def test_search_keeps_pubmed_relevance_order() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.esearch = lambda _: esearch_response(["32342851", "38719213", "31478634"])

    result = await make_client(ncbi).search("zinc common cold")

    assert [a.pmid for a in result.articles] == ["32342851", "38719213", "31478634"]


@pytest.mark.anyio
async def test_search_sends_identification_and_paging_params() -> None:
    ncbi = FakeNCBI(FakeClock())

    await make_client(ncbi, api_key="secret-key").search("zinc common cold", limit=3)

    params = ncbi.calls_to("esearch.fcgi")[0].url.params
    assert params["term"] == "zinc common cold"
    assert params["retmax"] == "3"
    assert params["tool"] == "SecondOpinion"
    assert params["email"] == "team@example.com"
    assert params["api_key"] == "secret-key"
    assert ncbi.calls_to("efetch.fcgi")[0].url.params["id"] == "38719213,31478634,32342851"


@pytest.mark.anyio
async def test_search_with_no_matches_skips_efetch() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.esearch = lambda _: httpx.Response(
        200, content=load_fixture("pubmed/esearch_no_results.json")
    )

    result = await make_client(ncbi).search("qwzxv flurbnog zzqq")

    assert result.total_results == 0
    assert result.articles == []
    assert ncbi.calls_to("efetch.fcgi") == []


@pytest.mark.anyio
async def test_get_article_returns_none_for_unknown_pmid() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.efetch = lambda _: httpx.Response(200, content=EMPTY_EFETCH)

    assert await make_client(ncbi).get_article("999999999") is None


@pytest.mark.anyio
async def test_retries_after_throttling_and_honors_retry_after() -> None:
    clock = FakeClock()
    ncbi = FakeNCBI(clock)
    responses = iter([httpx.Response(429, headers={"Retry-After": "2"}), esearch_response(["1"])])
    ncbi.esearch = lambda _: next(responses)

    ids, _, _ = await make_client(ncbi).search_ids("zinc")

    assert ids == ["1"]
    assert len(ncbi.calls_to("esearch.fcgi")) == 2
    assert 2.0 in clock.sleeps


@pytest.mark.anyio
async def test_retries_server_errors_with_backoff() -> None:
    clock = FakeClock()
    ncbi = FakeNCBI(clock)
    responses = iter([httpx.Response(502), httpx.Response(503), esearch_response(["1"])])
    ncbi.esearch = lambda _: next(responses)

    ids, _, _ = await make_client(ncbi).search_ids("zinc")

    assert ids == ["1"]
    assert 0.5 in clock.sleeps
    assert 1.0 in clock.sleeps


@pytest.mark.anyio
async def test_gives_up_after_max_retries() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.esearch = lambda _: httpx.Response(503)

    with pytest.raises(PubMedUnavailableError):
        await make_client(ncbi).search("zinc")

    assert len(ncbi.calls_to("esearch.fcgi")) == MAX_RETRIES + 1


@pytest.mark.anyio
async def test_network_failures_are_retried_then_reported() -> None:
    ncbi = FakeNCBI(FakeClock())

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    ncbi.esearch = fail

    with pytest.raises(PubMedUnavailableError):
        await make_client(ncbi).search("zinc")

    assert len(ncbi.calls_to("esearch.fcgi")) == MAX_RETRIES + 1


@pytest.mark.anyio
async def test_client_errors_are_not_retried() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.esearch = lambda _: httpx.Response(400)

    with pytest.raises(PubMedResponseError):
        await make_client(ncbi).search("zinc")

    assert len(ncbi.calls_to("esearch.fcgi")) == 1


@pytest.mark.anyio
async def test_query_errors_reported_by_esearch_raise() -> None:
    ncbi = FakeNCBI(FakeClock())
    ncbi.esearch = lambda _: httpx.Response(
        200, json={"esearchresult": {"ERROR": "Invalid query syntax"}}
    )

    with pytest.raises(PubMedResponseError, match="Invalid query syntax"):
        await make_client(ncbi).search("zinc[[[")


@pytest.mark.anyio
async def test_fifty_back_to_back_searches_are_never_throttled() -> None:
    """Done-when for #9: hammering the client 50 times produces no throttling errors.

    The fake NCBI enforces the real 3 requests/second limit, and the searches run
    concurrently to mimic several people using the demo at once.
    """
    ncbi = FakeNCBI(FakeClock(), limit_per_second=3)
    client = make_client(ncbi, rate_per_second=RATE_WITHOUT_KEY)

    results = await asyncio.gather(*(client.search("zinc common cold", limit=3) for _ in range(50)))

    assert all(len(r.articles) == 3 for r in results)
    assert len(ncbi.requests) == 100
    assert ncbi.throttled == 0
