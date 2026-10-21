import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from app.config import get_settings
from app.models.examples import ExampleResult


def initialize_examples() -> None:
    database_url = get_settings().database_url
    if database_url is None:
        return

    path = Path(__file__).resolve().parents[1] / "data" / "example_results.json"
    examples = json.loads(path.read_text(encoding="utf-8"))
    with psycopg.connect(database_url.get_secret_value()) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS example_results "
            "(slug TEXT PRIMARY KEY, result JSONB NOT NULL)"
        )
        for slug, data in examples.items():
            result = ExampleResult.model_validate(data)
            connection.execute(
                "INSERT INTO example_results (slug, result) VALUES (%s, %s) "
                "ON CONFLICT (slug) DO NOTHING",
                (slug, Jsonb(result.model_dump())),
            )


def get_example(slug: str) -> ExampleResult | None:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with psycopg.connect(database_url.get_secret_value()) as connection:
        row = connection.execute(
            "SELECT result FROM example_results WHERE slug = %s", (slug,)
        ).fetchone()

    return ExampleResult.model_validate(row[0]) if row else None
