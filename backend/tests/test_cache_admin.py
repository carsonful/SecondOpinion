"""The admin command can load and inspect responses without external API calls."""

import json
import os

import psycopg
import pytest

from app import cache_admin
from app.config import Settings
from app.models.claims import ClaimCandidates
from app.models.full_text import EvidenceCoverage
from app.models.normalization import NormalizedClaim
from app.services.claims import ClaimsCache

TEST_URL = os.getenv("TEST_CACHE_DATABASE_URL")
pytestmark = pytest.mark.anyio


def empty_result() -> ClaimCandidates:
    return ClaimCandidates(
        claim="Does zinc help with the common cold?",
        normalized=NormalizedClaim(
            query="(zinc) AND (common cold)", intervention="zinc", outcome="common cold",
            relation="helps", negated=False,
        ),
        query_translation=None, total_results=0, candidates=[],
        coverage=EvidenceCoverage(
            retrieved_studies=0, full_text_available=0, abstract_only=0, metadata_only=0,
        ),
    )


@pytest.fixture
async def configured_cache(monkeypatch):
    if not TEST_URL:
        pytest.skip("requires test PostgreSQL")
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
    result = empty_result()
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

    payload.write_text(json.dumps({
        "claim": "Does zinc help?",
        "normalized": {
            "query": "zinc", "intervention": "zinc", "outcome": "health",
            "relation": "helps", "negated": False,
        },
        "query_translation": None, "total_results": 0, "candidates": [],
        "coverage": {
            "retrieved_studies": 1, "full_text_available": 0,
            "abstract_only": 0, "metadata_only": 0,
        },
    }), encoding="utf-8")
    assert await cache_admin.run(["put", str(payload)]) == 2
    assert "coverage counts" in capsys.readouterr().err


async def test_validate_does_not_connect_to_database(tmp_path, monkeypatch, capsys):
    payload = tmp_path / "result.json"
    payload.write_text(empty_result().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(cache_admin, "get_settings", lambda: pytest.fail("database settings read"))

    assert await cache_admin.run(["validate", str(payload), "--limit", "5"]) == 0
    assert "Valid result with 0 candidates" in capsys.readouterr().out
