import asyncio
import time
from collections.abc import Awaitable, Callable


class RateLimiter:
    """Spaces calls at least 1/rate seconds apart, across every caller sharing the instance.

    Requests are spaced evenly rather than allowed in bursts, because NCBI counts
    requests per second and a burst at the start of a second is what gets throttled.
    """

    def __init__(
        self,
        rate_per_second: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self.interval = 1.0 / rate_per_second
        self._clock = clock
        self._sleep = sleep
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            wait = self._next_slot - now
            if wait > 0:
                await self._sleep(wait)
            self._next_slot = max(now, self._next_slot) + self.interval
