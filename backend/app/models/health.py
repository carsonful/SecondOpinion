from typing import Literal

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    """Optional services the API uses. None of these values contain secrets or hostnames."""

    # Read from settings only; no Azure call is made.
    azure: Literal["configured", "not_configured"]
    examples_db: Literal["not_configured", "reachable", "unreachable"]
    # "disabled" means a cache database was configured but failed, so the API
    # fell back to the in-memory cache.
    claim_cache: Literal["not_configured", "active", "disabled"]


class HealthResponse(BaseModel):
    # Stays "ok" while the API is up; optional dependencies being off is not an outage.
    status: Literal["ok"]
    version: str
    dependencies: DependencyStatus
