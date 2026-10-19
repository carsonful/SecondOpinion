from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2 as httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.routers import claims, health, normalization, pubmed
from app.services.pubmed import PubMedClient, PubMedResponseError, PubMedUnavailableError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One shared client per process, so every request goes through the same rate limiter.
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as http_client:
        app.state.pubmed_client = PubMedClient.from_settings(get_settings(), http_client)
        yield


async def pubmed_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "PubMed is unavailable, try again shortly"})


async def pubmed_response_handler(request: Request, exc: Exception) -> JSONResponse:
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

    app.add_exception_handler(PubMedUnavailableError, pubmed_unavailable_handler)
    app.add_exception_handler(PubMedResponseError, pubmed_response_handler)

    app.include_router(claims.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(pubmed.router, prefix="/api")
    app.include_router(normalization.router, prefix="/api")
    return app


app = create_app()
