from app.services.cache import canonical_claim_key
from app.services.durable_cache import cache_key


def test_claim_key_preserves_existing_case_and_spacing_behavior():
    assert canonical_claim_key("  Does  ZINC cure colds?  ") == "does zinc cure colds?"


def test_digest_has_distinct_layers_and_limits_without_raw_text():
    raw = canonical_claim_key("Does zinc cure colds?")
    normalized = cache_key("normalized", raw)
    candidates = cache_key("candidates", "(zinc) AND (common cold)", 20)

    assert len(normalized) == 64
    assert raw not in normalized
    assert normalized != candidates
    assert candidates != cache_key("candidates", "(zinc) AND (common cold)", 10)
    assert candidates == cache_key("candidates", "(zinc) AND (common cold)", 20)
