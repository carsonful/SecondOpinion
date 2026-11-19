"""PMC full-text retrieval against recorded BioC responses.

The fixtures in tests/fixtures/pmc are real BioC replies with passage text shortened.
Each one is a case seen in live claim searches. bioc_unprefixed_id.json is not openly
licensed, so its text is replaced with placeholders; only its IDs and structure matter.
"""

import json

import httpx2 as httpx
import pytest

from app.models.pubmed import PubMedArticle
from app.services.pmc import PMCClient, parse_bioc
from app.services.rate_limiter import RateLimiter
from tests.helpers import FakeClock, load_fixture


def article(pmid: str, pmc_id: str) -> PubMedArticle:
    return PubMedArticle(
        pmid=pmid, title="Study", abstract="An abstract.", journal=None, year=None,
        authors=[], doi=None, pmc_id=pmc_id, publication_types=[], mesh_terms=[],
        retracted=False, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    )


def bioc(name: str):
    return json.loads(load_fixture(f"pmc/{name}"))


def client(handler) -> tuple[PMCClient, FakeClock]:
    clock = FakeClock()
    pmc = PMCClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        RateLimiter(100, clock=clock, sleep=clock.sleep),
        sleep=clock.sleep,
    )
    return pmc, clock


def serve(name: str):
    return lambda request: httpx.Response(200, content=load_fixture(f"pmc/{name}"))


# --- Parsing and identity checks ------------------------------------------------------

def test_normal_document_is_parsed() -> None:
    document = parse_bioc(bioc("bioc_ok.json"), "PMC7356429", "32342851")

    assert document.pmid == "32342851"
    assert document.sections


def test_document_without_a_pmid_is_accepted_when_its_pmc_id_matches() -> None:
    document = parse_bioc(bioc("bioc_missing_pmid.json"), "PMC8844493", "35177991")

    assert document.pmid == "35177991"
    assert document.sections


def test_document_id_without_the_pmc_prefix_is_accepted() -> None:
    document = parse_bioc(bioc("bioc_unprefixed_id.json"), "PMC6768751", "30986133")

    assert document.sections


def test_unknown_document_id_is_accepted_when_its_pmid_matches() -> None:
    document = parse_bioc(bioc("bioc_unknown_id.json"), "PMC7341710", "32641681")

    assert document.sections


def test_unknown_document_id_with_another_studys_pmid_is_rejected() -> None:
    with pytest.raises(ValueError, match="PubMed identifier mismatch"):
        parse_bioc(bioc("bioc_unknown_id.json"), "PMC7341710", "11111111")


def test_document_with_a_different_pmid_is_rejected() -> None:
    with pytest.raises(ValueError, match="PubMed identifier mismatch"):
        parse_bioc(bioc("bioc_unprefixed_id.json"), "PMC6768751", "11111111")


def test_document_for_a_different_pmc_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="No matching PMC document"):
        parse_bioc(bioc("bioc_missing_pmid.json"), "PMC1234567", "35177991")


def test_unknown_document_with_no_ids_at_all_is_rejected() -> None:
    data = bioc("bioc_unknown_id.json")
    for document in data[0]["documents"]:
        for passage in document["passages"]:
            passage["infons"].pop("article-id_pmid", None)

    with pytest.raises(ValueError, match="identity could not be confirmed"):
        parse_bioc(data, "PMC7341710", "32641681")


def test_unknown_document_id_is_not_guessed_among_several_documents() -> None:
    data = bioc("bioc_unknown_id.json")
    data[0]["documents"].append(data[0]["documents"][0])

    with pytest.raises(ValueError, match="No matching PMC document"):
        parse_bioc(data, "PMC7341710", "32641681")


def test_references_only_document_has_no_full_text() -> None:
    with pytest.raises(ValueError, match="No full-text body passages"):
        parse_bioc(bioc("bioc_references_only.json"), "PMC7709583", "33154234")


# --- Retrieval outcomes ----------------------------------------------------------------

@pytest.mark.anyio
async def test_no_result_reply_means_not_available() -> None:
    pmc, _ = client(serve("bioc_no_result.txt"))

    result = await pmc.retrieve(article("38719213", "PMC11078591"))

    assert result.access.reason == "not_available"
    assert result.access.level == "abstract_only"


@pytest.mark.anyio
async def test_previously_rejected_documents_are_now_retrieved() -> None:
    pmc, _ = client(serve("bioc_missing_pmid.json"))

    result = await pmc.retrieve(article("35177991", "PMC8844493"))

    assert result.access.reason == "retrieved"
    assert result.access.level == "full_text"


@pytest.mark.anyio
async def test_references_only_document_is_parse_failed() -> None:
    pmc, _ = client(serve("bioc_references_only.json"))

    result = await pmc.retrieve(article("33154234", "PMC7709583"))

    assert result.access.reason == "parse_failed"


@pytest.mark.anyio
async def test_rate_limited_requests_back_off_and_retry() -> None:
    replies = iter([429, 429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(replies)
        if status == 429:
            return httpx.Response(429)
        return httpx.Response(200, content=load_fixture("pmc/bioc_ok.json"))

    pmc, clock = client(handler)

    result = await pmc.retrieve(article("32342851", "PMC7356429"))

    assert result.access.reason == "retrieved"
    assert clock.sleeps.count(1.0) >= 1 and 2.0 in clock.sleeps


@pytest.mark.anyio
async def test_retry_after_header_is_respected_up_to_a_cap() -> None:
    replies = iter([httpx.Response(429, headers={"Retry-After": "3"}),
                    httpx.Response(429, headers={"Retry-After": "120"}),
                    httpx.Response(200, content=load_fixture("pmc/bioc_ok.json"))])
    pmc, clock = client(lambda request: next(replies))

    result = await pmc.retrieve(article("32342851", "PMC7356429"))

    assert result.access.reason == "retrieved"
    assert 3.0 in clock.sleeps and 8.0 in clock.sleeps


@pytest.mark.anyio
async def test_persistent_rate_limiting_is_request_failed() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    pmc, _ = client(handler)

    result = await pmc.retrieve(article("32342851", "PMC7356429"))

    assert result.access.reason == "request_failed"
    assert calls == 4
