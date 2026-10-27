"""Run with TEST_CACHE_DATABASE_URL pointing to a disposable PostgreSQL database."""

import os

import psycopg
import pytest
from pydantic import SecretStr
from psycopg.types.json import Jsonb

from app.models.claims import ClaimCandidates
from app.models.normalization import NormalizedClaim
from app.services.durable_cache import FORMAT_VERSION, PostgresClaimsCache, cache_key

TEST_URL = os.getenv("TEST_CACHE_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not TEST_URL, reason="requires test PostgreSQL")]

NORMALIZED = NormalizedClaim(
    query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
    relation="cures", negated=False,
)


@pytest.fixture
async def store() -> PostgresClaimsCache:
    cache = PostgresClaimsCache(SecretStr(TEST_URL), ttl_seconds=3600)
    await cache.initialize()
    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        await connection.execute("TRUNCATE claim_cache_entries")
    return cache


def empty_result(claim: str = "does zinc cure colds") -> ClaimCandidates:
    return ClaimCandidates(
        claim=claim, normalized=NORMALIZED, query_translation=None,
        total_results=0, candidates=[],
    )


async def test_round_trip_layers_are_separate_and_claim_text_is_not_stored(store):
    await store.put_normalized("does zinc cure colds", NORMALIZED)
    await store.put_candidates(NORMALIZED.query, 20, empty_result())

    assert await store.get_normalized("does zinc cure colds") == NORMALIZED
    assert await store.get_normalized("does zinc help colds") is None
    result = await store.get_candidates(NORMALIZED.query, 20)
    assert result is not None
    assert result.claim == ""
    assert result.cached is False
    assert await store.get_candidates(NORMALIZED.query, 10) is None
    assert await store.stats() == {"normalized": 1, "candidates": 1}

    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        cursor = await connection.execute(
            "SELECT key_hash, payload->>'claim' FROM claim_cache_entries WHERE layer = 'candidates'"
        )
        key_hash, stored_claim = await cursor.fetchone()
    assert len(key_hash) == 64
    assert stored_claim == ""


async def test_expiry_and_prune(store):
    await store.put_normalized("does zinc cure colds", NORMALIZED)
    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        await connection.execute(
            "UPDATE claim_cache_entries SET expires_at = now() - interval '1 second'"
        )

    assert await store.get_normalized("does zinc cure colds") is None
    assert await store.stats() == {"normalized": 0, "candidates": 0}
    assert await store.prune() == 1


async def test_format_version_and_invalid_payload_miss_safely(store):
    await store.put_normalized("does zinc cure colds", NORMALIZED)
    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        await connection.execute(
            "UPDATE claim_cache_entries SET format_version = %s",
            (FORMAT_VERSION + 1,),
        )
    assert await store.get_normalized("does zinc cure colds") is None
    assert await store.prune() == 1

    await store.put_normalized("does zinc cure colds", NORMALIZED)
    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        await connection.execute(
            "UPDATE claim_cache_entries SET payload = %s WHERE key_hash = %s",
            (Jsonb({"bad": "data"}), cache_key("normalized", "does zinc cure colds")),
        )
    assert await store.get_normalized("does zinc cure colds") is None


async def test_upsert_delete_and_zero_ttl(store):
    await store.put_candidates(NORMALIZED.query, 20, empty_result("first wording"))
    await store.put_candidates(NORMALIZED.query, 20, empty_result("another wording"))
    assert await store.stats() == {"normalized": 0, "candidates": 1}
    assert await store.delete_candidates(NORMALIZED.query, 20) is True
    assert await store.delete_candidates(NORMALIZED.query, 20) is False

    disabled = PostgresClaimsCache(SecretStr(TEST_URL), ttl_seconds=0)
    await disabled.put_normalized("does zinc cure colds", NORMALIZED)
    assert await disabled.get_normalized("does zinc cure colds") is None
