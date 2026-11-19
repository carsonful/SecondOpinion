import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.config import Settings
from app.main import app
from app.routers import normalization
from app.services import examples as example_service
from app.services.pubmed import PubMedClient


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requires PostgreSQL test database")
def test_examples_are_read_from_postgres_without_live_services(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]
    settings = Settings(_env_file=None, database_url=database_url)
    monkeypatch.setattr(example_service, "get_settings", lambda: settings)

    def no_foundry(*args, **kwargs):
        pytest.fail("Saved examples must not call Foundry")

    async def no_pubmed(*args, **kwargs):
        pytest.fail("Saved examples must not search PubMed")

    monkeypatch.setattr(normalization, "normalize_claim", no_foundry)
    monkeypatch.setattr(PubMedClient, "search", no_pubmed)
    with psycopg.connect(database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS example_results")

    with TestClient(app) as client:
        for slug in ("raw-milk", "cold-showers", "cracking-knuckles"):
            response = client.get(f"/api/examples/{slug}")
            assert response.status_code == 200
            data = response.json()
            assert data["claim"] and data["verdict"] and data["explanation"]
            assert data["sources"]

        with psycopg.connect(database_url) as connection:
            connection.execute(
                "UPDATE example_results SET result = jsonb_set(result, '{tag}', %s) "
                "WHERE slug = %s",
                (Jsonb("Read from PostgreSQL"), "raw-milk"),
            )
        assert client.get("/api/examples/raw-milk").json()["tag"] == "Read from PostgreSQL"
        assert client.get("/api/examples/unknown").status_code == 404


def test_app_still_starts_and_reports_503_when_the_examples_database_is_down(monkeypatch):
    # Nothing listens on port 1, so every connection is refused straight away.
    settings = Settings(_env_file=None, database_url="postgresql://user:pass@127.0.0.1:1/examples")
    monkeypatch.setattr(example_service, "get_settings", lambda: settings)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/examples/raw-milk").status_code == 503
