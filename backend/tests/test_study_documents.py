import io
from unittest.mock import AsyncMock, Mock

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.config import Settings
from app.main import app
from app.routers import claims
from app.routers.pubmed import get_pubmed_client
from app.services import study_retrieval as retrieval
from app.services.full_text import FullTextUnavailable
from app.services.study_documents import extract_pdf, extract_html, StudyDocument
from tests.test_assessment import article

TITLE = 'A randomized study of zinc treatment in adults with a common cold'
PAPER = article(title=TITLE, doi='10.1234/example')
BODY = 'Introduction\n' + ('Study background and population details. ' * 25) + '\nMethods\n' + ('We randomized 120 adults to treatment or placebo. ' * 25) + '\nResults\n' + ('The treatment group was compared with controls. ' * 20)
HTML = f'<html><meta name="citation_title" content="{TITLE}"><meta name="citation_doi" content="10.1234/example"><div class="article-body">{BODY}</div></html>'.encode()


def pdf_bytes(title=TITLE, body=BODY, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    lines = '\n'.join(f'({line}) Tj 0 -12 Td' for line in (title + '\n' + body).splitlines())
    stream.set_data(('BT /F1 10 Tf 40 740 Td\n' + lines + '\nET').encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('password')
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_real_pdf_extraction_with_page_provenance():
    doc = extract_pdf(pdf_bytes(), PAPER)
    assert doc.source_kind == 'uploaded_pdf'
    assert doc.source_url is None
    assert '[Page 1]' in doc.text
    assert '120 adults' in doc.text
    assert extract_pdf(pdf_bytes(), PAPER, 'https://example.org/paper.pdf').source_kind == 'downloaded_pdf'


@pytest.mark.parametrize('content', [b'not a PDF', b'%PDF-broken', pdf_bytes(title='A different study title'), pdf_bytes(body='Abstract only.'), pdf_bytes(encrypted=True)])
def test_bad_pdf_never_becomes_full_study(content):
    with pytest.raises(FullTextUnavailable):
        extract_pdf(content, PAPER)


def test_pdf_text_budget_rejects_instead_of_truncating():
    with pytest.raises(FullTextUnavailable, match='60,000'):
        extract_pdf(pdf_bytes(body=BODY + ('excess text ' * 7000)), PAPER)


def test_html_body_identity_and_scope():
    doc = extract_html(HTML, PAPER, 'https://example.org/paper')
    assert '120 adults' in doc.text
    assert doc.source_kind == 'publisher_html'


@pytest.mark.parametrize('html', [
    HTML.replace(TITLE.encode(), b'An unrelated article'),
    HTML.replace(b'10.1234/example', b'10.1234/wrong'),
    HTML.replace(b'article-body', b'abstract'),
    f'<h1>{TITLE}</h1><div class="article-body">Abstract only.</div>'.encode(),
])
def test_landing_page_or_wrong_article_rejected(html):
    with pytest.raises(FullTextUnavailable):
        extract_html(html, PAPER, 'https://example.org')


@pytest.mark.anyio
async def test_discovery_combines_and_deduplicates_open_locations():
    def handler(request):
        if request.url.host == 'api.openalex.org':
            assert request.headers['authorization'] == 'Bearer test-key'
            return httpx.Response(200, json={'doi': 'https://doi.org/10.1234/example', 'locations': [
                {'is_oa': False, 'pdf_url': 'https://example.org/closed.pdf'},
                {'is_oa': True, 'pdf_url': 'https://example.org/open.pdf'}]})
        assert request.url.params['email'] == 'team@example.org'
        return httpx.Response(200, json={'doi': '10.1234/example', 'oa_locations': [
            {'url_for_pdf': 'https://example.org/open.pdf', 'url': 'https://repository.org/paper'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        urls, notes = await retrieval.discover_locations(PAPER, Settings(_env_file=None, unpaywall_email='team@example.org', openalex_api_key='test-key'), client)
    assert urls == ['https://example.org/open.pdf', 'https://repository.org/paper']
    assert notes == []


@pytest.mark.anyio
@pytest.mark.parametrize('status,payload', [(429, {}), (200, {'doi': '10.1234/wrong'}), (200, [])])
async def test_discovery_failure_is_not_a_closed_access_claim(status, payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=payload))) as client:
        urls, notes = await retrieval.discover_locations(PAPER, Settings(_env_file=None), client)
    assert urls == []
    assert 'unavailable' in notes[0]
    assert 'email' in notes[1]


@pytest.mark.anyio
async def test_pmc_success_skips_discovery(monkeypatch):
    monkeypatch.setattr(retrieval, 'retrieve_full_text', AsyncMock(return_value=BODY))
    discover = AsyncMock()
    monkeypatch.setattr(retrieval, 'discover_locations', discover)
    doc = await retrieval.retrieve_study_document(AsyncMock(), PAPER.model_copy(update={'pmc_id': 'PMC123'}))
    assert doc.source_kind == 'pmc'
    discover.assert_not_called()


@pytest.mark.anyio
async def test_fallback_tries_second_copy_after_access_failure(monkeypatch):
    from app.services.document_download import Download
    monkeypatch.setattr(retrieval, 'retrieve_full_text', AsyncMock(side_effect=FullTextUnavailable('No PMC')))
    monkeypatch.setattr(retrieval, 'discover_locations', AsyncMock(return_value=(['https://blocked.org', 'https://open.org'], [])))
    downloader = AsyncMock(side_effect=[FullTextUnavailable('Blocked'), Download(HTML, 'https://open.org', 'text/html')])
    monkeypatch.setattr(retrieval, 'download_document', downloader)
    doc = await retrieval.retrieve_study_document(AsyncMock(), PAPER)
    assert doc.source_url == 'https://open.org'
    assert downloader.await_count == 2


@pytest.mark.anyio
async def test_html_landing_page_follows_pdf_metadata(monkeypatch):
    from app.services.document_download import Download
    monkeypatch.setattr(retrieval, 'retrieve_full_text', AsyncMock(side_effect=FullTextUnavailable('No PMC')))
    monkeypatch.setattr(retrieval, 'discover_locations', AsyncMock(return_value=(['https://example.org/paper'], [])))
    downloader = AsyncMock(side_effect=[
        Download(b'<meta name="citation_pdf_url" content="/paper.pdf">', 'https://example.org/paper', 'text/html'),
        Download(pdf_bytes(), 'https://example.org/paper.pdf', 'application/pdf'),
    ])
    monkeypatch.setattr(retrieval, 'download_document', downloader)
    doc = await retrieval.retrieve_study_document(AsyncMock(), PAPER)
    assert doc.source_kind == 'downloaded_pdf'
    assert downloader.await_args.args == ('https://example.org/paper.pdf',)


@pytest.mark.parametrize('valid', [True, False])
def test_pdf_upload_route_only_assesses_verified_documents(monkeypatch, valid):
    client = AsyncMock()
    client.get_article.return_value = PAPER
    app.dependency_overrides[get_pubmed_client] = lambda: client
    assessor = Mock(return_value=claims.assess_metadata(PAPER).model_copy(update={'assessment_status': 'completed', 'assessment_basis': 'full_text'}))
    monkeypatch.setattr(claims, 'assess_abstract', assessor)
    try:
        response = TestClient(app).post('/api/claims/articles/123/assess-pdf', data={'claim': 'claim'},
            files={'file': ('study.pdf', pdf_bytes() if valid else b'%PDF-wrong', 'application/pdf')})
        assert response.status_code == (200 if valid else 422)
        if valid:
            assert response.json()['source_kind'] == 'uploaded_pdf'
            assert response.json()['source_url'] is None
            assert response.json()['weight_version'] == 'base_weights_v0.1'
            assert assessor.call_count == 1
        else:
            assessor.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('mode,status', [('oversize', 413), ('blank_claim', 422), ('retracted', 200), ('not_found', 404)])
def test_pdf_route_rejects_before_model_call(monkeypatch, mode, status):
    client = AsyncMock()
    client.get_article.return_value = None if mode == 'not_found' else PAPER.model_copy(update={'retracted': mode == 'retracted'})
    app.dependency_overrides[get_pubmed_client] = lambda: client
    assessor = Mock()
    extractor = Mock()
    monkeypatch.setattr(claims, 'assess_abstract', assessor)
    monkeypatch.setattr(claims, 'extract_pdf', extractor)
    if mode == 'oversize':
        monkeypatch.setattr(claims, 'MAX_DOCUMENT_BYTES', 5)
    try:
        response = TestClient(app).post('/api/claims/articles/123/assess-pdf', data={'claim': ' ' if mode == 'blank_claim' else 'claim'},
            files={'file': ('study.pdf', b'%PDF-content', 'application/pdf')})
        assert response.status_code == status
        assessor.assert_not_called()
        extractor.assert_not_called()
        if mode == 'retracted':
            assert response.json()['assessment_status'] == 'skipped'
    finally:
        app.dependency_overrides.clear()
