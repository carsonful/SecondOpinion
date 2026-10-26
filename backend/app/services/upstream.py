"""Shared plumbing for calling external evidence APIs (PubMed, Crossref, ...)."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2 as httpx

from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Cap on how long we honor a Retry-After header, so a user request never hangs.
MAX_RETRY_AFTER = 10.0


class UpstreamError(Exception):
    """Base class for failures talking to an external API."""

    service = "An evidence source"


class UpstreamUnavailableError(UpstreamError):
    """The service could not be reached, or kept failing after retries. Maps to HTTP 503."""


class UpstreamResponseError(UpstreamError):
    """The service answered, but with something we could not use. Maps to HTTP 502."""


async def get_with_retries(
    http: httpx.AsyncClient,
    url: str,
    *,
    limiter: RateLimiter,
    sleep: Callable[[float], Awaitable[None]],
    unavailable_error: type[UpstreamUnavailableError],
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = False,
) -> httpx.Response:
    """GET `url`, retrying throttling, server errors, and dropped connections with backoff.

    Any other response, including 4xx errors, is returned for the caller to interpret.
    """
    service = unavailable_error.service
    for attempt in range(MAX_RETRIES + 1):
        await limiter.acquire()
        try:
            response = await http.get(
                url, params=params, headers=headers, follow_redirects=follow_redirects
            )
        except httpx.TransportError as exc:
            if attempt == MAX_RETRIES:
                raise unavailable_error(f"Could not reach {service}: {exc}") from exc
            delay = RETRY_BASE_DELAY * 2**attempt
            logger.warning("%s transport error (%s), retrying in %.1fs", service, exc, delay)
            await sleep(delay)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == MAX_RETRIES:
                raise unavailable_error(f"{service} kept failing with HTTP {response.status_code}")
            delay = _retry_delay(response, attempt)
            logger.warning(
                "%s returned HTTP %s for %s, retrying in %.1fs",
                service, response.status_code, response.url.path, delay,
            )
            await sleep(delay)
            continue

        return response

    raise AssertionError("unreachable")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER)
        except ValueError:
            pass
    return RETRY_BASE_DELAY * 2**attempt
