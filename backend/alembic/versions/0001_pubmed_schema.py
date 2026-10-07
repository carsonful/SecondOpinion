"""Initial claim, evidence, PubMed and embedding schema.

Revision ID: 0001_pubmed_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

revision = "0001_pubmed_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_claims_status_created_at", "claims", ["status", "created_at"])
    op.create_table(
        "studies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pmid", sa.String(32), nullable=False, unique=True),
        sa.Column("doi", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("abstract", sa.Text()),
        sa.Column("journal", sa.Text()),
        sa.Column("publication_date", sa.Date()),
        sa.Column("study_type", sa.Text()),
        sa.Column("sample_size", sa.Integer()),
        sa.Column("retraction_status", sa.String(32)),
        sa.Column("mesh_terms", JSONB()),
        sa.Column("metadata", JSONB()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sample_size > 0", name="ck_studies_sample_size_positive"),
    )
    op.create_index("ix_studies_doi", "studies", ["doi"])
    op.create_index("ix_studies_publication_date", "studies", ["publication_date"])
    op.execute("CREATE INDEX ix_studies_text_search ON studies USING gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, '')))")
    op.create_table(
        "evidence_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("quality_score", sa.Float()),
        sa.Column("recency_score", sa.Float()),
        sa.Column("final_weight", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("claim_id", "study_id", name="uq_evidence_claim_study"),
        *(sa.CheckConstraint(f"{field} BETWEEN 0 AND 1", name=f"ck_evidence_{field}")
          for field in ("relevance_score", "quality_score", "recency_score", "final_weight")),
    )
    op.create_index("ix_evidence_study_id", "evidence_scores", ["study_id"])
    op.create_table(
        "verdicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("explanation", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IN ('supported', 'refuted', 'unproven')", name="ck_verdict_outcome"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_verdict_confidence"),
    )
    op.create_table(
        "study_embeddings",
        sa.Column("study_id", sa.Integer(), sa.ForeignKey("studies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("model_revision", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("CREATE INDEX ix_study_embeddings_hnsw ON study_embeddings USING hnsw (embedding vector_cosine_ops)")
    op.create_table(
        "ingestion_checkpoints",
        sa.Column("source", sa.Text(), primary_key=True),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    for table in ("ingestion_checkpoints", "study_embeddings", "verdicts", "evidence_scores", "studies", "claims"):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
