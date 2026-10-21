import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx2 as httpx
import pytest

from app.models.full_text import FullTextRecord, Section
from app.services.document_download import Download
from app.services.full_text import FullTextRetriever, abstract_record
from app.services.http_retry import UpstreamError
from app.services.pdf_parsing import DocumentIntelligenceParser, sections_from_layout
from app.services.rate_limiter import RateLimiter
from app.services.record_cache import LocalRecordCache
from tests.helpers import FakeClock, load_fixture
from tests.test_assessment import article

PDF_URL = "https://publisher.example.org/articles/so.0002.pdf"
LAYOUT = json.loads(load_fixture("full_text/docintel_layout.json"))


def study(pmid="99000001", **overrides):
    values = dict(pmid=pmid, title=f"Study {pmid}", abstract=f"PubMed abstract for {pmid}.",
                  publication_types=["Randomized Controlled Trial"], journal="Journal of Example Nutrition", year=2024)
    return article(**(values | overrides))


class FakeSources:
    """Stands in for NCBI, Europe PMC and Unpaywall, serving the saved fixtures."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.idconv = lambda _: httpx.Response(200, content=load_fixture("full_text/idconv.json"))
        self.europe_pmc = lambda _: httpx.Response(200, content=load_fixture("full_text/europepmc_fulltext.xml"))
        self.bioc = lambda _: httpx.Response(200, content=load_fixture("full_text/bioc.json"))
        self.unpaywall = lambda _: httpx.Response(200, content=load_fixture("full_text/unpaywall.json"))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.startswith("/pmc/utils/idconv"):
            return self.idconv(request)
        if request.url.host == "www.ebi.ac.uk":
            return self.europe_pmc(request)
        if "/research/bionlp/" in request.url.path:
            return self.bioc(request)
        if request.url.host == "api.unpaywall.org":
            return self.unpaywall(request)
        return httpx.Response(404)

    def calls(self, name: str) -> list[httpx.Request]:
        match = {
            "idconv": lambda r: r.url.path.startswith("/pmc/utils/idconv"),
            "europe_pmc": lambda r: r.url.host == "www.ebi.ac.uk",
            "bioc": lambda r: "/research/bionlp/" in r.url.path,
            "unpaywall": lambda r: r.url.host == "api.unpaywall.org",
        }[name]
        return [r for r in self.requests if match(r)]


class FakePdfParser:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    async def parse(self, pdf: bytes):
        self.calls += 1
        if self.error:
            raise self.error
        return sections_from_layout(LAYOUT)


class MemoryCache:
    def __init__(self) -> None:
        self.records: dict[str, FullTextRecord] = {}

    async def get(self, pmid):
        return self.records.get(pmid)

    async def put(self, record):
        self.records[record.pmid] = record


async def pdf_download(url: str) -> Download:
    return Download(b"%PDF-1.7 fake", url, "application/pdf")


def make_retriever(sources, *, parser=None, download=pdf_download, cache=None, **options):
    clock = FakeClock()
    limiter = RateLimiter(100, clock=clock, sleep=clock.sleep)
    retriever = FullTextRetriever(
        httpx.AsyncClient(transport=httpx.MockTransport(sources.handler)),
        cache=cache if cache is not None else MemoryCache(),
        ncbi_limiter=limiter, europe_pmc_limiter=limiter, unpaywall_limiter=limiter,
        ncbi_email="team@example.com", unpaywall_email="team@example.com",
        pdf_parser=parser if parser is not None else FakePdfParser(),
        download=download, sleep=clock.sleep, min_body_characters=50, **options,
    )
    return retriever, clock


@pytest.mark.anyio
async def test_pmcid_resolves_to_europe_pmc_full_text():
    sources = FakeSources()
    retriever, _ = make_retriever(sources)

    [record] = await retriever.retrieve([study()])

    assert record.source_tier == "pmc_fulltext"
    assert record.pmcid == "PMC9900001"
    assert record.doi == "10.5555/so.0001"
    assert record.license == "cc-by"
    assert record.publication_types == ["Randomized Controlled Trial"]
    assert {"abstract", "methods", "results", "limitations"} <= {s.type for s in record.sections}
    assert sources.calls("europe_pmc")[0].url.path == "/europepmc/webservices/rest/PMC9900001/fullTextXML"
    assert sources.calls("bioc") == []
    assert sources.calls("unpaywall") == []


@pytest.mark.anyio
async def test_europe_pmc_outage_falls_back_to_bioc():
    sources = FakeSources()
    sources.europe_pmc = lambda _: httpx.Response(500)
    retriever, clock = make_retriever(sources)

    [record] = await retriever.retrieve([study()])

    assert record.source_tier == "pmc_fulltext"
    assert sources.calls("bioc")[0].url.path.endswith("/BioC_json/PMC9900001/unicode")
    assert len(sources.calls("europe_pmc")) == 4  # first try plus three retries
    assert [s for s in clock.sleeps if s >= 0.1] == [0.5, 1.0, 2.0]  # backoff, not rate spacing


@pytest.mark.anyio
async def test_retry_after_is_honored():
    sources = FakeSources()
    replies = iter([httpx.Response(429, headers={"Retry-After": "2"})])
    sources.europe_pmc = lambda _: next(replies, None) or httpx.Response(
        200, content=load_fixture("full_text/europepmc_fulltext.xml"))
    retriever, clock = make_retriever(sources)

    [record] = await retriever.retrieve([study()])

    assert record.source_tier == "pmc_fulltext"
    assert 2.0 in clock.sleeps


@pytest.mark.anyio
async def test_no_pmcid_with_doi_uses_unpaywall_pdf():
    sources = FakeSources()
    parser = FakePdfParser()
    downloads = []

    async def download(url):
        downloads.append(url)
        return await pdf_download(url)

    retriever, _ = make_retriever(sources, parser=parser, download=download)

    [record] = await retriever.retrieve([study("99000002")])

    assert record.source_tier == "oa_pdf"
    assert record.pmcid is None
    assert record.doi == "10.5555/so.0002"
    assert record.license == "cc-by-nc"
    assert downloads == [PDF_URL]
    assert parser.calls == 1
    assert sources.calls("unpaywall")[0].url.params["email"] == "team@example.com"
    assert sources.calls("europe_pmc") == []
    assert [s.type for s in record.sections] == [
        "other", "abstract", "introduction", "methods", "results", "discussion", "limitations",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("unpaywall", [
    lambda _: httpx.Response(404),
    lambda _: httpx.Response(200, json={"doi": "10.5555/so.0002", "best_oa_location": None}),
    lambda _: httpx.Response(200, json={"doi": "10.5555/so.0002", "best_oa_location": {"url_for_pdf": None}}),
])
async def test_no_open_access_pdf_falls_back_to_abstract(unpaywall):
    sources = FakeSources()
    sources.unpaywall = unpaywall
    cache = MemoryCache()
    retriever, _ = make_retriever(sources, cache=cache)

    [record] = await retriever.retrieve([study("99000002")])

    assert record.source_tier == "abstract_only"
    assert [(s.type, s.text) for s in record.sections] == [("abstract", "PubMed abstract for 99000002.")]
    # A definite "not open access" is cached; it expires after a week.
    assert cache.records["99000002"] == record


@pytest.mark.anyio
async def test_no_pmcid_or_doi_goes_straight_to_abstract():
    sources = FakeSources()
    retriever, _ = make_retriever(sources)

    [record] = await retriever.retrieve([study("99000003")])

    assert record.source_tier == "abstract_only"
    assert sources.calls("europe_pmc") == sources.calls("unpaywall") == []


@pytest.mark.anyio
async def test_pmc_without_a_body_tries_unpaywall_next():
    sources = FakeSources()
    sources.europe_pmc = lambda _: httpx.Response(404)
    sources.bioc = lambda _: httpx.Response(200, content=b"[No result can be found]")
    sources.unpaywall = lambda _: httpx.Response(200, json={
        "doi": "10.5555/so.0001", "best_oa_location": {"url_for_pdf": PDF_URL, "license": "cc-by"}})
    retriever, _ = make_retriever(sources)

    [record] = await retriever.retrieve([study()])

    assert record.source_tier == "oa_pdf"
    assert record.pmcid == "PMC9900001"


@pytest.mark.anyio
async def test_id_converter_outage_uses_pubmed_ids():
    sources = FakeSources()
    sources.idconv = lambda _: httpx.Response(503)
    retriever, _ = make_retriever(sources)

    [record] = await retriever.retrieve([study("99000009", pmc_id="PMC9900001")])

    assert record.source_tier == "pmc_fulltext"
    assert record.pmcid == "PMC9900001"


@pytest.mark.anyio
async def test_id_converter_is_one_batched_request():
    sources = FakeSources()
    retriever, _ = make_retriever(sources)

    await retriever.retrieve([study("99000001"), study("99000002"), study("99000003")])

    [request] = sources.calls("idconv")
    assert request.url.params["ids"] == "99000001,99000002,99000003"
    assert request.url.params["tool"] == "SecondOpinion"


@pytest.mark.anyio
async def test_one_failing_study_does_not_fail_the_batch(caplog):
    sources = FakeSources()
    retriever, _ = make_retriever(sources, parser=FakePdfParser(RuntimeError("parser bug")))

    with caplog.at_level(logging.INFO, logger="app.services.full_text"):
        records = await retriever.retrieve([study("99000001"), study("99000002"), study("99000003")])

    assert [(r.pmid, r.source_tier) for r in records] == [
        ("99000001", "pmc_fulltext"), ("99000002", "abstract_only"), ("99000003", "abstract_only"),
    ]
    assert "full_text_tier pmid=99000001 tier=pmc_fulltext detail=europe_pmc" in caplog.text
    assert "full_text_tier pmid=99000002 tier=abstract_only detail=unexpected error" in caplog.text
    assert "full_text_tier pmid=99000003 tier=abstract_only detail=no PMCID; no DOI" in caplog.text


@pytest.mark.anyio
async def test_slow_study_times_out_to_abstract_without_caching():
    async def slow_download(url):
        await asyncio.sleep(5)

    cache = MemoryCache()
    retriever, _ = make_retriever(FakeSources(), download=slow_download, cache=cache, study_timeout=0.05)

    [record] = await retriever.retrieve([study("99000002")])

    assert record.source_tier == "abstract_only"
    assert cache.records == {}


@pytest.mark.anyio
async def test_outages_and_missing_config_are_not_cached():
    sources = FakeSources()
    sources.europe_pmc = sources.bioc = lambda _: httpx.Response(503)
    cache = MemoryCache()
    retriever, _ = make_retriever(sources, cache=cache)
    retriever._pdf_parser = None

    records = await retriever.retrieve([study("99000001"), study("99000002")])

    assert [r.source_tier for r in records] == ["abstract_only", "abstract_only"]
    assert cache.records == {}


@pytest.mark.anyio
async def test_cached_records_are_not_fetched_again(tmp_path):
    sources = FakeSources()
    retriever, _ = make_retriever(sources, cache=LocalRecordCache(tmp_path))

    first = await retriever.retrieve([study()])
    count = len(sources.requests)
    second = await retriever.retrieve([study()])

    assert second == first
    assert len(sources.requests) == count
    assert await retriever.cached(["99000001", "99000002"]) == first


@pytest.mark.anyio
async def test_concurrency_is_bounded():
    active = peak = 0

    async def download(url):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return await pdf_download(url)

    sources = FakeSources()
    sources.idconv = lambda _: httpx.Response(200, json={"records": []})
    sources.unpaywall = lambda request: httpx.Response(200, json={
        "doi": request.url.path.removeprefix("/v2/"), "best_oa_location": {"url_for_pdf": PDF_URL}})
    retriever, _ = make_retriever(sources, download=download, concurrency=2)

    records = await retriever.retrieve([study(str(n), doi=f"10.5555/{n}") for n in range(6)])

    assert {r.source_tier for r in records} == {"oa_pdf"}
    assert peak == 2


@pytest.mark.anyio
async def test_record_cache_round_trip_and_expiry(tmp_path):
    cache = LocalRecordCache(tmp_path)
    record = abstract_record(study())
    await cache.put(record)
    assert await cache.get("99000001") == record

    entry = json.loads((tmp_path / "99000001.json").read_text())
    entry["cached_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    (tmp_path / "99000001.json").write_text(json.dumps(entry))
    assert await cache.get("99000001") is None

    full = record.model_copy(update={"source_tier": "pmc_fulltext"})
    entry["record"] = full.model_dump()
    (tmp_path / "99000001.json").write_text(json.dumps(entry))
    assert await cache.get("99000001") == full  # Full text does not expire.

    (tmp_path / "99000001.json").write_text("{broken")
    assert await cache.get("99000001") is None
    with pytest.raises(ValueError):
        await cache.get("../secrets")


@pytest.mark.anyio
async def test_document_intelligence_parser_polls_until_done():
    requests = []
    statuses = iter(["running", "succeeded"])
    operation = "https://example-di.cognitiveservices.azure.com/documentintelligence/documentModels/prebuilt-layout/analyzeResults/abc"

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, headers={"Operation-Location": operation})
        status = next(statuses)
        return httpx.Response(200, json=LAYOUT if status == "succeeded" else {"status": status})

    clock = FakeClock()
    parser = DocumentIntelligenceParser(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        "https://example-di.cognitiveservices.azure.com/", "secret-key", sleep=clock.sleep,
    )
    sections = await parser.parse(b"%PDF-1.7")

    post = requests[0]
    assert post.url.path == "/documentintelligence/documentModels/prebuilt-layout:analyze"
    assert post.url.params["api-version"] == "2024-11-30"
    assert post.headers["Ocp-Apim-Subscription-Key"] == "secret-key"
    assert post.headers["Content-Type"] == "application/pdf"
    assert len(requests) == 3
    by_type = {s.type: s for s in sections}
    assert by_type["methods"].heading == "2 Methods"
    assert by_type["limitations"].text == "Diet was self-reported and residual confounding is possible."
    text = "\n".join(s.text for s in sections)
    for excluded in ("Journal of Example Nutrition 2023", "© 2023 The Authors", "Earlier cohort study"):
        assert excluded not in text


@pytest.mark.anyio
@pytest.mark.parametrize("post,poll", [
    (httpx.Response(202, headers={"Operation-Location": "https://elsewhere.example.org/op"}), None),
    (httpx.Response(202), None),
    (httpx.Response(202, headers={"Operation-Location": "https://example-di.cognitiveservices.azure.com/op"}),
     httpx.Response(200, json={"status": "failed"})),
    (httpx.Response(401), None),
])
async def test_document_intelligence_failures_raise(post, poll):
    def handler(request):
        return post if request.method == "POST" else poll

    clock = FakeClock()
    parser = DocumentIntelligenceParser(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        "https://example-di.cognitiveservices.azure.com", "secret-key", sleep=clock.sleep,
    )
    with pytest.raises(UpstreamError) as error:
        await parser.parse(b"%PDF-1.7")
    assert "secret-key" not in str(error.value)


def test_layout_text_before_any_heading_is_other():
    sections = sections_from_layout({"analyzeResult": {"paragraphs": [
        {"content": "Author list"}, {"role": "sectionHeading", "content": "Results"}, {"content": "X."},
    ]}})
    assert sections == [Section(type="other", heading=None, text="Author list"),
                        Section(type="results", heading="Results", text="X.")]
