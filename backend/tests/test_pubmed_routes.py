from collections.abc import Iterator

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.pubmed import get_pubmed_client
from tests.helpers import EMPTY_EFETCH, FakeClock, FakeNCBI, make_client


@pytest.fixture
def ncbi() -> FakeNCBI:
    return FakeNCBI(FakeClock())


@pytest.fixture
def api(ncbi: FakeNCBI) -> Iterator[TestClient]:
    app.dependency_overrides[get_pubmed_client] = lambda: make_client(ncbi)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_returns_articles(api: TestClient) -> None:
    response = api.get("/api/pubmed/search", params={"q": "zinc common cold", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["total_results"] == 278
    assert [a["pmid"] for a in body["articles"]] == ["38719213", "31478634", "32342851"]
    assert body["articles"][0]["publication_types"] == [
        "Journal Article",
        "Research Support, Non-U.S. Gov't",
        "Systematic Review",
    ]


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "z"}, {"q": "zinc", "limit": 0}, {"q": "zinc", "limit": 101}],
)
def test_search_validates_input(api: TestClient, params: dict) -> None:
    assert api.get("/api/pubmed/search", params=params).status_code == 422


def test_get_article(api: TestClient) -> None:
    response = api.get("/api/pubmed/articles/38719213")

    assert response.status_code == 200
    assert response.json()["doi"] == "10.1002/14651858.CD014914.pub2"


def test_get_unknown_article_is_404(api: TestClient, ncbi: FakeNCBI) -> None:
    ncbi.efetch = lambda _: httpx.Response(200, content=EMPTY_EFETCH)

    assert api.get("/api/pubmed/articles/999999999").status_code == 404


def test_get_article_rejects_non_numeric_pmid(api: TestClient) -> None:
    assert api.get("/api/pubmed/articles/abc").status_code == 422


def test_pubmed_outage_is_503(api: TestClient, ncbi: FakeNCBI) -> None:
    ncbi.esearch = lambda _: httpx.Response(503)

    response = api.get("/api/pubmed/search", params={"q": "zinc"})

    assert response.status_code == 503
    assert response.json() == {"detail": "PubMed is unavailable, try again shortly"}


def test_unusable_pubmed_response_is_502(api: TestClient, ncbi: FakeNCBI) -> None:
    ncbi.efetch = lambda _: httpx.Response(200, content=b"<not-xml")

    assert api.get("/api/pubmed/search", params={"q": "zinc"}).status_code == 502
