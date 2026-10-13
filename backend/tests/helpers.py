import json
from collections.abc import Callable
from pathlib import Path

import httpx2 as httpx

from app.services.pubmed import PubMedClient
from app.services.rate_limiter import RateLimiter

FIXTURES = Path(__file__).parent / "fixtures"

EMPTY_EFETCH = b"<PubmedArticleSet></PubmedArticleSet>"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeClock:
    """Stands in for time.monotonic and asyncio.sleep so timing tests run instantly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeNCBI:
    """A stand-in for eutils.ncbi.nlm.nih.gov that serves recorded responses.

    Set `limit_per_second` to enforce NCBI's throttling rule against the fake clock:
    any request that would make more than that many in a trailing one-second window
    gets a 429, just like the real service.
    """

    def __init__(self, clock: FakeClock, limit_per_second: int | None = None) -> None:
        self.clock = clock
        self.limit_per_second = limit_per_second
        self.requests: list[httpx.Request] = []
        self.request_times: list[float] = []
        self.throttled = 0
        self.esearch: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, content=load_fixture("pubmed/esearch_zinc_cold.json")
        )
        self.efetch: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, content=load_fixture("pubmed/efetch_zinc_cold.xml")
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        now = self.clock.now
        self.requests.append(request)
        self.request_times.append(now)

        if self.limit_per_second is not None:
            recent = [t for t in self.request_times if now - t < 1.0]
            if len(recent) > self.limit_per_second:
                self.throttled += 1
                return httpx.Response(429, json={"error": "API rate limit exceeded"})

        if request.url.path.endswith("/esearch.fcgi"):
            return self.esearch(request)
        if request.url.path.endswith("/efetch.fcgi"):
            return self.efetch(request)
        return httpx.Response(404)

    def calls_to(self, endpoint: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path.endswith(endpoint)]


def esearch_response(ids: list[str], count: int | None = None) -> httpx.Response:
    body = {"esearchresult": {"count": str(len(ids) if count is None else count), "idlist": ids}}
    return httpx.Response(200, content=json.dumps(body).encode())


def make_client(
    ncbi: FakeNCBI, rate_per_second: float = 2.5, api_key: str | None = None
) -> PubMedClient:
    clock = ncbi.clock
    return PubMedClient(
        httpx.AsyncClient(transport=httpx.MockTransport(ncbi.handler)),
        api_key=api_key,
        email="team@example.com",
        rate_limiter=RateLimiter(rate_per_second, clock=clock, sleep=clock.sleep),
        sleep=clock.sleep,
    )
