from pydantic import BaseModel


class PubMedArticle(BaseModel):
    """One study record as parsed from a PubMed EFetch response."""

    pmid: str
    title: str
    abstract: str | None
    journal: str | None
    year: int | None
    authors: list[str]
    doi: str | None
    pmc_id: str | None
    # Raw NLM publication types ("Randomized Controlled Trial", "Meta-Analysis", ...).
    # Study-type classification (#14) is built on top of these.
    publication_types: list[str]
    mesh_terms: list[str]
    # PubMed's own retraction marker. Crossref (#13) is the authoritative check.
    retracted: bool
    url: str


class PubMedSearchResponse(BaseModel):
    query: str
    # How PubMed actually interpreted the query, useful for debugging bad matches.
    query_translation: str | None
    total_results: int
    articles: list[PubMedArticle]
