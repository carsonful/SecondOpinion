import pytest

from app.models.pubmed import PubMedArticle
from app.services.assessment import assess_metadata


def article(types=(), **overrides):
    values = dict(
        pmid="123", title="Example", abstract="Example abstract.", journal=None,
        year=None, authors=[], doi=None, pmc_id=None, publication_types=list(types),
        mesh_terms=[], retracted=False, url="https://pubmed.ncbi.nlm.nih.gov/123/",
    )
    return PubMedArticle(**(values | overrides))


@pytest.mark.parametrize("types,category,weight", [
    (["Randomized Controlled Trial", "Clinical Trial", "Journal Article"], "Randomized evidence", 8),
    (["Controlled Clinical Trial"], "Intervention evidence; randomization unknown", 5),
    (["Clinical Trial, Phase III"], "Intervention evidence; randomization unknown", 5),
    (["Observational Study"], "Observational evidence: subtype unknown", 3),
    (["Case Reports"], "Descriptive evidence", 1),
    (["Review"], "General review", 0),
    (["Letter"], "Commentary / inspect abstract", 0),
    (["Letter", "Randomized Controlled Trial"], "Randomized evidence", 8),
    (["Meta-Analysis", "Randomized Controlled Trial"], "Research synthesis", None),
    (["Systematic Review", "Review"], "Research synthesis", None),
    (["Randomized Controlled Trial", "Observational Study"], "Unclassified", None),
    (["Review", "Clinical Trial"], "Unclassified", None),
    (["Journal Article"], "Unclassified", None),
    ([], "Unclassified", None),
])
def test_design_defaults(types, category, weight):
    result = assess_metadata(article(types))
    assert result.category == category
    assert result.base_weight == weight
    assert result.effective_weight == 0
    assert result.eligibility == "withheld"
    assert result.finding == result.relevance == "not_assessed"


def test_retraction_preserves_design_weight():
    result = assess_metadata(article(["Randomized Controlled Trial"], retracted=True))
    assert result.base_weight == 8
    assert result.eligibility == "excluded"
    assert result.effective_weight == 0
    assert "Retracted publication" in result.flags


def test_retraction_notice_is_not_retracted_study():
    result = assess_metadata(article(["Retraction of Publication"]))
    assert result.eligibility == "withheld"
    assert "Retracted publication" not in result.flags


@pytest.mark.parametrize("types", [["Expression of Concern"], ["Published Erratum"]])
def test_integrity_notices_withheld(types):
    assert assess_metadata(article(types)).eligibility == "withheld"


@pytest.mark.parametrize("abstract", [None, "", "  "])
def test_missing_abstract_preserves_weight(abstract):
    result = assess_metadata(article(["Randomized Controlled Trial"], abstract=abstract))
    assert result.base_weight == 8
    assert "No abstract" in result.eligibility_reason
    assert result.eligibility == "withheld"


def test_animal_indexing_separate_but_humans_and_animals_not_assumed_animal_only():
    result = assess_metadata(article(mesh_terms=["Animals"]))
    assert result.eligibility == "separate"
    mixed = assess_metadata(article(mesh_terms=["Humans", "Animals"]))
    assert mixed.eligibility == "withheld"
    assert not any("Animal-only" in flag for flag in mixed.flags)


def test_preprint_separate_and_retraction_takes_precedence():
    assert assess_metadata(article(["Preprint"])).eligibility == "separate"
    result = assess_metadata(article(["Preprint", "Retracted Publication"]))
    assert result.eligibility == "excluded"


def test_age_does_not_change_weight():
    old = assess_metadata(article(["Randomized Controlled Trial"], year=1970))
    recent = assess_metadata(article(["Randomized Controlled Trial"], year=2026))
    assert old == recent
