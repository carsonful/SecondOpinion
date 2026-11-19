"""PMC full-text retrieval status and access coverage."""

from typing import Literal

from pydantic import BaseModel, Field


class FullTextAccess(BaseModel):
    level: Literal["full_text", "abstract_only", "metadata_only"]
    reason: Literal["retrieved", "no_pmc_id", "not_available", "request_failed", "parse_failed", "too_large"]
    detail: str
    pmc_id: str | None = None
    source_url: str | None = None
    license: str | None = None
    sections: list[str] = Field(default_factory=list)


class TextSection(BaseModel):
    id: str
    label: str
    text: str


class PMCDocument(BaseModel):
    pmc_id: str
    pmid: str | None
    source_url: str
    license: str | None
    sections: list[TextSection]


class RetrievalResult(BaseModel):
    access: FullTextAccess
    document: PMCDocument | None = None


class EvidenceCoverage(BaseModel):
    retrieved_studies: int
    full_text_available: int
    abstract_only: int
    metadata_only: int
