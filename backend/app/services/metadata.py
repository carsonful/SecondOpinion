"""Deterministic metadata extraction; unresolved information stays unknown.

Design classification uses indexed publication types and explicit observational
self-descriptions, not generic topic mentions.
Sample size requires an explicit total participant statement in the abstract.
No AI calls, inferred group sums, or review participant totals are used.
"""

import re

from app.models.metadata import StudyMetadata
from app.models.pubmed import PubMedArticle
from app.services.weighting import StudyDesign


def resolve_design(publication_types: list[str]) -> tuple[StudyDesign, str]:
    tags = {tag.strip().casefold() for tag in publication_types}
    if tags & {"systematic review", "meta-analysis"}:
        return StudyDesign.SYNTHESIS, "Indexed as a research synthesis; included designs are unresolved."
    designs = set()
    if "randomized controlled trial" in tags:
        designs.add(StudyDesign.RANDOMIZED_TRIAL)
    elif tags & {"clinical trial", "controlled clinical trial", "clinical trial, phase i", "clinical trial, phase ii", "clinical trial, phase iii", "clinical trial, phase iv"}:
        designs.add(StudyDesign.INTERVENTION)
    if "observational study" in tags:
        designs.add(StudyDesign.OBSERVATIONAL)
    if "case reports" in tags:
        designs.add(StudyDesign.DESCRIPTIVE)
    if len(designs) > 1:
        return StudyDesign.UNKNOWN, "Conflicting indexed study designs; abstract review is needed."
    if designs:
        return designs.pop(), "Resolved from indexed publication types; generic format tags do not override a study design."
    if "review" in tags:
        return StudyDesign.GENERAL_REVIEW, "Indexed as Review without a systematic review or meta-analysis tag."
    # Letters can report original data; format alone does not establish commentary.
    if "editorial" in tags or "comment" in tags:
        return StudyDesign.COMMENTARY, "Indexed as editorial/commentary without an indexed primary study design."
    return StudyDesign.UNKNOWN, "Publication types do not establish a study design."


_NUMBER = r"([1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?![\d,]|\.\d)"
_PEOPLE = r"(?:participants|patients|subjects|volunteers|adults|children|people|individuals)"
_TOTALS = [
    re.compile(r"\b(?:we\s+)?(?:enrolled|recruited|randomized|randomised)\s+(?:a total of\s+)?" + _NUMBER + r"\s+" + _PEOPLE + r"\b", re.I),
    re.compile(r"\b(?:a total of\s+)?" + _NUMBER + r"\s+" + _PEOPLE + r"\s+(?:were|was)\s+(?:enrolled|recruited|randomized|randomised)\b", re.I),
    re.compile(r"\b(?:total sample size|total enrollment|total enrolment)\s*(?:was|of|=|:)\s*" + _NUMBER + r"\b", re.I),
]
_AMBIGUOUS = re.compile(
    r"\b(?:per (?:treatment )?group|each (?:treatment )?group|each arm|per arm|planned|aimed|target|will|would|previous|prior|other studies|excluded|not enrolled|not recruited)\b",
    re.I,
)


def extract_metadata(article: PubMedArticle) -> StudyMetadata:
    design, reason = resolve_design(article.publication_types)
    design_evidence = None
    # Only refine confirmed observational evidence; do not infer a design from
    # research discussed in a review or generic topic mentions.
    if design == StudyDesign.OBSERVATIONAL:
        subtypes = {}
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", article.abstract or ""):
            for match in re.finditer(
                r"\b(?:this|our|we conducted a|we performed a)\s+"
                r"(?:(?:prospective|retrospective|population-based|matched)\s+)*"
                r"(cohort|case-control|cross-sectional)\s+study\b", sentence, re.I,
            ):
                subtypes[match.group(1).casefold()] = sentence.strip()
        if len(subtypes) == 1:
            subtype, design_evidence = next(iter(subtypes.items()))
            design = {"cohort": StudyDesign.COHORT, "case-control": StudyDesign.CASE_CONTROL,
                      "cross-sectional": StudyDesign.CROSS_SECTIONAL}[subtype]
            reason = "Indexed observational evidence with an explicit self-description of its subtype in the abstract."
        elif subtypes:
            design, reason = StudyDesign.UNKNOWN, "Conflicting observational subtype descriptions in the abstract."
    mesh = {tag.casefold() for tag in article.mesh_terms}
    animal_only = "animals" in mesh and "humans" not in mesh
    sample_size, evidence = None, None
    sample_reason = "No unambiguous total participant count was found."
    if design in (StudyDesign.SYNTHESIS, StudyDesign.GENERAL_REVIEW, StudyDesign.COMMENTARY):
        sample_reason = "Participant totals are not extracted from reviews or commentary."
    elif animal_only:
        sample_reason = "Animal-only evidence is not assigned a human participant count."
    else:
        matches = []
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", article.abstract or ""):
            if _AMBIGUOUS.search(sentence):
                continue
            for pattern in _TOTALS:
                for match in pattern.finditer(sentence):
                    matches.append((int(match.group(1).replace(",", "")), sentence.strip()))
        counts = {count for count, _ in matches}
        if len(counts) == 1:
            sample_size, evidence = matches[0]
            sample_reason = "Explicit total enrollment/recruitment statement in the abstract."
        elif counts:
            sample_reason = "Conflicting participant totals in the abstract; count remains unknown."
    return StudyMetadata(
        design=design, design_reason=reason, design_evidence=design_evidence, sample_size=sample_size,
        sample_size_evidence=evidence, sample_size_reason=sample_reason,
        animal_only=animal_only,
    )
