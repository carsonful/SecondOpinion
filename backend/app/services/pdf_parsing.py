"""Turn a study PDF into labeled sections.

PdfParser is the seam: DocumentIntelligenceParser is the current implementation,
and a GROBID parser would be another class with the same parse() method.
"""

import asyncio
import json
from typing import Any, Protocol

import httpx2 as httpx

from app.config import Settings
from app.models.full_text import Section, SectionType
from app.services.http_retry import Sleep, UpstreamError, request_with_retries
from app.services.jats_parser import FullTextParseError, classify_heading

DOCUMENT_INTELLIGENCE_API_VERSION = "2024-11-30"
POLL_INTERVAL = 1.0
MAX_POLLS = 60

# Layout roles that repeat on every page rather than belonging to the article.
_FURNITURE_ROLES = {"pageHeader", "pageFooter", "pageNumber", "footnote"}
# Back matter that is never study content.
_BACK_MATTER = ("references", "bibliography", "acknowledg", "funding", "conflict", "competing interest",
                "author contributions", "supplementary", "data availability")


class PdfParser(Protocol):
    async def parse(self, pdf: bytes) -> list[Section]: ...


class DocumentIntelligenceParser:
    """Azure AI Document Intelligence prebuilt-layout model, called over REST."""

    def __init__(
        self, http: httpx.AsyncClient, endpoint: str, api_key: str, *, sleep: Sleep = asyncio.sleep,
    ) -> None:
        url = httpx.URL(endpoint.rstrip("/"))
        if url.scheme != "https" or not url.host:
            raise ValueError("Use an HTTPS Document Intelligence endpoint")
        self._http = http
        self._analyze_url = (
            f"https://{url.host}/documentintelligence/documentModels/prebuilt-layout:analyze"
        )
        self._api_key = api_key
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings, http: httpx.AsyncClient) -> "DocumentIntelligenceParser | None":
        if not settings.azure_document_intelligence_endpoint or not settings.azure_document_intelligence_api_key:
            return None
        return cls(http, settings.azure_document_intelligence_endpoint,
                   settings.azure_document_intelligence_api_key.get_secret_value())

    async def parse(self, pdf: bytes) -> list[Section]:
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        response = await request_with_retries(
            self._http, "POST", self._analyze_url, service="Document Intelligence", sleep=self._sleep,
            params={"api-version": DOCUMENT_INTELLIGENCE_API_VERSION},
            headers=headers | {"Content-Type": "application/pdf"}, content=pdf,
        )
        operation = response.headers.get("Operation-Location")
        if not operation or httpx.URL(operation).host != httpx.URL(self._analyze_url).host:
            raise UpstreamError("Document Intelligence did not return an operation to poll")

        for _ in range(MAX_POLLS):
            await self._sleep(POLL_INTERVAL)
            poll = await request_with_retries(
                self._http, "GET", operation, service="Document Intelligence", sleep=self._sleep,
                headers=headers,
            )
            try:
                result = json.loads(poll.content)
                status = result["status"]
            except (ValueError, KeyError, TypeError):
                raise UpstreamError("Document Intelligence returned an unexpected response") from None
            if status == "succeeded":
                return sections_from_layout(result)
            if status not in ("notStarted", "running"):
                raise UpstreamError(f"Document Intelligence analysis {status}")
        raise UpstreamError("Document Intelligence analysis timed out")


def sections_from_layout(result: dict[str, Any]) -> list[Section]:
    """Group layout paragraphs into sections, starting a new one at each section heading."""
    try:
        paragraphs = result["analyzeResult"]["paragraphs"]
        if not isinstance(paragraphs, list):
            raise TypeError
    except (KeyError, TypeError):
        raise FullTextParseError("Document Intelligence result has no paragraphs") from None

    sections: list[Section] = []
    current: Section | None = None
    skipping = False
    for paragraph in paragraphs:
        role = paragraph.get("role")
        text = " ".join(str(paragraph.get("content") or "").split())
        if not text or role in _FURNITURE_ROLES or role == "title":
            continue
        if role == "sectionHeading":
            skipping = any(word in text.casefold() for word in _BACK_MATTER)
            if skipping:
                continue
            section_type: SectionType = classify_heading(text)
            if current is not None and section_type == "other" and current.type != "other":
                # Unrecognized headings such as "Participants" are subsections.
                current.text += f"\n{text}"
                continue
            current = Section(type=section_type, heading=text, text="")
            sections.append(current)
            continue
        if skipping:
            continue
        if current is None:
            # Author lines and affiliations before the first heading.
            current = Section(type="other", heading=None, text="")
            sections.append(current)
        current.text += f"\n{text}"

    for section in sections:
        section.text = section.text.strip()
    return [s for s in sections if s.text]
