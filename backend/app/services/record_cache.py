"""Cache full-text records so repeated claims don't re-fetch the same studies.

The project has no Azure Blob Storage yet, so records live as local JSON files.
Another backend (Blob, Postgres) only needs to implement RecordCache.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.models.full_text import FullTextRecord

logger = logging.getLogger(__name__)

# Abstract-only results expire so a later open-access release gets picked up.
ABSTRACT_ONLY_TTL = timedelta(days=7)


class RecordCache(Protocol):
    async def get(self, pmid: str) -> FullTextRecord | None: ...

    async def put(self, record: FullTextRecord) -> None: ...


class LocalRecordCache:
    """One JSON file per PMID: {"cached_at": ISO time, "record": {...}}."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    async def get(self, pmid: str) -> FullTextRecord | None:
        return await asyncio.to_thread(self._read, pmid)

    async def put(self, record: FullTextRecord) -> None:
        await asyncio.to_thread(self._write, record)

    def _path(self, pmid: str) -> Path:
        # PMIDs become file names, so accept digits only.
        if not re.fullmatch(r"\d{1,9}", pmid):
            raise ValueError("Invalid PMID")
        return self._directory / f"{pmid}.json"

    def _read(self, pmid: str) -> FullTextRecord | None:
        path = self._path(pmid)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            record = FullTextRecord.model_validate(entry["record"])
            cached_at = datetime.fromisoformat(entry["cached_at"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            logger.warning("Ignoring unreadable full-text cache entry: pmid=%s", pmid)
            return None
        if record.source_tier == "abstract_only" and datetime.now(timezone.utc) - cached_at > ABSTRACT_ONLY_TTL:
            return None
        return record

    def _write(self, record: FullTextRecord) -> None:
        path = self._path(record.pmid)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"cached_at": datetime.now(timezone.utc).isoformat(), "record": record.model_dump()}
        # Write then rename, so a concurrent reader never sees half a file.
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(entry), encoding="utf-8")
        os.replace(temporary, path)
