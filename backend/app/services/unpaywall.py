"""Find a legal open-access PDF for a DOI with Unpaywall.

Docs: https://unpaywall.org/products/api
"""

import asyncio
import json
from dataclasses import dataclass
from urllib.parse import quote

import httpx2 as httpx

from app.services.http_retry import Sleep, UpstreamError, request_with_retries
from app.services.jats_parser import normalize_license
from app.services.rate_limiter import RateLimiter

UNPAYWALL_URL = "https://api.unpaywall.org/v2"


@dataclass(frozen=True)
class OaPdf:
    url: str
    license: str | None


def doi_value(value: str) -> str:
    return value.removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip().casefold()


async def find_oa_pdf(
    http: httpx.AsyncClient,
    doi: str,
    email: str,
    *,
    limiter: RateLimiter | None = None,
    sleep: Sleep = asyncio.sleep,
) -> OaPdf | None:
    """Return best_oa_location.url_for_pdf, or None when Unpaywall has no PDF for the DOI."""
    try:
        response = await request_with_retries(
            http, "GET", f"{UNPAYWALL_URL}/{quote(doi, safe='/')}", service="Unpaywall",
            limiter=limiter, sleep=sleep, params={"email": email},
        )
    except UpstreamError as exc:
        if exc.status_code == 404:  # Unpaywall does not know this DOI.
            return None
        raise
    return parse_unpaywall(response.content, doi)


def parse_unpaywall(content: bytes, doi: str) -> OaPdf | None:
    try:
        work = json.loads(content)
        if doi_value(work.get("doi") or "") != doi_value(doi):
            raise ValueError("DOI mismatch")
        location = work.get("best_oa_location")
    except (ValueError, AttributeError):
        raise UpstreamError("Unpaywall returned an unexpected response") from None
    if not isinstance(location, dict):
        return None
    url = location.get("url_for_pdf")
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    return OaPdf(url=url, license=normalize_license(location.get("license")))
