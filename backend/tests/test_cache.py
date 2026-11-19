from app.services.cache import TTLCache
from tests.helpers import FakeClock


def test_returns_what_was_stored() -> None:
    cache: TTLCache[str, int] = TTLCache(60, 10)

    cache.set("a", 1)

    assert cache.get("a") == 1
    assert cache.get("missing") is None


def test_entries_expire_after_the_ttl() -> None:
    clock = FakeClock()
    cache: TTLCache[str, int] = TTLCache(60, 10, clock=clock)
    cache.set("a", 1)

    clock.now = 59.9
    assert cache.get("a") == 1
    clock.now = 60
    assert cache.get("a") is None
    assert len(cache) == 0


def test_least_recently_used_entry_is_dropped_when_full() -> None:
    cache: TTLCache[str, int] = TTLCache(60, 2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # "b" is now the least recently used

    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_zero_ttl_disables_the_cache() -> None:
    cache: TTLCache[str, int] = TTLCache(0, 10)

    cache.set("a", 1)

    assert cache.get("a") is None
    assert cache.enabled is False


def test_clear_empties_the_cache() -> None:
    cache: TTLCache[str, int] = TTLCache(60, 10)
    cache.set("a", 1)

    cache.clear()

    assert len(cache) == 0
