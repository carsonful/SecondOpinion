"""Conservative, local extraction of single English health-effect claims.

Unsupported phrasing is an input error, never a judgment about evidence.
Negation describes the user's assertion; retrieval intentionally searches both
sides of it. Extend the vocabulary/rules alongside regression fixtures.
"""

import logging
import re
import unicodedata

from app.models.normalization import NormalizedClaim

logger = logging.getLogger(__name__)


class ClaimNormalizationError(ValueError):
    """Input is non-health, malformed, or outside the supported grammar."""


# These identify health topics, not whether a claim is plausible or true.
_HEALTH = re.compile(
    r"\b(colds?|cancer|autism|diabetes|sleep|insomnia|anxiety|depression|"
    r"pain|headaches?|migraine|blood pressure|cholesterol|weight|obesity|"
    r"heart disease|stroke|infection|flu|influenza|immunity|immune system|"
    r"bone health|osteoporosis|acne|fertility|dementia|mortality|health|"
    r"digestion|dehydration|arthritis|asthma|allergies|covid(?:-19)?)\b"
)
_RELATIONS = (
    r"causes?|prevents?|cures?|treats?|reduces?|increases?|improves?|"
    r"worsens?|affects?|helps?(?: with)?|lowers?|raises?|"
    r"protects? against|leads? to|is associated with|are associated with"
)
_EFFECT = re.compile(
    rf"^(?P<intervention>.+?)\s+"
    rf"(?:(?:does|do|did|can|will|may|might)\s+)?"
    rf"(?P<negation>not\s+|never\s+)?(?P<relation>{_RELATIONS})\s+"
    rf"(?P<outcome>.+)$"
)
_POPULATION = re.compile(
    r"\s+(?:in|among|for)\s+(?P<population>(?:(?:healthy|older|young|pregnant|"
    r"breastfeeding|adult)\s+)?(?:adults|children|kids|infants|babies|"
    r"teenagers|adolescents|women|men|people|patients|humans|mice|rats)"
    r"(?:\s+(?:with|aged|over|under)\s+.+)?)$"
)
_ALIASES = {"colds": "common cold", "cold": "common cold", "kids": "children"}


def _term(value: str) -> str:
    value = re.sub(r"^(?:the|a|an)\s+", "", value.strip())
    return _ALIASES.get(value, value)


def _extract(raw_text: str) -> NormalizedClaim:
    if not raw_text.strip() or len(raw_text) > 2000:
        raise ClaimNormalizationError("Enter one health claim of 1–2000 characters")
    text = unicodedata.normalize("NFKC", raw_text).lower().replace("’", "'")
    for contraction, expanded in {
        "doesn't": "does not", "don't": "do not", "didn't": "did not",
        "can't": "can not", "cannot": "can not", "won't": "will not",
    }.items():
        text = re.sub(rf"\b{re.escape(contraction)}\b", expanded, text)
    if "\n" in text.strip():
        raise ClaimNormalizationError("Enter a single, simple health-effect claim")
    text = re.sub(r"\s+", " ", text).strip().rstrip("?!. ")
    text = re.sub(r"\s+(?:lol|lmao|pls|please)$", "", text).rstrip("?!. ")
    text = re.sub(r"^(?:does|do|did|can|will|may|might)\s+", "", text)
    if not _HEALTH.search(text):
        raise ClaimNormalizationError("Input must describe a health outcome")
    # Boolean operators and multiple clauses must not become retrieval syntax.
    if re.search(r'[;."\[\]()!?]|\b(?:and|or|but|unless|if)\b', text):
        raise ClaimNormalizationError("Enter a single, simple health-effect claim")
    population_match = _POPULATION.search(text)
    population = None
    if population_match:
        population = _term(population_match["population"])
        text = text[:population_match.start()]
    match = _EFFECT.fullmatch(text)
    if not match:
        raise ClaimNormalizationError("Could not extract an intervention and health outcome")
    intervention, outcome = _term(match["intervention"]), _term(match["outcome"])
    # Do not silently reinterpret negation embedded in a noun phrase or a
    # second effect clause (e.g. 'no exercise', 'does not fail to prevent').
    ambiguous_words = r"\b(?:no|not|never|without|does|do|did|can|will|may|might)\b"
    if re.search(ambiguous_words, intervention + " " + outcome) or re.search(
        rf"\b(?:{_RELATIONS})\b", outcome
    ):
        raise ClaimNormalizationError("Ambiguous claim; simplify its wording")
    if not _HEALTH.search(outcome):
        raise ClaimNormalizationError("Could not identify a health outcome")
    terms = [intervention, outcome]
    if population:
        terms.append(population)
    # Quoted terms cannot inject Boolean operators. No NOT restriction: studies
    # finding either an effect or no effect must remain discoverable.
    query = " AND ".join(f'"{term}"' for term in terms)
    return NormalizedClaim(
        query=query, intervention=intervention, outcome=outcome,
        population=population, relation=match["relation"],
        negated=bool(match["negation"]),
    )


def normalize_claim(raw_text: str) -> NormalizedClaim:
    """Extract a searchable claim and log every accepted/rejected invocation."""
    try:
        result = _extract(raw_text)
    except ClaimNormalizationError as exc:
        logger.info("claim_normalization", extra={
            "raw_input": raw_text, "normalized_output": None, "error": str(exc),
        })
        raise
    logger.info("claim_normalization", extra={
        "raw_input": raw_text, "normalized_output": result.model_dump(), "error": None,
    })
    return result
