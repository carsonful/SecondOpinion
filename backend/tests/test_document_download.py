from unittest.mock import AsyncMock
import socket

import httpx2 as httpx
import pytest

from app.services import document_download as download
from app.services.study_documents import FullTextUnavailable


@pytest.mark.anyio
@pytest.mark.parametrize('url', ['http://example.org', 'https://user:pass@example.org', 'https://example.org:8443'])
async def test_non_public_url_forms_rejected(url):
    with pytest.raises(FullTextUnavailable):
        await download.public_address(httpx.URL(url))


@pytest.mark.anyio
@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', '192.168.1.1'])
async def test_private_dns_results_rejected(monkeypatch, ip):
    import asyncio
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, 'getaddrinfo', AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, '', (ip, 443))]))
    with pytest.raises(FullTextUnavailable):
        await download.public_address(httpx.URL('https://example.org'))


@pytest.mark.anyio
async def test_download_pins_address_and_rechecks_redirect(monkeypatch):
    resolver = AsyncMock(side_effect=['93.184.215.14', FullTextUnavailable('private redirect')])
    monkeypatch.setattr(download, 'public_address', resolver)
    real_client = httpx.AsyncClient
    def handler(request):
        assert request.url.host == '93.184.215.14'
        assert request.headers['host'] == 'example.org'
        assert request.extensions['sni_hostname'] == 'example.org'
        return httpx.Response(302, headers={'location': 'https://127.0.0.1/private'})
    monkeypatch.setattr(download.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(FullTextUnavailable, match='private redirect'):
        await download.download_document('https://example.org/paper')
    assert resolver.await_count == 2


@pytest.mark.anyio
async def test_download_size_limit(monkeypatch):
    monkeypatch.setattr(download, 'public_address', AsyncMock(return_value='93.184.215.14'))
    monkeypatch.setattr(download, 'MAX_DOCUMENT_BYTES', 10)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(download.httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b'x' * 11)), **kwargs))
    with pytest.raises(FullTextUnavailable, match='download limit'):
        await download.download_document('https://example.org/paper')
