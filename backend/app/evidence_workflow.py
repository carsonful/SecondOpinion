"""Small functions to fill in independently as the team builds the workflow.

No API calls, persistence, or route changes are wired up here.
See docs/evidence-grading.md for the provisional grading rules.
"""

from collections.abc import Sequence

from app.evidence_models import Claim, EvidenceScore, Study, Verdict
from app.services.normalization import normalize_claim as normalize_search_claim


def create_claim(raw_text: str) -> Claim:
    """Create a pending claim in memory, preserving the user's original text."""
    if not raw_text.strip():
        raise ValueError("Claim text must not be blank")
    return Claim(raw_text=raw_text)


def normalize_claim(raw_text: str) -> str:
    """Return a retrieval query; use the service directly for structured fields.

    The caller will save the returned string in Claim.normalized_query.
    """
    return normalize_search_claim(raw_text).query


def score_study(claim: Claim, study: Study) -> EvidenceScore:
    """TODO: assess one study for one claim and return their linked score.

    Keep design weight separate from eligibility. Preserve unknown values,
    record the rule version, and explain excluded or withheld evidence.
    Add inputs for abstracts/findings when that retrieval contract is agreed.
    """
    raise NotImplementedError("Evidence scoring is not implemented yet")


def generate_verdict(claim: Claim, scores: Sequence[EvidenceScore]) -> Verdict:
    """TODO: summarize assessed findings using team-approved verdict rules.

    Reject scores for other claims. Weights alone cannot establish an outcome
    or confidence; extend these inputs with findings and citations first.
    Unimplemented analysis must not be returned as an 'unproven' verdict.
    """
    raise NotImplementedError("Verdict generation is not implemented yet")
