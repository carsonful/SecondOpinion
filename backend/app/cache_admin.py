"""Inspect and manually add validated results to the separate claim cache database."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import psycopg
from pydantic import ValidationError

from app.config import get_settings
from app.models.claims import ClaimCandidates
from app.services.cache import canonical_claim_key
from app.services.claims import ClaimsCache


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Manage the optional PostgreSQL claim cache (CACHE_DATABASE_URL)."
    )
    actions = command.add_subparsers(dest="action", required=True)

    put = actions.add_parser("put", help="Cache a validated /api/claims response from a JSON file")
    put.add_argument("file", type=Path)
    put.add_argument("--limit", type=int, default=20, help="Limit used for the original request")

    validate = actions.add_parser("validate", help="Check a response file without using the database")
    validate.add_argument("file", type=Path)
    validate.add_argument("--limit", type=int, default=20)

    get = actions.add_parser("get", help="Print a cached result for an exact claim wording")
    get.add_argument("claim")
    get.add_argument("--limit", type=int, default=20)

    delete = actions.add_parser("delete", help="Remove the claim and matching candidate result")
    delete.add_argument("claim")
    delete.add_argument("--limit", type=int, default=20)

    actions.add_parser("stats", help="Count live cache entries by layer")
    actions.add_parser("prune", help="Delete expired or old-format cache entries")
    return command


def _validate_result(data: object, limit: int) -> ClaimCandidates:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    result = ClaimCandidates.model_validate(data)
    if not result.claim.strip():
        raise ValueError("the response must include its original claim")
    if not result.normalized.query.strip():
        raise ValueError("the normalized search query cannot be blank")
    if len(result.candidates) > limit:
        raise ValueError("candidate count exceeds the supplied limit")
    if result.total_results < len(result.candidates):
        raise ValueError("total_results cannot be smaller than the candidate count")
    levels = [item.access.level for item in result.candidates]
    coverage = result.coverage
    if (
        coverage.retrieved_studies != len(levels)
        or coverage.full_text_available != levels.count("full_text")
        or coverage.abstract_only != levels.count("abstract_only")
        or coverage.metadata_only != levels.count("metadata_only")
    ):
        raise ValueError("coverage counts do not match the candidate studies")
    return result


def _load_result(path: Path, limit: int) -> ClaimCandidates:
    return _validate_result(json.loads(path.read_text(encoding="utf-8")), limit)


async def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.action in {"put", "validate"}:
        try:
            result = _load_result(args.file, args.limit)
        except (OSError, ValueError, ValidationError) as exc:
            print(f"Invalid result: {exc}", file=sys.stderr)
            return 2
        if args.action == "validate":
            print(f"Valid result with {len(result.candidates)} candidates for limit {args.limit}.")
            return 0

    settings = get_settings()
    cache = ClaimsCache.from_settings(settings)
    store = cache.persistent
    if store is None:
        print("Set CACHE_DATABASE_URL and enable caching to manage the cache.", file=sys.stderr)
        return 2

    await store.initialize()
    if args.action == "put":
        await store.put_normalized(canonical_claim_key(result.claim), result.normalized)
        await store.put_candidates(result.normalized.query, args.limit, result)
        print(f"Cached claim for {settings.claims_cache_ttl_seconds:g} seconds.")
        return 0

    if args.action in {"get", "delete"}:
        if args.limit < 1 or args.limit > 100:
            print("limit must be between 1 and 100", file=sys.stderr)
            return 2
        key = canonical_claim_key(args.claim)
        normalized = await store.get_normalized(key)
        if normalized is None:
            print("Claim is not cached.", file=sys.stderr)
            return 1
        if args.action == "delete":
            await store.delete_candidates(normalized.query, args.limit)
            await store.delete_normalized(key)
            print("Removed matching cache entries.")
            return 0
        result = await store.get_candidates(normalized.query, args.limit)
        if result is None:
            print("Candidate result is not cached for that limit.", file=sys.stderr)
            return 1
        print(result.model_copy(update={
            "claim": args.claim, "normalized": normalized, "cached": True,
        }).model_dump_json(indent=2))
        return 0

    if args.action == "prune":
        print(f"Removed {await store.prune()} expired or old-format entries.")
    else:
        print(json.dumps(await store.stats(), sort_keys=True))
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run()))
    except psycopg.Error:
        print("Cannot access the configured claim cache database.", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
