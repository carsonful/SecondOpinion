import asyncio

import pytest

from app.services.rate_limiter import RateLimiter
from tests.helpers import FakeClock


@pytest.mark.anyio
async def test_first_call_does_not_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(3, clock=clock, sleep=clock.sleep)

    await limiter.acquire()

    assert clock.sleeps == []


@pytest.mark.anyio
async def test_back_to_back_calls_are_spaced_by_the_interval() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, clock=clock, sleep=clock.sleep)
    times = []

    for _ in range(5):
        await limiter.acquire()
        times.append(clock.now)

    assert times == [0.0, 0.5, 1.0, 1.5, 2.0]


@pytest.mark.anyio
async def test_concurrent_callers_share_one_budget() -> None:
    clock = FakeClock()
    limiter = RateLimiter(4, clock=clock, sleep=clock.sleep)
    times = []

    async def call() -> None:
        await limiter.acquire()
        times.append(clock.now)

    await asyncio.gather(*(call() for _ in range(8)))

    assert sorted(times) == [i * 0.25 for i in range(8)]


@pytest.mark.anyio
async def test_idle_time_is_not_banked_into_a_burst() -> None:
    clock = FakeClock()
    limiter = RateLimiter(2, clock=clock, sleep=clock.sleep)

    await limiter.acquire()
    clock.now = 10.0
    await limiter.acquire()
    await limiter.acquire()

    assert clock.now == 10.5


def test_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(0)
