"""Classify study type from PubMed publication types and explicit abstract text."""

import re

from app.models.metadata import StudyDesign, StudyMetadata
from app.models.pubmed import PubMedArticle


def classify_study_type(article: PubMedArticle) -> StudyDesign:
    tags = {tag.strip().casefold() for tag in article.publication_types}
    if tags & {"systematic review", "meta-analysis"}:
        return StudyDesign.SYNTHESIS
    if "randomized controlled trial" in tags:
        return StudyDesign.RANDOMIZED_TRIAL
    if tags & {"clinical trial", "controlled clinical trial", "clinical trial, phase i", "clinical trial, phase ii", "clinical trial, phase iii", "clinical trial, phase iv"}:
        return StudyDesign.INTERVENTION
    if "observational study" in tags:
        subtypes = set(re.findall(
            r"\b(?:this|our|we conducted a|we performed a)\s+"
            r"(?:(?:prospective|retrospective|population-based|matched)\s+)*"
            r"(cohort|case-control|cross-sectional)\s+study\b",
            article.abstract or "", re.I,
        ))
        if len(subtypes) == 1:
            return {
                "cohort": StudyDesign.COHORT,
                "case-control": StudyDesign.CASE_CONTROL,
                "cross-sectional": StudyDesign.CROSS_SECTIONAL,
            }[next(iter(subtypes)).casefold()]
        return StudyDesign.OBSERVATIONAL
    if "case reports" in tags:
        return StudyDesign.DESCRIPTIVE
    if "review" in tags:
        return StudyDesign.GENERAL_REVIEW
    if tags & {"editorial", "comment"}:
        return StudyDesign.COMMENTARY
    return StudyDesign.UNKNOWN


def extract_metadata(article: PubMedArticle) -> StudyMetadata:
    return StudyMetadata(design=classify_study_type(article))
