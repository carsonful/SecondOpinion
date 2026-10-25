from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2 as httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.routers import claims, crossref, examples, health, normalization, pubmed
from app.services.crossref import CrossrefClient
from app.services.examples import initialize_examples
from app.services.pubmed import PubMedClient
from app.services.upstream import UpstreamResponseError, UpstreamUnavailableError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_examples()
    # One shared client per service and process, so every request goes through the same rate limiter.
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as http_client:
        app.state.pubmed_client = PubMedClient.from_settings(settings, http_client)
        app.state.crossref_client = CrossrefClient.from_settings(settings, http_client)
        yield


async def upstream_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    service = getattr(exc, "service", "An evidence source")
    return JSONResponse(status_code=503, content={"detail": f"{service} is unavailable, try again shortly"})


async def upstream_response_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(UpstreamUnavailableError, upstream_unavailable_handler)
    app.add_exception_handler(UpstreamResponseError, upstream_response_handler)

    app.include_router(health.router, prefix="/api")
    app.include_router(pubmed.router, prefix="/api")
    app.include_router(normalization.router, prefix="/api")
    app.include_router(claims.router, prefix="/api")
    app.include_router(examples.router, prefix="/api")
    app.include_router(crossref.router, prefix="/api")
    return app


app = create_app()
