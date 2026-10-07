"""Independent, resumable CPU embedding job for PubMed titles and abstracts."""

import hashlib
import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import Study, StudyEmbedding

LOG = logging.getLogger(__name__)
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def content_text(title: str | None, abstract: str | None) -> str:
    return "\n\n".join(part.strip() for part in (title, abstract) if part and part.strip())


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_studies(engine, model_id: str = DEFAULT_MODEL, revision: str = DEFAULT_REVISION,
                  batch_size: int = 64, limit: int | None = None, encoder=None) -> dict:
    if batch_size < 1 or (limit is not None and limit < 1):
        raise ValueError("batch_size and limit must be positive")
    if encoder is None:
        from sentence_transformers import SentenceTransformer
        encoder = SentenceTransformer(model_id, revision=revision, device="cpu")
    get_dimension = getattr(encoder, "get_embedding_dimension", None)
    dimension = get_dimension() if get_dimension else encoder.get_sentence_embedding_dimension()
    if dimension != 384:
        raise ValueError("The current pgvector column requires 384-dimensional embeddings")
    last_id = 0
    scanned = embedded = skipped = 0
    while True:
        with engine.connect() as connection:
            rows = connection.execute(
                select(Study.id, Study.title, Study.abstract,
                       StudyEmbedding.content_hash, StudyEmbedding.model_id,
                       StudyEmbedding.model_revision)
                .outerjoin(StudyEmbedding, Study.id == StudyEmbedding.study_id)
                .where(Study.id > last_id, Study.is_deleted.is_(False))
                .order_by(Study.id).limit(batch_size)
            ).all()
        if not rows:
            break
        last_id = rows[-1].id
        scanned += len(rows)
        work = []
        for row in rows:
            content = content_text(row.title, row.abstract)
            if not content:
                skipped += 1
                continue
            digest = content_hash(content)
            if row.content_hash == digest and row.model_id == model_id and row.model_revision == revision:
                skipped += 1
                continue
            work.append((row.id, content, digest))
        if limit is not None:
            work = work[:limit - embedded]
        if work:
            vectors = encoder.encode([item[1] for item in work], batch_size=batch_size,
                                     convert_to_numpy=True, normalize_embeddings=True,
                                     show_progress_bar=False)
            with engine.begin() as connection:
                current = {row.id: content_hash(content_text(row.title, row.abstract)) for row in
                           connection.execute(select(Study.id, Study.title, Study.abstract)
                                              .where(Study.id.in_([item[0] for item in work]),
                                                     Study.is_deleted.is_(False))).all()}
                values = []
                for (study_id, _, digest), vector in zip(work, vectors):
                    if current.get(study_id) == digest:
                        values.append({"study_id": study_id, "embedding": vector.tolist(),
                                       "model_id": model_id, "model_revision": revision,
                                       "content_hash": digest})
                if values:
                    statement = insert(StudyEmbedding).values(values)
                    connection.execute(statement.on_conflict_do_update(
                        index_elements=[StudyEmbedding.study_id], set_={
                            "embedding": statement.excluded.embedding,
                            "model_id": statement.excluded.model_id,
                            "model_revision": statement.excluded.model_revision,
                            "content_hash": statement.excluded.content_hash,
                            "embedded_at": func.now(),
                        }))
                    embedded += len(values)
        LOG.info("Embedding progress: scanned=%d embedded=%d skipped=%d", scanned, embedded, skipped)
        if limit is not None and embedded >= limit:
            break
    return {"scanned": scanned, "embedded": embedded, "skipped": skipped}
