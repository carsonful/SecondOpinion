"""One normalized study record, whichever source its text came from."""

from typing import Literal

from pydantic import BaseModel

SectionType = Literal[
    "abstract", "introduction", "methods", "results", "discussion", "limitations", "other",
]
# pmc_fulltext: Europe PMC JATS or NCBI BioC. oa_pdf: Unpaywall PDF parsed by
# Document Intelligence. abstract_only: the PubMed abstract.
SourceTier = Literal["pmc_fulltext", "oa_pdf", "abstract_only"]


class Section(BaseModel):
    type: SectionType
    heading: str | None
    text: str


class FullTextRecord(BaseModel):
    pmid: str
    pmcid: str | None
    doi: str | None
    title: str
    year: int | None
    journal: str | None
    # Raw NLM publication types from PubMed ("Randomized Controlled Trial", ...).
    publication_types: list[str]
    source_tier: SourceTier
    # Unpaywall-style identifier such as "cc-by", when the source states one.
    license: str | None
    sections: list[Section]
