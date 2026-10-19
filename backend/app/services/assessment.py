"""Implement metadata rules from docs/evidence-grading.md.

Weights describe provisional design defaults for human intervention effects,
not quality ratings or confidence. No abstract assessment or aggregation yet.
"""

from app.models.assessment import StudyAssessment
from app.models.pubmed import PubMedArticle

BASE_WEIGHTS = {
    "Randomized evidence": 8,
    "Intervention evidence; randomization unknown": 5,
    "Observational evidence: subtype unknown": 3,
    "Descriptive evidence": 1,
    "General review": 0,
    "Commentary / inspect abstract": 0,
    "Research synthesis": None,
    "Unclassified": None,
}


def classify_design(types: set[str]) -> str:
    # Reviews may also carry trial tags; those do not establish included designs.
    if types & {"systematic review", "meta-analysis"}:
        return "Research synthesis"
    designs = []
    if "randomized controlled trial" in types:
        designs.append("Randomized evidence")
    elif types & {"clinical trial", "controlled clinical trial"} or any(
        tag.startswith("clinical trial, phase ") for tag in types
    ):
        designs.append("Intervention evidence; randomization unknown")
    if "observational study" in types:
        designs.append("Observational evidence: subtype unknown")
    if "case reports" in types:
        designs.append("Descriptive evidence")
    if len(designs) > 1 or (designs and "review" in types):
        return "Unclassified"
    if designs:
        return designs[0]
    if "review" in types:
        return "General review"
    if types & {"editorial", "comment", "letter"}:
        return "Commentary / inspect abstract"
    return "Unclassified"


def assess_metadata(article: PubMedArticle) -> StudyAssessment:
    types = {tag.strip().casefold() for tag in article.publication_types}
    mesh = {tag.strip().casefold() for tag in article.mesh_terms}
    category = classify_design(types)
    flags = []
    retracted = article.retracted or "retracted publication" in types
    relations = {link.relation for link in article.integrity_links}
    linked_issue = bool(relations & {"ErratumIn", "ExpressionOfConcernIn"})
    notice = bool(types & {"retraction of publication", "expression of concern", "published erratum"}) or bool(relations & {"RetractionOf", "ErratumFor", "ExpressionOfConcernFor"})
    preclinical = "animals" in mesh and "humans" not in mesh
    preprint = "preprint" in types
    missing_abstract = not article.abstract or not article.abstract.strip()
    if retracted:
        flags.append("Retracted publication")
    if notice:
        flags.append("Integrity notice; inspect linked article")
    if "ErratumIn" in relations:
        flags.append("Linked correction: impact not yet reviewed")
    if "ExpressionOfConcernIn" in relations:
        flags.append("Linked expression of concern: unresolved")
    if preclinical:
        flags.append("Animal-only indexing; confirm population from abstract")
    if preprint:
        flags.append("Preprint")
    if missing_abstract:
        flags.append("Limited information: abstract unavailable")
    if category == "Unclassified":
        flags.append("Study design unresolved")
    if category == "Research synthesis":
        flags.append("Included designs and overlap need assessment")

    eligibility = "withheld"
    reason = "Relevance and findings have not been assessed."
    if retracted:
        eligibility, reason = "excluded", "Retracted findings are excluded from synthesis."
    elif notice:
        reason = "This record is an integrity notice; the affected article needs review."
    elif linked_issue:
        reason = "Linked correction or concern requires review before findings can contribute to synthesis."
    elif preclinical or preprint:
        eligibility = "separate"
        reason = "Keep preclinical evidence or preprints separate from the main human-evidence comparison."
    elif missing_abstract:
        reason = "No abstract is available to assess relevance or findings."
    elif category in {"Unclassified", "Research synthesis"}:
        reason = "Design weight is unresolved; relevance and findings also need assessment."

    return StudyAssessment(
        pmid=article.pmid, category=category, base_weight=BASE_WEIGHTS[category],
        eligibility=eligibility, eligibility_reason=reason, flags=flags,
    )
