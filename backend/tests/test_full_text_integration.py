"""Live check against the real full-text services. Off by default.

Run with: RUN_INTEGRATION_TESTS=1 pytest -m integration
"""

import os

import httpx2 as httpx
import pytest

from app.services.full_text import FullTextRetriever
from app.services.rate_limiter import RateLimiter
from app.services.record_cache import LocalRecordCache
from tests.test_assessment import article

# Ioannidis, "Why most published research findings are false", PLoS Med 2005: CC BY, in PMC.
KNOWN_OPEN_ACCESS_PMID = os.environ.get("INTEGRATION_PMID", "16060722")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION_TESTS") != "1", reason="set RUN_INTEGRATION_TESTS=1"),
]


@pytest.mark.anyio
async def test_known_open_access_study_resolves_to_pmc_full_text(tmp_path):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as http:
        retriever = FullTextRetriever(
            http, cache=LocalRecordCache(tmp_path), ncbi_limiter=RateLimiter(2.5),
            ncbi_email=os.environ.get("NCBI_EMAIL"), ncbi_api_key=os.environ.get("NCBI_API_KEY"),
        )
        [record] = await retriever.retrieve([article(pmid=KNOWN_OPEN_ACCESS_PMID, title="Integration study")])

    assert record.source_tier == "pmc_fulltext"
    assert record.pmcid and record.pmcid.startswith("PMC")
    assert record.license and record.license.startswith("cc")
    assert record.sections[0].type == "abstract"
    assert sum(len(s.text) for s in record.sections if s.type != "abstract") > 5000
