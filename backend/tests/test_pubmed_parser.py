import pytest

from app.services.pubmed import PubMedResponseError, parse_efetch_xml
from tests.helpers import load_fixture


def test_parses_every_article_in_a_recorded_response() -> None:
    articles = parse_efetch_xml(load_fixture("pubmed/efetch_zinc_cold.xml"))

    assert [a.pmid for a in articles] == ["38719213", "31478634", "32342851"]


def test_parses_the_fields_the_grading_engine_needs() -> None:
    cochrane = parse_efetch_xml(load_fixture("pubmed/efetch_zinc_cold.xml"))[0]

    assert cochrane.title == "Zinc for prevention and treatment of the common cold."
    assert cochrane.journal == "The Cochrane database of systematic reviews"
    assert cochrane.year == 2024
    assert cochrane.doi == "10.1002/14651858.CD014914.pub2"
    assert cochrane.pmc_id == "PMC11078591"
    assert "Systematic Review" in cochrane.publication_types
    assert "Common Cold" in cochrane.mesh_terms
    assert cochrane.authors[0] == "Nault D"
    assert cochrane.retracted is False
    assert cochrane.url == "https://pubmed.ncbi.nlm.nih.gov/38719213/"


def test_structured_abstracts_keep_their_section_labels() -> None:
    cochrane = parse_efetch_xml(load_fixture("pubmed/efetch_zinc_cold.xml"))[0]

    assert cochrane.abstract is not None
    assert cochrane.abstract.startswith("BACKGROUND: The common cold is an acute")
    assert "\n\nOBJECTIVES: " in cochrane.abstract


def test_unstructured_abstracts_have_no_label_prefix() -> None:
    article = parse_efetch_xml(load_fixture("pubmed/efetch_zinc_cold.xml"))[1]

    assert article.abstract is not None
    assert not article.abstract.startswith("None")
    assert article.doi is None


def test_flags_retracted_publications() -> None:
    (wakefield,) = parse_efetch_xml(load_fixture("pubmed/efetch_retracted.xml"))

    assert wakefield.pmid == "9500320"
    assert wakefield.retracted is True
    assert wakefield.year == 1998


def test_handles_medline_dates_inline_markup_and_group_authors() -> None:
    xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
        <Journal><Title>Some Journal</Title><JournalIssue><PubDate>
          <MedlineDate>1998 Dec-1999 Jan</MedlineDate>
        </PubDate></JournalIssue></Journal>
        <ArticleTitle>Effect of vitamin D<sub>3</sub> on <i>Streptococcus</i></ArticleTitle>
        <AuthorList>
          <Author><CollectiveName>The Cold Study Group</CollectiveName></Author>
          <Author><LastName>Smith</LastName><Initials>J</Initials></Author>
        </AuthorList>
        <CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"><PMID>2</PMID></CommentsCorrections></CommentsCorrectionsList>
      </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

    (article,) = parse_efetch_xml(xml)

    assert article.year == 1998
    assert article.title == "Effect of vitamin D3 on Streptococcus"
    assert article.authors == ["The Cold Study Group", "Smith J"]
    assert article.abstract is None
    assert article.publication_types == []


def test_empty_result_set_parses_to_no_articles() -> None:
    assert parse_efetch_xml(b"<PubmedArticleSet></PubmedArticleSet>") == []


def test_malformed_xml_raises() -> None:
    with pytest.raises(PubMedResponseError):
        parse_efetch_xml(b"<PubmedArticleSet><PubmedArticle>")


@pytest.mark.parametrize("relation,retracted", [
    ("RetractionIn", True), ("RetractionOf", False),
    ("ErratumIn", False), ("ErratumFor", False),
    ("ExpressionOfConcernIn", False), ("ExpressionOfConcernFor", False),
])
def test_integrity_links_keep_direction(relation, retracted):
    xml = f'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>
    <Article><ArticleTitle>Study</ArticleTitle></Article>
    <CommentsCorrectionsList><CommentsCorrections RefType="{relation}">
    <RefSource>Notice citation</RefSource><PMID>2</PMID><Note>Details</Note>
    </CommentsCorrections></CommentsCorrectionsList>
    </MedlineCitation></PubmedArticle></PubmedArticleSet>'''.encode()
    paper = parse_efetch_xml(xml)[0]
    assert paper.retracted is retracted
    assert paper.integrity_links[0].model_dump() == dict(
        relation=relation, pmid="2", citation="Notice citation", note="Details")


def test_integrity_link_without_pmid_and_unrelated_comment():
    xml = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article/>
    <CommentsCorrectionsList><CommentsCorrections RefType="ErratumIn"><RefSource>Correction</RefSource></CommentsCorrections>
    <CommentsCorrections RefType="CommentIn"><PMID>3</PMID></CommentsCorrections>
    </CommentsCorrectionsList></MedlineCitation></PubmedArticle></PubmedArticleSet>'''
    paper = parse_efetch_xml(xml)[0]
    assert len(paper.integrity_links) == 1
    assert paper.integrity_links[0].pmid is None
    assert paper.integrity_links[0].citation == "Correction"
