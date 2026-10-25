from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.crossref import IntegrityReport
from app.services.crossref import CrossrefClient, InvalidDoiError

router = APIRouter(
    prefix="/crossref",
    tags=["crossref"],
    responses={
        502: {"description": "Crossref returned a response we could not use"},
        503: {"description": "Crossref is unreachable or throttling us"},
    },
)


def get_crossref_client(request: Request) -> CrossrefClient:
    return request.app.state.crossref_client


CrossrefDep = Annotated[CrossrefClient, Depends(get_crossref_client)]


@router.get("/notices")
async def get_integrity_notices(
    client: CrossrefDep,
    doi: Annotated[str, Query(max_length=300, description="DOI, with or without a doi.org prefix")],
) -> IntegrityReport:
    """Retractions, corrections, and expressions of concern published against a paper."""
    try:
        return await client.check(doi)
    except InvalidDoiError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
