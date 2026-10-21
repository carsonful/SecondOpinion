import json

import pytest

from app.services.id_converter import parse_idconv
from app.services.http_retry import UpstreamError
from app.services.jats_parser import (
    FullTextParseError,
    classify_heading,
    normalize_license,
    parse_bioc,
    parse_jats,
)
from tests.helpers import load_fixture


@pytest.mark.parametrize("heading,expected", [
    ("Materials and Methods", "methods"),
    ("2. Materials and methods", "methods"),
    ("METHODS", "methods"),
    ("Patients and Methods", "methods"),
    ("Study design and participants", "methods"),
    ("Statistical analysis", "methods"),
    ("Results", "results"),
    ("Results and Discussion", "results"),
    ("3.2 Main findings", "results"),
    ("Discussion", "discussion"),
    ("Conclusions", "discussion"),
    ("Strengths and limitations", "limitations"),
    ("Limitations of the study", "limitations"),
    ("Introduction", "introduction"),
    ("Background", "introduction"),
    ("Abstract", "abstract"),
    ("Acknowledgements", "other"),
    ("Zinc lozenges", "other"),
    (None, "other"),
    ("", "other"),
])
def test_classify_heading(heading, expected):
    assert classify_heading(heading) == expected


def test_jats_sections_are_labeled_in_order():
    sections, license_id = parse_jats(load_fixture("full_text/europepmc_fulltext.xml"))

    assert [(s.type, s.heading) for s in sections] == [
        ("abstract", "Abstract"),
        ("introduction", "1. Introduction"),
        ("methods", "2. Materials and Methods"),
        ("results", "3. Results"),
        ("discussion", "4. Discussion"),
        ("limitations", "4.1. Strengths and limitations"),
        ("discussion", "4. Discussion"),
        ("discussion", "5. Conclusions"),
    ]
    assert license_id == "cc-by"


def test_jats_text_keeps_content_and_drops_back_matter():
    sections, _ = parse_jats(load_fixture("full_text/europepmc_fulltext.xml"))
    by_type = {}
    for section in sections:
        by_type.setdefault(section.type, []).append(section.text)
    text = "\n".join(s.text for s in sections)

    assert "Background\nRaw milk is claimed" in by_type["abstract"][0]
    assert "Graphical abstract" not in text
    # Subsections stay inside their parent, with their headings inline.
    assert "2.1. Participants\nWe enrolled 120 adults aged 18 to 65." in by_type["methods"][0]
    assert "Statistical analysis" in by_type["methods"][0]
    # Tables and figure captions are kept as text.
    assert "Table 1\nSymptom scores by milk type" in by_type["results"][0]
    assert "Raw | 4.1 |" in by_type["results"][0]
    assert "Flow of participants." in by_type["results"][0]
    assert by_type["limitations"] == ["Participants were not blinded to milk taste."]
    assert "4.2. Comparison with other studies" in by_type["discussion"][1]
    for excluded in ("Cited background study", "We thank the participants", "Supplementary data"):
        assert excluded not in text


def test_jats_body_outside_sections_is_other():
    content = b"<article><front><article-meta><abstract><p>Short.</p></abstract></article-meta></front>" \
              b"<body><p>A letter with no sections.</p></body></article>"
    sections, license_id = parse_jats(content)
    assert [(s.type, s.heading, s.text) for s in sections] == [
        ("abstract", "Abstract", "Short."), ("other", None, "A letter with no sections."),
    ]
    assert license_id is None


def test_jats_inside_a_wrapper_is_found():
    content = b"<pmc-articleset><article><body><sec><title>Results</title><p>X.</p></sec></body></article></pmc-articleset>"
    sections, _ = parse_jats(content)
    assert [(s.type, s.text) for s in sections] == [("results", "X.")]


@pytest.mark.parametrize("content", [b"<article><body>", b"<resultList/>", b"not xml"])
def test_jats_unusable_content_raises(content):
    with pytest.raises(FullTextParseError):
        parse_jats(content)


def test_bioc_sections_match_jats_structure():
    sections, license_id = parse_bioc(load_fixture("full_text/bioc.json"))

    assert [(s.type, s.heading) for s in sections] == [
        ("abstract", "Abstract"),
        ("introduction", "1. Introduction"),
        ("methods", "2. Materials and Methods"),
        ("results", "3. Results"),
        ("discussion", "4. Discussion"),
        ("limitations", "4.1. Strengths and limitations"),
        ("discussion", "4.2. Comparison with other studies"),
    ]
    assert license_id == "cc-by"
    by_type = {s.type: s.text for s in sections}
    assert by_type["abstract"] == "Background\nRaw milk is claimed to be better tolerated than pasteurized milk."
    assert by_type["methods"] == "2.1. Participants\nWe enrolled 120 adults aged 18 to 65."
    assert "Symptom scores by milk type" in by_type["results"]
    assert by_type["limitations"] == "Participants were not blinded to milk taste."
    assert all("Cited background" not in s.text for s in sections)


def test_bioc_accepts_a_collection_object():
    payload = json.loads(load_fixture("full_text/bioc.json"))[0]
    sections, _ = parse_bioc(json.dumps(payload).encode())
    assert sections[0].type == "abstract"


@pytest.mark.parametrize("content", [b"[]", b"{}", b"not json", b'[{"documents": []}]'])
def test_bioc_unusable_content_raises(content):
    with pytest.raises(FullTextParseError):
        parse_bioc(content)


@pytest.mark.parametrize("value,expected", [
    ("https://creativecommons.org/licenses/by/4.0/", "cc-by"),
    ("http://creativecommons.org/licenses/by-nc-nd/3.0/", "cc-by-nc-nd"),
    ("https://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
    ("CC BY", "cc-by"),
    ("CC BY-NC", "cc-by-nc"),
    ("This is an open access article under the Creative Commons Attribution License", "cc-by"),
    ("All rights reserved", None),
    (None, None),
])
def test_normalize_license(value, expected):
    assert normalize_license(value) == expected


def test_idconv_maps_known_ids_and_skips_errors():
    ids = parse_idconv(load_fixture("full_text/idconv.json"))
    assert set(ids) == {"99000001", "99000002"}
    assert ids["99000001"].pmcid == "PMC9900001"
    assert ids["99000001"].doi == "10.5555/so.0001"
    assert ids["99000002"].pmcid is None
    assert ids["99000002"].doi == "10.5555/so.0002"


@pytest.mark.parametrize("content", [b"not json", b"{}", b'{"records": "x"}'])
def test_idconv_unexpected_response(content):
    with pytest.raises(UpstreamError):
        parse_idconv(content)
