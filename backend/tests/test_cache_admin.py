"""The admin command can load and inspect responses without external API calls."""

import json
import os

import psycopg
import pytest

from app import cache_admin
from app.config import Settings
from app.models.claims import ClaimCandidates
from app.models.normalization import NormalizedClaim
from app.services.claims import ClaimsCache

TEST_URL = os.getenv("TEST_CACHE_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not TEST_URL, reason="requires test PostgreSQL")]


@pytest.fixture
async def configured_cache(monkeypatch):
    settings = Settings(
        _env_file=None,
        cache_database_url=TEST_URL,
        database_url="postgresql://localhost/separate_examples_test",
    )
    monkeypatch.setattr(cache_admin, "get_settings", lambda: settings)
    await ClaimsCache.from_settings(settings).persistent.initialize()
    async with await psycopg.AsyncConnection.connect(TEST_URL) as connection:
        await connection.execute("TRUNCATE claim_cache_entries")
    return settings


async def test_put_get_stats_and_delete(tmp_path, capsys, configured_cache):
    result = ClaimCandidates(
        claim="Does zinc help with the common cold?",
        normalized=NormalizedClaim(
            query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
            relation="helps", negated=False,
        ),
        query_translation=None, total_results=0, candidates=[],
    )
    payload = tmp_path / "result.json"
    payload.write_text(result.model_dump_json(), encoding="utf-8")

    assert await cache_admin.run(["put", str(payload), "--limit", "5"]) == 0
    assert await cache_admin.run(["stats"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {
        "normalized": 1, "candidates": 1,
    }

    assert await cache_admin.run(["get", "  DOES zinc help with the common cold?", "--limit", "5"]) == 0
    loaded = json.loads(capsys.readouterr().out)
    assert loaded["cached"] is True
    assert loaded["claim"] == "  DOES zinc help with the common cold?"
    assert loaded["normalized"] == result.normalized.model_dump()

    assert await cache_admin.run(["delete", result.claim, "--limit", "5"]) == 0
    assert await cache_admin.run(["get", result.claim, "--limit", "5"]) == 1


async def test_invalid_manual_result_does_not_write(tmp_path, capsys, configured_cache):
    payload = tmp_path / "bad.json"
    payload.write_text('{"claim":"blank"}', encoding="utf-8")
    assert await cache_admin.run(["put", str(payload)]) == 2
    assert "Invalid result" in capsys.readouterr().err
    assert await cache_admin.run(["stats"]) == 0
    assert json.loads(capsys.readouterr().out) == {"normalized": 0, "candidates": 0}
