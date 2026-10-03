from fastapi import APIRouter

from app import __version__
from app.models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
