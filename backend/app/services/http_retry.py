"""Rate-limited HTTP requests with retries, for the full-text sources.

Same policy as PubMedClient: retry transport errors, 429 and 5xx with exponential
backoff, honoring a short Retry-After. Other error statuses fail immediately.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2 as httpx

from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 10.0

Sleep = Callable[[float], Awaitable[None]]


class UpstreamError(Exception):
    """A full-text source failed. Messages never include URLs, which can carry keys."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def request_with_retries(
    http: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    service: str,
    limiter: RateLimiter | None = None,
    sleep: Sleep = asyncio.sleep,
    **kwargs: Any,
) -> httpx.Response:
    """Send one request, retrying transient failures. Raises UpstreamError on failure."""
    for attempt in range(MAX_RETRIES + 1):
        if limiter is not None:
            await limiter.acquire()
        try:
            response = await http.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            if attempt == MAX_RETRIES:
                raise UpstreamError(f"Could not reach {service}") from exc
            delay = RETRY_BASE_DELAY * 2**attempt
            logger.warning("%s transport error (%s), retrying in %.1fs", service, type(exc).__name__, delay)
            await sleep(delay)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == MAX_RETRIES:
                raise UpstreamError(
                    f"{service} kept failing with HTTP {response.status_code}", response.status_code
                )
            delay = retry_delay(response, attempt)
            logger.warning("%s returned HTTP %s, retrying in %.1fs", service, response.status_code, delay)
            await sleep(delay)
            continue

        if response.is_error:
            raise UpstreamError(f"{service} returned HTTP {response.status_code}", response.status_code)
        return response

    raise AssertionError("unreachable")


def retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER)
        except ValueError:
            pass
    return RETRY_BASE_DELAY * 2**attempt
