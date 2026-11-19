"""Population labels are indexed source metadata, not guesses from study design."""

import pytest
from pydantic import ValidationError

from app.models.metadata import StudyDesign, StudyMetadata, StudyPopulation
from app.services.metadata import classify_population, extract_metadata
from app.services.pubmed import parse_efetch_xml
from tests.helpers import load_fixture


@pytest.fixture
def article():
    return parse_efetch_xml(load_fixture("pubmed/efetch_zinc_cold.xml"))[0]


@pytest.mark.parametrize(("terms", "expected"), [
    (["Humans"], "human"),
    (["Animals"], "animal"),
    (["Animals", "Humans"], "human"),
    (["Humans", "Animals"], "human"),
    (["In Vitro Techniques"], "in_vitro"),
    (["Cells, Cultured"], "in_vitro"),
    (["Cell Culture Techniques"], "in_vitro"),
    (["Humans", "Cells, Cultured"], "in_vitro"),
    (["Animals", "In Vitro Techniques"], "in_vitro"),
    (["Animals", "Humans", "Cells, Cultured"], "in_vitro"),
    (["  hUMaNs  "], "human"),
    ([" ANIMALS "], "animal"),
    (["In  Vitro\tTechniques"], "in_vitro"),
    (["Humans", "Humans"], "human"),
    ([], "unknown"),
    ([""], "unknown"),
    (["Mice"], "unknown"),
    (["Zinc", "Common Cold"], "unknown"),
    (["Nonhuman"], "unknown"),
    (["Animal Experimentation"], "unknown"),
])
def test_explicit_mesh_classification(article, terms, expected):
    article.mesh_terms = terms
    assert classify_population(article) == expected
    assert extract_metadata(article).population == expected


@pytest.mark.parametrize("design", [
    "Randomized Controlled Trial", "Clinical Trial", "Observational Study",
    "Systematic Review", "Meta-Analysis", "Review", "Case Reports", "Editorial",
])
def test_design_does_not_imply_people(article, design):
    article.publication_types = [design]
    article.mesh_terms = []
    article.title = "A study in humans"
    article.abstract = "Human volunteers participated in this study."
    assert extract_metadata(article).population == StudyPopulation.UNKNOWN


def test_recorded_animal_trial_keeps_design_and_population_separate():
    (animal,) = parse_efetch_xml(load_fixture("pubmed/efetch_animal_trial.xml"))
    assert animal.pmid == "42907999"
    assert "Animals" in animal.mesh_terms
    assert "Humans" not in animal.mesh_terms
    assert "Randomized Controlled Trial" in animal.publication_types
    metadata = extract_metadata(animal)
    assert metadata.design == StudyDesign.RANDOMIZED_TRIAL
    assert metadata.population == StudyPopulation.ANIMAL
    assert metadata.model_dump(mode="json") == {
        "design": "randomized_controlled_trial", "population": "animal",
    }


def test_existing_human_fixture_is_labeled_from_mesh(article):
    assert "Humans" in article.mesh_terms
    assert extract_metadata(article).population == "human"


def test_backward_compatible_metadata_does_not_invent_participants():
    metadata = StudyMetadata.model_validate({"design": "cohort"})
    assert metadata.population == "unknown"


@pytest.mark.parametrize("population", ["mouse", "people", "", None])
def test_population_contract_rejects_unsupported_labels(population):
    with pytest.raises(ValidationError):
        StudyMetadata(design="unknown", population=population)


def test_classifier_does_not_mutate_source(article):
    article.mesh_terms = [" Humans ", "Animals", "Humans"]
    original = article.model_copy(deep=True)
    extract_metadata(article)
    assert article == original
