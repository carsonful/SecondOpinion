import psycopg
from fastapi import APIRouter, HTTPException

from app.models.examples import ExampleResult
from app.services.examples import get_example

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("/{slug}")
def read_example(slug: str) -> ExampleResult:
    try:
        result = get_example(slug)
    except (psycopg.Error, RuntimeError):
        raise HTTPException(status_code=503, detail="Saved examples are unavailable") from None

    if result is None:
        raise HTTPException(status_code=404, detail="Example not found")
    return result
