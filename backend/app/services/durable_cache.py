"""Keys and PostgreSQL storage for the optional cross-process claim cache."""

import hashlib
import json
import logging

import psycopg
from pydantic import SecretStr, ValidationError
from psycopg.types.json import Jsonb

from app.models.claims import ClaimCandidates
from app.models.normalization import NormalizedClaim

FORMAT_VERSION = 1
logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_cache_entries (
    layer TEXT NOT NULL CHECK (layer IN ('normalized', 'candidates')),
    key_hash TEXT NOT NULL,
    format_version INTEGER NOT NULL,
    payload JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (layer, key_hash)
)
"""


def cache_key(layer: str, *parts: str | int) -> str:
    """Versioned digest avoids storing raw claim text in PostgreSQL keys."""
    encoded = json.dumps(
        [FORMAT_VERSION, layer, *parts], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PostgresClaimsCache:
    """Optional shared cache stored in a dedicated PostgreSQL database.

    Connections are short-lived. The existing in-memory cache serves hot requests
    in each process; PostgreSQL is consulted after a local miss.
    """

    def __init__(self, database_url: SecretStr, ttl_seconds: float) -> None:
        self._database_url = database_url
        self.ttl_seconds = ttl_seconds

    async def _connect(self) -> psycopg.AsyncConnection:
        return await psycopg.AsyncConnection.connect(
            self._database_url.get_secret_value(), connect_timeout=2
        )

    async def initialize(self) -> None:
        async with await self._connect() as connection:
            await connection.execute(SCHEMA)
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS claim_cache_expires_at "
                "ON claim_cache_entries (expires_at)"
            )

    async def _get(self, layer: str, key_hash: str) -> dict | None:
        async with await self._connect() as connection:
            cursor = await connection.execute(
                "SELECT payload FROM claim_cache_entries "
                "WHERE layer = %s AND key_hash = %s AND format_version = %s "
                "AND expires_at > now()",
                (layer, key_hash, FORMAT_VERSION),
            )
            row = await cursor.fetchone()
        return row[0] if row else None

    async def _put(self, layer: str, key_hash: str, payload: dict) -> None:
        if self.ttl_seconds <= 0:
            return
        async with await self._connect() as connection:
            await connection.execute(
                "INSERT INTO claim_cache_entries "
                "(layer, key_hash, format_version, payload, expires_at) "
                "VALUES (%s, %s, %s, %s, now() + (%s::double precision * interval '1 second')) "
                "ON CONFLICT (layer, key_hash) DO UPDATE SET "
                "format_version = EXCLUDED.format_version, "
                "payload = EXCLUDED.payload, expires_at = EXCLUDED.expires_at",
                (layer, key_hash, FORMAT_VERSION, Jsonb(payload), self.ttl_seconds),
            )

    async def get_normalized(self, raw_key: str) -> NormalizedClaim | None:
        payload = await self._get("normalized", cache_key("normalized", raw_key))
        if payload is None:
            return None
        try:
            return NormalizedClaim.model_validate(payload)
        except ValidationError:
            logger.warning("invalid normalized cache entry")
            return None

    async def put_normalized(self, raw_key: str, value: NormalizedClaim) -> None:
        await self._put(
            "normalized", cache_key("normalized", raw_key), value.model_dump(mode="json")
        )

    async def get_candidates(self, query: str, limit: int) -> ClaimCandidates | None:
        payload = await self._get("candidates", cache_key("candidates", query, limit))
        if payload is None:
            return None
        try:
            return ClaimCandidates.model_validate(payload)
        except ValidationError:
            logger.warning("invalid candidates cache entry")
            return None

    async def put_candidates(self, query: str, limit: int, value: ClaimCandidates) -> None:
        # The submitted wording belongs to the current request, not a shared row.
        stored = value.model_copy(update={"claim": "", "cached": False})
        await self._put(
            "candidates", cache_key("candidates", query, limit), stored.model_dump(mode="json")
        )

    async def _delete(self, layer: str, key_hash: str) -> bool:
        async with await self._connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM claim_cache_entries WHERE layer = %s AND key_hash = %s",
                (layer, key_hash),
            )
            return cursor.rowcount > 0

    async def delete_normalized(self, raw_key: str) -> bool:
        return await self._delete("normalized", cache_key("normalized", raw_key))

    async def delete_candidates(self, query: str, limit: int) -> bool:
        return await self._delete("candidates", cache_key("candidates", query, limit))

    async def prune(self) -> int:
        async with await self._connect() as connection:
            cursor = await connection.execute(
                "DELETE FROM claim_cache_entries "
                "WHERE expires_at <= now() OR format_version <> %s",
                (FORMAT_VERSION,),
            )
            return cursor.rowcount

    async def stats(self) -> dict[str, int]:
        async with await self._connect() as connection:
            cursor = await connection.execute(
                "SELECT layer, count(*) FROM claim_cache_entries "
                "WHERE expires_at > now() AND format_version = %s GROUP BY layer",
                (FORMAT_VERSION,),
            )
            rows = await cursor.fetchall()
        counts = {"normalized": 0, "candidates": 0}
        counts.update({layer: count for layer, count in rows})
        return counts
