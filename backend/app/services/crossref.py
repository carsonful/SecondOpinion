"""Client for the Crossref REST API, used to find retractions, corrections, and
expressions of concern published against a paper.

Crossref merges publisher-deposited notices with the Retraction Watch database and
lists both in a work's `updated-by` field. Docs: https://api.crossref.org/swagger-ui/
"""

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx2 as httpx

from app import __version__
from app.config import Settings
from app.models.crossref import IntegrityNotice, IntegrityReport, NoticeCategory
from app.services.rate_limiter import RateLimiter
from app.services.upstream import (
    UpstreamError,
    UpstreamResponseError,
    UpstreamUnavailableError,
    get_with_retries,
)

CROSSREF_BASE_URL = "https://api.crossref.org"

# Crossref's polite pool (requests that include a contact email) allows 10 requests/second
# and 3 concurrent; the public pool allows 5/second and 1 at a time. We stay a little under.
RATE_POLITE = 8.0
RATE_PUBLIC = 4.0
CONCURRENCY_POLITE = 3
CONCURRENCY_PUBLIC = 1

_NOTICE_CATEGORIES: dict[str, NoticeCategory] = {
    "retraction": "retraction",
    # A partial retraction still retracts findings, and we cannot tell which ones,
    # so it is treated as a retraction. Grading can inspect crossref_type to refine this.
    "partial_retraction": "retraction",
    "withdrawal": "retraction",
    "removal": "retraction",
    "correction": "correction",
    "corrigendum": "correction",
    "erratum": "correction",
    "expression_of_concern": "expression_of_concern",
}

_DOI_PREFIXES = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


class InvalidDoiError(ValueError):
    """The input does not look like a DOI."""


class CrossrefError(UpstreamError):
    """Base class for Crossref client failures."""

    service = "Crossref"


class CrossrefUnavailableError(CrossrefError, UpstreamUnavailableError):
    """Crossref could not be reached, or kept failing after retries."""


class CrossrefResponseError(CrossrefError, UpstreamResponseError):
    """Crossref answered, but with something we could not use."""


def normalize_doi(value: str) -> str:
    """Strip URL/"doi:" prefixes and lowercase, since DOIs are case-insensitive."""
    doi = _DOI_PREFIXES.sub("", value.strip()).strip().lower()
    if not _DOI_PATTERN.match(doi):
        raise InvalidDoiError(f"Not a valid DOI: {value!r}")
    return doi


class CrossrefClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        mailto: str | None = None,
        rate_limiter: RateLimiter | None = None,
        max_concurrency: int | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http = http_client
        self._mailto = mailto
        self._limiter = rate_limiter or RateLimiter(RATE_POLITE if mailto else RATE_PUBLIC)
        self._concurrency = asyncio.Semaphore(
            max_concurrency or (CONCURRENCY_POLITE if mailto else CONCURRENCY_PUBLIC)
        )
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings, http_client: httpx.AsyncClient) -> "CrossrefClient":
        return cls(http_client, mailto=settings.crossref_mailto)

    async def check(self, doi: str) -> IntegrityReport:
        """Look up integrity notices for one DOI."""
        doi = normalize_doi(doi)
        async with self._concurrency:
            response = await get_with_retries(
                self._http,
                f"{CROSSREF_BASE_URL}/works/{quote(doi, safe='')}",
                params={"mailto": self._mailto} if self._mailto else None,
                headers={"User-Agent": self._user_agent()},
                limiter=self._limiter,
                sleep=self._sleep,
                unavailable_error=CrossrefUnavailableError,
            )

        if response.status_code == 404:
            return IntegrityReport(
                doi=doi, found=False, retracted=None, has_expression_of_concern=None,
                has_correction=None, notices=[],
            )
        if response.is_error:
            raise CrossrefResponseError(f"Crossref returned HTTP {response.status_code} for {doi}")

        try:
            work = response.json()["message"]
            updated_by = work.get("updated-by", [])
        except (ValueError, KeyError, AttributeError) as exc:
            raise CrossrefResponseError("Crossref returned an unexpected response") from exc
        return build_report(doi, updated_by)

    async def check_many(self, dois: Iterable[str]) -> dict[str, IntegrityReport]:
        """Check several DOIs concurrently, within Crossref's limits. Keyed by normalized DOI."""
        unique = list(dict.fromkeys(normalize_doi(d) for d in dois))
        reports = await asyncio.gather(*(self.check(doi) for doi in unique))
        return dict(zip(unique, reports))

    def _user_agent(self) -> str:
        contact = f" (mailto:{self._mailto})" if self._mailto else ""
        return f"SecondOpinion/{__version__}{contact}"


def build_report(doi: str, updated_by: list[dict[str, Any]]) -> IntegrityReport:
    """Turn a work's `updated-by` entries into a report.

    Only `updated-by` is used. Some publishers deposit `update-to` on the retracted paper
    itself (pointing at its own notices), so reading `update-to` would misclassify papers.
    """
    merged: dict[tuple[NoticeCategory, str], IntegrityNotice] = {}
    for entry in updated_by:
        crossref_type = str(entry.get("type", "")).lower()
        category = _NOTICE_CATEGORIES.get(crossref_type, "other")
        notice_doi = str(entry["DOI"]).lower() if entry.get("DOI") else None
        source = entry.get("source")

        # Publishers and Retraction Watch often report the same notice; merge them.
        key = (category, notice_doi or f"{crossref_type}:{len(merged)}")
        if key in merged:
            if source and source not in merged[key].sources:
                merged[key].sources.append(source)
                merged[key].sources.sort()
            continue

        merged[key] = IntegrityNotice(
            category=category,
            crossref_type=crossref_type,
            label=entry.get("label"),
            notice_doi=notice_doi,
            notice_url=f"https://doi.org/{notice_doi}" if notice_doi else None,
            published_on=_parse_date(entry.get("updated")),
            sources=[source] if source else [],
        )

    notices = sorted(merged.values(), key=lambda n: (n.published_on or date.max, n.category))
    categories = {n.category for n in notices}
    return IntegrityReport(
        doi=doi,
        found=True,
        retracted="retraction" in categories,
        has_expression_of_concern="expression_of_concern" in categories,
        has_correction="correction" in categories,
        notices=notices,
    )


def _parse_date(value: Any) -> date | None:
    try:
        parts = value["date-parts"][0]
        return date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    except (TypeError, KeyError, IndexError, ValueError):
        return None
