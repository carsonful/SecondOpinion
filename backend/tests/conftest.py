import pytest

from app.main import app
from app.routers.claims import get_full_text_retriever
from app.services.full_text import abstract_record


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class AbstractOnlyRetriever:
    """Stands in for FullTextRetriever in route tests: every study resolves to its abstract."""

    def __init__(self) -> None:
        self.records = {}

    async def retrieve(self, articles):
        return [await self.retrieve_one(article) for article in articles]

    async def retrieve_one(self, article):
        record = self.records.get(article.pmid) or abstract_record(article)
        self.records[article.pmid] = record
        return record

    async def cached(self, pmids):
        return [self.records[pmid] for pmid in pmids if pmid in self.records]


@pytest.fixture(autouse=True)
def full_text_retriever():
    # Route tests never reach the network; tests that care replace records directly.
    retriever = AbstractOnlyRetriever()
    app.dependency_overrides[get_full_text_retriever] = lambda: retriever
    yield retriever
    app.dependency_overrides.pop(get_full_text_retriever, None)
