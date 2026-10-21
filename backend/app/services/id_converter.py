"""Map PMIDs to PMCIDs and DOIs with the NCBI PMC ID Converter API.

Docs: https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/
"""

import asyncio
import json
import re
from dataclasses import dataclass

import httpx2 as httpx

from app.services.http_retry import Sleep, UpstreamError, request_with_retries
from app.services.rate_limiter import RateLimiter

IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
# The service accepts up to 200 IDs per request.
MAX_IDCONV_BATCH = 200


@dataclass(frozen=True)
class ArticleIds:
    pmid: str
    pmcid: str | None
    doi: str | None


async def convert_pmids(
    http: httpx.AsyncClient,
    pmids: list[str],
    *,
    limiter: RateLimiter,
    tool: str,
    email: str | None = None,
    api_key: str | None = None,
    sleep: Sleep = asyncio.sleep,
) -> dict[str, ArticleIds]:
    """Return IDs for each PMID the converter knows. Raises UpstreamError if a batch fails."""
    found: dict[str, ArticleIds] = {}
    for start in range(0, len(pmids), MAX_IDCONV_BATCH):
        batch = pmids[start : start + MAX_IDCONV_BATCH]
        params = {"ids": ",".join(batch), "idtype": "pmid", "format": "json", "tool": tool}
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        # NCBI has moved PMC tools between hosts before; follow its redirect.
        response = await request_with_retries(
            http, "GET", IDCONV_URL, service="NCBI ID Converter", limiter=limiter,
            params=params, follow_redirects=True, sleep=sleep,
        )
        found.update(parse_idconv(response.content))
    return found


def parse_idconv(content: bytes) -> dict[str, ArticleIds]:
    try:
        records = json.loads(content)["records"]
        if not isinstance(records, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise UpstreamError("NCBI ID Converter returned an unexpected response") from None

    found = {}
    for record in records:
        if not isinstance(record, dict) or record.get("status") == "error" or not record.get("pmid"):
            continue
        pmid = str(record["pmid"])
        pmcid = record.get("pmcid")
        found[pmid] = ArticleIds(
            pmid=pmid,
            pmcid=pmcid if isinstance(pmcid, str) and re.fullmatch(r"PMC\d+", pmcid) else None,
            doi=record.get("doi") or None,
        )
    return found
