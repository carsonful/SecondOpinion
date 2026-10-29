"""Classify study type from PubMed publication types and explicit abstract text."""

import re

from app.models.metadata import StudyDesign, StudyMetadata, StudyPopulation
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


IN_VITRO_TERMS = frozenset({"in vitro techniques", "cells, cultured", "cell culture techniques"})


def classify_population(article: PubMedArticle) -> StudyPopulation:
    """Read explicit MeSH descriptors, never infer participants from a trial tag.

    Lab descriptors take precedence: cells can be human-derived without findings
    in people. Otherwise Humans wins over Animals for mixed indexed records.
    MeSH absence is common for recent/unindexed records and means unknown.
    """
    terms = {" ".join(term.split()).casefold() for term in article.mesh_terms}
    if terms & IN_VITRO_TERMS:
        return StudyPopulation.IN_VITRO
    if "humans" in terms:
        return StudyPopulation.HUMAN
    if "animals" in terms:
        return StudyPopulation.ANIMAL
    return StudyPopulation.UNKNOWN


def extract_metadata(article: PubMedArticle) -> StudyMetadata:
    return StudyMetadata(
        design=classify_study_type(article), population=classify_population(article),
    )
