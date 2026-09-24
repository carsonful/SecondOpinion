import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Claim


@dataclass(frozen=True)
class ClaimMatch:
    claim: Claim
    score: float
    exact: bool


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    without_punctuation = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return " ".join(without_punctuation.split())


def find_matching_claim(
    session: Session,
    text: str,
    threshold: float = 0.6,
) -> ClaimMatch | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    exact_claim = session.scalars(
        select(Claim)
        .where(Claim.normalized_text == normalized)
        .order_by(Claim.id)
        .limit(1)
    ).first()
    if exact_claim is not None:
        return ClaimMatch(claim=exact_claim, score=1.0, exact=True)

    similarity = func.similarity(Claim.normalized_text, normalized)
    row = session.execute(
        select(Claim, similarity.label("score"))
        .where(similarity >= threshold)
        .order_by(similarity.desc(), Claim.id)
        .limit(1)
    ).first()
    if row is None:
        return None

    claim, score = row
    return ClaimMatch(claim=claim, score=float(score), exact=False)
