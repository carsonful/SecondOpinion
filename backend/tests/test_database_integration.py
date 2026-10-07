"""Runs against a disposable PostgreSQL database with pgvector installed."""

import io
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db import Study, StudyEmbedding
from app.config import get_settings
from app.embeddings import embed_studies
from app.pubmed import ingest_stream
from tests.test_pubmed import XML

pytestmark = pytest.mark.integration


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()
    command.downgrade(config, "base")
    rollback_engine = create_engine(url)
    with rollback_engine.connect() as connection:
        assert not {"claims", "studies", "evidence_scores", "verdicts", "study_embeddings", "ingestion_checkpoints"} & set(inspect(connection).get_table_names())
    rollback_engine.dispose()
    get_settings.cache_clear()


def test_migration_constraints_and_indexes(database):
    tables = set(inspect(database).get_table_names())
    assert {"claims", "studies", "evidence_scores", "verdicts", "study_embeddings", "ingestion_checkpoints"} <= tables
    with database.connect() as connection:
        indexes = {row[0]: row[1] for row in connection.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = current_schema()"))}
    assert "USING gin" in indexes["ix_studies_text_search"]
    assert "USING hnsw" in indexes["ix_study_embeddings_hnsw"]
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(text("INSERT INTO studies (pmid, sample_size) VALUES ('1', 0)"))
    with database.begin() as connection:
        connection.execute(text("INSERT INTO studies (pmid) VALUES ('1')"))
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(text("INSERT INTO studies (pmid) VALUES ('1')"))


def test_import_update_delete_resume_and_embeddings(database):
    result = ingest_stream(database, io.BytesIO(XML), "fixture:base", batch_size=1)
    assert result["processed"] == 2 and result["deleted"] == 1
    assert ingest_stream(database, io.BytesIO(XML), "fixture:base")["processed"] == 2
    with database.connect() as connection:
        rows = connection.execute(select(Study).order_by(Study.pmid)).all()
        assert len(rows) == 2
        assert rows[0].is_deleted and not rows[1].is_deleted

    # The first record commits; a malformed tail interrupts the next batch.
    partial = b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>200</PMID><Article><ArticleTitle>Old</ArticleTitle></Article></MedlineCitation></PubmedArticle><bad>"
    with pytest.raises(Exception):
        ingest_stream(database, io.BytesIO(partial), "fixture:resume", batch_size=1)
    repaired = b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>200</PMID><Article><ArticleTitle>Old</ArticleTitle></Article></MedlineCitation></PubmedArticle><PubmedArticle><MedlineCitation><PMID>201</PMID><Article><ArticleTitle>New</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    assert ingest_stream(database, io.BytesIO(repaired), "fixture:resume", batch_size=1)["resumed_from"] == 1

    class Encoder:
        def get_sentence_embedding_dimension(self):
            return 384

        def encode(self, texts, **kwargs):
            class Vector(list):
                def tolist(self):
                    return list(self)
            return [Vector([float(len(value))] + [0.0] * 383) for value in texts]

    encoder = Encoder()
    assert embed_studies(database, encoder=encoder, batch_size=2)["embedded"] == 3
    assert embed_studies(database, encoder=encoder)["embedded"] == 0
    with database.begin() as connection:
        connection.execute(text("UPDATE studies SET title = 'Changed' WHERE pmid = '200'"))
    assert embed_studies(database, encoder=encoder)["embedded"] == 1
    update_xml = b"<PubmedArticleSet><DeleteCitation><PMID>200</PMID></DeleteCitation><PubmedArticle><MedlineCitation><PMID>124</PMID><Article><ArticleTitle>Amended</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    ingest_stream(database, io.BytesIO(update_xml), "fixture:update", batch_size=2)
    with database.connect() as connection:
        assert connection.scalar(select(Study.is_deleted).where(Study.pmid == "200")) is True
        assert connection.scalar(select(Study.title).where(Study.pmid == "124")) == "Amended"
        assert connection.scalar(select(StudyEmbedding.study_id).join(Study).where(Study.pmid == "200")) is None
