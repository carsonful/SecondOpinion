import pytest
from sqlalchemy.orm import Session

from app.matching import find_matching_claim, normalize_text
from app.models import Claim


@pytest.mark.parametrize(
    "text",
    [
        "Vitamin C cures colds!",
        "  Vitamin   C cures colds  ",
        "VITAMIN C CURES COLDS",
    ],
)
def test_normalize_text_produces_consistent_text(text: str) -> None:
    assert normalize_text(text) == "vitamin c cures colds"


def test_normalize_text_handles_unicode_punctuation_and_whitespace() -> None:
    assert normalize_text("  Caf\u00e9\u2014helps\t digestion... ") == "caf\u00e9 helps digestion"


def test_normalize_text_normalizes_unicode_width() -> None:
    assert normalize_text("\uff36\uff49\uff54\uff41\uff4d\uff49\uff4e \uff23") == "vitamin c"


def add_claim(session: Session, text: str) -> Claim:
    claim = Claim(text=text, normalized_text=normalize_text(text))
    session.add(claim)
    session.commit()
    return claim


def test_finds_exact_claim(database_session: Session) -> None:
    claim = add_claim(database_session, "Vitamin C cures colds!")

    result = find_matching_claim(database_session, "VITAMIN C CURES COLDS")

    assert result is not None
    assert result.claim.id == claim.id
    assert result.score == 1.0
    assert result.exact is True


def test_finds_close_claim(database_session: Session) -> None:
    claim = add_claim(database_session, "Vitamin C prevents the common cold")

    result = find_matching_claim(
        database_session,
        "does vitamin c prevent common colds",
        threshold=0.4,
    )

    assert result is not None
    assert result.claim.id == claim.id
    assert result.score >= 0.4
    assert result.exact is False


def test_does_not_match_unrelated_claim(database_session: Session) -> None:
    add_claim(database_session, "Vitamin C prevents the common cold")

    result = find_matching_claim(
        database_session,
        "Regular exercise can improve sleep quality",
        threshold=0.6,
    )

    assert result is None
