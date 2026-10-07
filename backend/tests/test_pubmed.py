import io

from app.pubmed import iter_pubmed_xml


XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
    <Journal><JournalIssue><PubDate><Year>2024</Year><Month>Apr</Month><Day>05</Day></PubDate></JournalIssue><Title>Medical Journal</Title></Journal>
    <ArticleTitle>Vitamin <i>D</i> trial</ArticleTitle>
    <Abstract><AbstractText Label="OBJECTIVE">Test a treatment.</AbstractText><AbstractText Label="RESULTS">No effect.</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList>
  </Article><MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList></MedlineCitation>
  <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/test</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
  <PubmedArticle><MedlineCitation><PMID>124</PMID><Article><ArticleTitle>No abstract</ArticleTitle>
    <Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
  </Article></MedlineCitation></PubmedArticle>
  <DeleteCitation><PMID>123</PMID></DeleteCitation>
</PubmedArticleSet>"""


def test_xml_parsing_preserves_available_and_missing_metadata():
    records = list(iter_pubmed_xml(io.BytesIO(XML)))
    assert [kind for kind, _ in records] == ["article", "article", "delete"]
    first = records[0][1]
    assert first["pmid"] == "123"
    assert first["title"] == "Vitamin D trial"
    assert first["abstract"] == "OBJECTIVE: Test a treatment.\nRESULTS: No effect."
    assert str(first["publication_date"]) == "2024-04-05"
    assert first["doi"] == "10.1000/test"
    assert first["mesh_terms"] == ["Humans"]
    assert first["sample_size"] is None
    second = records[1][1]
    assert second["abstract"] is None
    assert second["publication_date"] is None
    assert second["metadata"]["publication_year"] == "2023"
    assert records[2] == ("delete", "123")


def test_invalid_pmid_is_ignored():
    xml = b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>bad</PMID><Article/></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    assert list(iter_pubmed_xml(io.BytesIO(xml))) == []
