"""Database schema. Alembic migrations, rather than create_all, own its lifecycle."""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, create_engine, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_claims_status_created_at", "status", "created_at"),)


class Study(Base):
    __tablename__ = "studies"
    id: Mapped[int] = mapped_column(primary_key=True)
    pmid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    doi: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    journal: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    study_type: Mapped[str | None] = mapped_column(Text)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    retraction_status: Mapped[str | None] = mapped_column(String(32))
    mesh_terms: Mapped[list | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("sample_size > 0", name="ck_studies_sample_size_positive"),
        Index("ix_studies_doi", "doi"),
        Index("ix_studies_publication_date", "publication_date"),
        Index("ix_studies_text_search", text(
            "to_tsvector('english'::regconfig, (COALESCE(title, ''::text) || ' '::text) || COALESCE(abstract, ''::text))"),
            postgresql_using="gin"),
    )


class EvidenceScore(Base):
    __tablename__ = "evidence_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)
    recency_score: Mapped[float | None] = mapped_column(Float)
    final_weight: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("claim_id", "study_id", name="uq_evidence_claim_study"),
        Index("ix_evidence_study_id", "study_id"),
        *(CheckConstraint(f"{field} BETWEEN 0 AND 1", name=f"ck_evidence_{field}")
          for field in ("relevance_score", "quality_score", "recency_score", "final_weight")),
    )


class Verdict(Base):
    __tablename__ = "verdicts"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, unique=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("outcome IN ('supported', 'refuted', 'unproven')", name="ck_verdict_outcome"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_verdict_confidence"),
    )


class StudyEmbedding(Base):
    __tablename__ = "study_embeddings"
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_study_embeddings_hnsw", "embedding",
                            postgresql_using="hnsw",
                            postgresql_ops={"embedding": "vector_cosine_ops"}),)


class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoints"
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deleted: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)
