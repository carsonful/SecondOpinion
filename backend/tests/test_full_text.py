import json
from unittest.mock import AsyncMock

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import claims
from app.routers.pubmed import get_pubmed_client
from app.services.full_text import FullTextUnavailable, parse_full_text, retrieve_full_text
from app.services.pubmed import PubMedResponseError
from app.services.findings import assess_abstract, AssessmentOutputError
from tests.test_assessment import article
from tests.test_normalization import settings
from tests.test_findings import OUTPUT, transport

PAPER = article(pmc_id="PMC456")
XML = b'''<pmc-articleset><article><front><article-meta>
<article-id pub-id-type="pmc">456</article-id><article-id pub-id-type="pmid">123</article-id>
<abstract><p>Brief abstract.</p></abstract></article-meta></front>
<body><sec><title>Methods</title><p>We randomized <italic>120 adults</italic>.</p></sec>
<sec><title>Results</title><p>There was no clear difference.</p>
<table-wrap><caption>Outcomes</caption><table><tr><td>Treatment</td><td>60</td></tr></table></table-wrap>
</sec></body><back><ref-list><ref>Cited background only.</ref></ref-list></back>
</article></pmc-articleset>'''


def test_full_body_includes_methods_tables_not_references():
    text = parse_full_text(XML, PAPER)
    assert "We randomized 120 adults." in text
    assert "Treatment\n\n60" in text or "Treatment\n60" in text
    assert "Cited background" not in text


@pytest.mark.parametrize("content", [b'<pmc-articleset/>', XML.replace(b'<body>', b'<missing>').replace(b'</body>', b'</missing>')])
def test_no_body_is_not_an_abstract_assessment(content):
    with pytest.raises(FullTextUnavailable):
        parse_full_text(content, PAPER)


def test_identity_and_malformed_xml_rejected():
    for content in [b'<broken', XML.replace(b'>123<', b'>999<')]:
        with pytest.raises(PubMedResponseError):
            parse_full_text(content, PAPER)


def test_oversize_paper_not_truncated():
    with pytest.raises(FullTextUnavailable, match="budget"):
        parse_full_text(XML.replace(b'120 adults', b'x' * 60001), PAPER)


@pytest.mark.anyio
async def test_missing_pmc_makes_no_request():
    client = AsyncMock()
    with pytest.raises(FullTextUnavailable):
        await retrieve_full_text(client, article())
    client._get.assert_not_awaited()


def test_provider_reads_body_and_validates_its_quotes():
    text = parse_full_text(XML, PAPER)
    output = OUTPUT | {"supporting_passages": ["We randomized 120 adults."]}
    def handler(request):
        payload = json.loads(request.content)
        data = json.loads(payload['messages'][1]['content'])
        assert data['full_text'] == text
        assert 'abstract' not in data
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}]})
    result = assess_abstract('claim', PAPER.model_copy(update={'abstract': None}), full_text=text,
                             settings=settings(), transport=httpx.MockTransport(handler))
    assert result.assessment_basis == 'full_text'
    assert result.source_url.endswith('/PMC456/')
    assert result.weight_version == 'base_weights_v0.1'
    assert result.effective_weight == 0
    with pytest.raises(AssessmentOutputError):
        assess_abstract('claim', PAPER, full_text=text, settings=settings(), transport=transport())


@pytest.mark.parametrize('mode', ['available', 'missing', 'retracted', 'oversize', 'outage'])
def test_full_study_route(monkeypatch, mode):
    client = AsyncMock()
    client.get_article.return_value = PAPER.model_copy(update={'retracted': mode == 'retracted'})
    from app.services.study_documents import StudyDocument
    text = AsyncMock(return_value=StudyDocument('Full body text.', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC456/', 'pmc', 'PMC text.'))
    if mode in {'missing', 'oversize'}:
        text.side_effect = FullTextUnavailable('Unavailable or over budget')
    if mode == 'outage':
        from app.services.pubmed import PubMedUnavailableError
        text.side_effect = PubMedUnavailableError('outage')
    monkeypatch.setattr(claims, 'retrieve_study_document', text)
    from unittest.mock import Mock
    assessor = Mock(return_value=claims.assess_metadata(PAPER).model_copy(update={'assessment_status': 'completed', 'assessment_basis': 'full_text'}))
    monkeypatch.setattr(claims, 'assess_abstract', assessor)
    app.dependency_overrides[get_pubmed_client] = lambda: client
    try:
        response = TestClient(app).post('/api/claims/articles/123/assess-full-text', json={'claim': 'claim'})
        if mode == 'outage':
            assert response.status_code == 503
        else:
            assert response.status_code == 200
            assert response.json()['assessment_status'] == {'available': 'completed', 'retracted': 'skipped'}.get(mode, 'unavailable')
        if mode == 'available':
            assessor.assert_called_once_with('claim', client.get_article.return_value, full_text='Full body text.')
        else:
            assessor.assert_not_called()
        if mode == 'retracted':
            text.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
