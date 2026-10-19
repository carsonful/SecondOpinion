from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.models.pubmed import PubMedArticle, PubMedSearchResponse
from app.services.pubmed import PubMedClient

router = APIRouter(
    prefix="/pubmed",
    tags=["pubmed"],
    responses={
        502: {"description": "PubMed returned a response we could not use"},
        503: {"description": "PubMed is unreachable or throttling us"},
    },
)


def get_pubmed_client(request: Request) -> PubMedClient:
    return request.app.state.pubmed_client


PubMedDep = Annotated[PubMedClient, Depends(get_pubmed_client)]


@router.get("/search")
async def search_pubmed(
    client: PubMedDep,
    q: Annotated[str, Query(min_length=2, max_length=500, description="PubMed search query")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PubMedSearchResponse:
    """Search PubMed and return full study records for the top matches, most relevant first."""
    return await client.search(q, limit)


@router.get("/articles/{pmid}", responses={404: {"description": "No PubMed article with this PMID"}})
async def get_pubmed_article(
    client: PubMedDep,
    pmid: Annotated[str, Path(pattern=r"^\d{1,9}$", description="PubMed ID")],
) -> PubMedArticle:
    article = await client.get_article(pmid)
    if article is None:
        raise HTTPException(status_code=404, detail=f"No PubMed article with PMID {pmid}")
    return article
