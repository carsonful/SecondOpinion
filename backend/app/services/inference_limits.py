"""Bounded, per-process token buckets shared by all model-backed routes."""

from collections import OrderedDict
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request


class InferenceLimiter:
    def __init__(
        self, requests: int, window_seconds: int, max_clients: int,
        *, enabled: bool = True, clock: Callable[[], float] = monotonic,
    ) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.enabled = enabled
        self.clock = clock
        self._clients: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._lock = Lock()

    def retry_after(self, client: str) -> int | None:
        if not self.enabled:
            return None
        with self._lock:
            now = self.clock()
            # An idle bucket refills fully in one window. Never evict an active
            # bucket: rotating identities must not reset another client's quota.
            while self._clients:
                _, updated = next(iter(self._clients.values()))
                if now - updated < self.window_seconds:
                    break
                self._clients.popitem(last=False)
            previous = self._clients.get(client)
            if previous is None:
                if len(self._clients) >= self.max_clients:
                    return self.window_seconds
                tokens = float(self.requests)
            else:
                tokens, updated = previous
                tokens = min(self.requests, tokens + (now - updated) * self.requests / self.window_seconds)
            retry = None if tokens >= 1 else max(1, ceil((1 - tokens) * self.window_seconds / self.requests))
            self._clients[client] = (tokens - 1 if retry is None else tokens, now)
            self._clients.move_to_end(client)
            return retry


async def require_inference_budget(request: Request) -> None:
    # Only the ASGI peer is trusted here. Uvicorn may rewrite it when the
    # immediate proxy is explicitly trusted; never parse forwarding headers.
    client = request.client.host if request.client else "unknown"
    retry = request.app.state.inference_limiter.retry_after(client)
    if retry is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many research requests. Please wait before trying again.",
            headers={"Retry-After": str(retry)},
        )
