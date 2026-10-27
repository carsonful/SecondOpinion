"""Keys and PostgreSQL storage for the optional cross-process claim cache."""

import hashlib
import json

FORMAT_VERSION = 1


def cache_key(layer: str, *parts: str | int) -> str:
    """Versioned digest avoids storing raw claim text in PostgreSQL keys."""
    encoded = json.dumps(
        [FORMAT_VERSION, layer, *parts], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
