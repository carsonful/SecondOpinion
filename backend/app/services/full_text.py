"""Resolve ranked PubMed studies to normalized full-text records.

Tiers, per study, each falling through to the next on failure:
1. PMCID (NCBI ID Converter, else EFetch's own ID): Europe PMC JATS, else NCBI BioC.
2. DOI: Unpaywall's best open-access PDF, parsed by a PdfParser.
3. The PubMed abstract.

No PMC OA web service, FTP packages, or publisher web pages are used.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Sequence

import httpx2 as httpx

from app.config import Settings
from app.models.full_text import FullTextRecord, Section, SourceTier
from app.models.pubmed import PubMedArticle
from app.services.document_download import Download, download_document
from app.services.http_retry import Sleep, UpstreamError, request_with_retries
from app.services.id_converter import ArticleIds, convert_pmids
from app.services.jats_parser import FullTextParseError, parse_bioc, parse_jats
from app.services.pdf_parsing import DocumentIntelligenceParser, PdfParser
from app.services.rate_limiter import RateLimiter
from app.services.record_cache import LocalRecordCache, RecordCache
from app.services.study_documents import FullTextUnavailable
from app.services.unpaywall import find_oa_pdf

logger = logging.getLogger(__name__)

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
BIOC_URL = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json"
# Europe PMC and Unpaywall publish no hard per-second limit; stay polite.
EUROPE_PMC_RATE = 5.0
UNPAYWALL_RATE = 5.0
# Below this much non-abstract text, a "full text" is really front matter or an access page.
MIN_BODY_CHARACTERS = 1000


class FullTextRetriever:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        cache: RecordCache,
        ncbi_limiter: RateLimiter,
        ncbi_tool: str = "SecondOpinion",
        ncbi_email: str | None = None,
        ncbi_api_key: str | None = None,
        unpaywall_email: str | None = None,
        pdf_parser: PdfParser | None = None,
        concurrency: int = 4,
        study_timeout: float = 45.0,
        min_body_characters: int = MIN_BODY_CHARACTERS,
        download: Callable[[str], Awaitable[Download]] = download_document,
        europe_pmc_limiter: RateLimiter | None = None,
        unpaywall_limiter: RateLimiter | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = http
        self._cache = cache
        self._ncbi_limiter = ncbi_limiter
        self._ncbi_tool = ncbi_tool
        self._ncbi_email = ncbi_email
        self._ncbi_api_key = ncbi_api_key
        self._unpaywall_email = unpaywall_email
        self._pdf_parser = pdf_parser
        self._concurrency = concurrency
        self._study_timeout = study_timeout
        self._min_body = min_body_characters
        self._download = download
        self._europe_pmc_limiter = europe_pmc_limiter or RateLimiter(EUROPE_PMC_RATE)
        self._unpaywall_limiter = unpaywall_limiter or RateLimiter(UNPAYWALL_RATE)
        self._sleep = sleep

    @classmethod
    def from_settings(
        cls, settings: Settings, http: httpx.AsyncClient, ncbi_limiter: RateLimiter,
    ) -> "FullTextRetriever":
        return cls(
            http,
            cache=LocalRecordCache(settings.full_text_cache_dir),
            ncbi_limiter=ncbi_limiter,
            ncbi_tool=settings.ncbi_tool,
            ncbi_email=settings.ncbi_email,
            ncbi_api_key=settings.ncbi_api_key,
            unpaywall_email=settings.unpaywall_email or settings.ncbi_email,
            pdf_parser=DocumentIntelligenceParser.from_settings(settings, http),
            concurrency=settings.full_text_concurrency,
            study_timeout=settings.full_text_study_timeout,
        )

    async def retrieve(self, articles: Sequence[PubMedArticle]) -> list[FullTextRecord]:
        """Return one record per article, in the same order. Never raises for one study."""
        records: list[FullTextRecord | None] = list(
            await asyncio.gather(*(self._cached(article.pmid) for article in articles))
        )
        missing = [article for article, record in zip(articles, records) if record is None]
        if not missing:
            return records  # type: ignore[return-value]

        try:
            converted = await convert_pmids(
                self._http, [a.pmid for a in missing], limiter=self._ncbi_limiter, tool=self._ncbi_tool,
                email=self._ncbi_email, api_key=self._ncbi_api_key, sleep=self._sleep,
            )
        except UpstreamError as exc:
            # PubMed's own record usually carries the PMCID and DOI too.
            logger.warning("ID Converter unavailable, using PubMed IDs: %s", exc)
            converted = {}

        semaphore = asyncio.Semaphore(self._concurrency)

        async def resolve(article: PubMedArticle) -> FullTextRecord:
            async with semaphore:
                return await self._resolve(article, converted.get(article.pmid))

        resolved = iter(await asyncio.gather(*(resolve(article) for article in missing)))
        return [record if record is not None else next(resolved) for record in records]

    async def retrieve_one(self, article: PubMedArticle) -> FullTextRecord:
        return (await self.retrieve([article]))[0]

    async def cached(self, pmids: Sequence[str]) -> list[FullTextRecord]:
        """Records already in the cache, without fetching anything."""
        found = await asyncio.gather(*(self._cached(pmid) for pmid in pmids))
        return [record for record in found if record is not None]

    async def _cached(self, pmid: str) -> FullTextRecord | None:
        try:
            return await self._cache.get(pmid)
        except (OSError, ValueError):
            logger.warning("Full-text cache read failed: pmid=%s", pmid)
            return None

    async def _resolve(self, article: PubMedArticle, ids: ArticleIds | None) -> FullTextRecord:
        pmcid = (ids.pmcid if ids else None) or _valid_pmcid(article.pmc_id)
        doi = (ids.doi if ids else None) or article.doi
        try:
            async with asyncio.timeout(self._study_timeout):
                record, detail, cacheable = await self._tiers(article, pmcid, doi)
        except TimeoutError:
            record, detail, cacheable = abstract_record(article, pmcid, doi), "timed out", False
        except Exception:
            # One study must never fail the batch, whatever went wrong.
            logger.exception("Full-text retrieval failed unexpectedly: pmid=%s", article.pmid)
            record, detail, cacheable = abstract_record(article, pmcid, doi), "unexpected error", False

        logger.info("full_text_tier pmid=%s tier=%s detail=%s", article.pmid, record.source_tier, detail)
        if cacheable:
            try:
                await self._cache.put(record)
            except (OSError, ValueError):
                logger.warning("Full-text cache write failed: pmid=%s", article.pmid)
        return record

    async def _tiers(
        self, article: PubMedArticle, pmcid: str | None, doi: str | None,
    ) -> tuple[FullTextRecord, str, bool]:
        """Returns (record, what happened, whether the outcome is worth caching)."""
        notes: list[str] = []
        # Outages and missing configuration may clear up; don't cache their fallback.
        transient = False

        if pmcid:
            for source, fetch in (("europe_pmc", self._europe_pmc), ("bioc", self._bioc)):
                try:
                    sections, license_id = await fetch(pmcid)
                    sections = _require_body(_with_abstract(sections, article), self._min_body)
                    record = _record(article, pmcid, doi, "pmc_fulltext", license_id, sections)
                    return record, source, True
                except UpstreamError as exc:
                    transient = transient or exc.status_code != 404
                    notes.append(f"{source}: {exc}")
                except FullTextParseError as exc:
                    notes.append(f"{source}: {exc}")
        else:
            notes.append("no PMCID")

        if not doi:
            notes.append("no DOI")
        elif not self._unpaywall_email:
            notes.append("Unpaywall email not configured")
            transient = True
        elif self._pdf_parser is None:
            notes.append("Document Intelligence not configured")
            transient = True
        else:
            try:
                location = await find_oa_pdf(
                    self._http, doi, self._unpaywall_email, limiter=self._unpaywall_limiter, sleep=self._sleep,
                )
                if location is None:
                    notes.append("no open-access PDF")
                else:
                    download = await self._download(location.url)
                    if not download.content.startswith(b"%PDF-"):
                        raise FullTextUnavailable("Open-access link was not a PDF")
                    parsed = await self._pdf_parser.parse(download.content)
                    sections = _require_body(_with_abstract(parsed, article), self._min_body)
                    return _record(article, pmcid, doi, "oa_pdf", location.license, sections), "unpaywall", True
            except UpstreamError as exc:
                transient = True
                notes.append(f"pdf: {exc}")
            except (FullTextUnavailable, FullTextParseError) as exc:
                notes.append(f"pdf: {exc}")

        return abstract_record(article, pmcid, doi), "; ".join(notes), not transient

    async def _europe_pmc(self, pmcid: str) -> tuple[list[Section], str | None]:
        response = await request_with_retries(
            self._http, "GET", f"{EUROPE_PMC_URL}/{pmcid}/fullTextXML", service="Europe PMC",
            limiter=self._europe_pmc_limiter, sleep=self._sleep,
        )
        return parse_jats(response.content)

    async def _bioc(self, pmcid: str) -> tuple[list[Section], str | None]:
        response = await request_with_retries(
            self._http, "GET", f"{BIOC_URL}/{pmcid}/unicode", service="NCBI BioC",
            limiter=self._ncbi_limiter, sleep=self._sleep,
        )
        return parse_bioc(response.content)


def abstract_record(article: PubMedArticle, pmcid: str | None = None, doi: str | None = None) -> FullTextRecord:
    """The last tier: PubMed's abstract as the only section (none if PubMed has no abstract)."""
    return _record(article, pmcid, doi or article.doi, "abstract_only", None, _abstract_sections(article))


def _abstract_sections(article: PubMedArticle) -> list[Section]:
    text = (article.abstract or "").strip()
    return [Section(type="abstract", heading="Abstract", text=text)] if text else []


def _with_abstract(sections: list[Section], article: PubMedArticle) -> list[Section]:
    # The abstract is the highest-priority section, so borrow PubMed's when the source lacks one.
    if any(s.type == "abstract" for s in sections):
        return sections
    return _abstract_sections(article) + sections


def _require_body(sections: list[Section], minimum: int) -> list[Section]:
    if sum(len(s.text) for s in sections if s.type != "abstract") < minimum:
        raise FullTextParseError("too little article text beyond the abstract")
    return sections


def _record(
    article: PubMedArticle, pmcid: str | None, doi: str | None, tier: SourceTier,
    license_id: str | None, sections: list[Section],
) -> FullTextRecord:
    return FullTextRecord(
        pmid=article.pmid, pmcid=pmcid, doi=doi, title=article.title, year=article.year,
        journal=article.journal, publication_types=article.publication_types,
        source_tier=tier, license=license_id, sections=sections,
    )


def _valid_pmcid(value: str | None) -> str | None:
    return value if value and re.fullmatch(r"PMC\d+", value) else None
