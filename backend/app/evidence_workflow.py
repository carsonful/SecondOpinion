"""Small functions to fill in independently as the team builds the workflow.

Normalization calls Azure Foundry; base design weighting uses versioned rules.
Claim assessment, effective contributions, and verdicts remain unimplemented.
Verdicts only accept evidence that passed the integrity gate in services/integrity.py.
See docs/evidence-grading.md for the provisional grading rules.
"""

from collections.abc import Sequence

from app.evidence_models import Claim, EvidenceScore, Study, Verdict
from app.services.integrity import AdmittedEvidence, require_admitted
from app.services.normalization import normalize_claim as normalize_search_claim
from app.services.weighting import get_design_weight


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
    """Record a provisional base weight from an already resolved study design.

    `study_type` must be a canonical StudyDesign value from metadata extraction
    (#14), not a raw PubMed publication type. Missing/unrecognized values remain
    unknown. This does not establish relevance, findings, or eligibility;
    final_weight remains None until those assessments are implemented.
    """
    weight = get_design_weight(
        study.study_type, included_design=study.synthesis_included_design,
    )
    return EvidenceScore(
        claim_id=claim.id, study_id=study.id,
        component_scores={"base_weight": weight.base_weight},
        weight_version=weight.version,
        resolved_design=weight.resolved_design,
        weighted_design=weight.weighted_design,
        weight_reason=weight.reason,
    )


def generate_verdict(claim: Claim, evidence: Sequence[AdmittedEvidence]) -> Verdict:
    """TODO: summarize assessed findings using team-approved verdict rules.

    `evidence` must be GateResult.admitted from apply_integrity_gate(), so retracted
    and withheld studies can never reach this function (#19). Keep the
    require_admitted() check below as the first line when implementing this.

    Reject scores for other claims. Weights alone cannot establish an outcome
    or confidence; extend these inputs with findings and citations first.
    Unimplemented analysis must not be returned as an 'unproven' verdict.
    """
    require_admitted(evidence)
    raise NotImplementedError("Verdict generation is not implemented yet")
