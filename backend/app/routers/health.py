from fastapi import APIRouter, Request

from app import __version__
from app.config import get_settings
from app.models.health import DependencyStatus, HealthResponse
from app.services import examples

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    """API status plus which optional dependencies are working (#71).

    `status` is "ok" whenever the API process is up. Check `dependencies` to see
    whether Azure, the saved examples database, and the shared claim cache are set up.
    """
    settings = get_settings()
    azure_configured = all((
        settings.azure_inference_endpoint,
        settings.azure_model_deployment_name,
        settings.azure_inference_api_key,
    ))

    if settings.database_url is None:
        examples_db = "not_configured"
    elif await examples.examples_database_reachable(settings.database_url):
        examples_db = "reachable"
    else:
        examples_db = "unreachable"

    # The cache drops its PostgreSQL layer after a failure, so a configured URL
    # without a persistent layer means it was turned off.
    if request.app.state.claims_cache.persistent is not None:
        claim_cache = "active"
    elif settings.cache_database_url is not None:
        claim_cache = "disabled"
    else:
        claim_cache = "not_configured"

    return HealthResponse(
        status="ok",
        version=__version__,
        dependencies=DependencyStatus(
            azure="configured" if azure_configured else "not_configured",
            examples_db=examples_db,
            claim_cache=claim_cache,
        ),
    )
