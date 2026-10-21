"""Public HTTPS downloads with DNS pinning, bounded redirects and response size."""
import asyncio
from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urljoin

import httpx2 as httpx

from app.services.study_documents import FullTextUnavailable, MAX_DOCUMENT_BYTES


@dataclass(frozen=True)
class Download:
    content: bytes
    url: str
    content_type: str


async def public_address(url: httpx.URL) -> str:
    if url.scheme != 'https' or not url.host or url.userinfo or url.port not in (None, 443):
        raise FullTextUnavailable('Document link is not a public HTTPS URL.')
    addresses = await asyncio.get_running_loop().getaddrinfo(url.host, 443, type=socket.SOCK_STREAM)
    ips = [entry[4][0] for entry in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise FullTextUnavailable('Document link does not resolve to a public server.')
    return ips[0]


async def download_document(url: str) -> Download:
    try:
        async with asyncio.timeout(30):
            for _ in range(5):
                original = httpx.URL(url)
                ip = await public_address(original)
                # Connect to the vetted address; don't re-resolve the hostname.
                # Preserve Host and TLS hostname verification. A fresh pool prevents
                # cross-host connection reuse when two hosts share an IP.
                async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False) as client:
                    async with client.stream('GET', original.copy_with(host=ip),
                        headers={'Host': original.host, 'User-Agent': 'SecondOpinion/0.1 (study retrieval)'},
                        extensions={'sni_hostname': original.host}) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get('location')
                            if not location:
                                raise FullTextUnavailable('Publisher returned an invalid redirect.')
                            url = urljoin(str(original), location)
                            continue
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                            data.extend(chunk)
                            if len(data) > MAX_DOCUMENT_BYTES:
                                raise FullTextUnavailable('Document exceeds the 10 MB download limit.')
                        return Download(bytes(data), str(original), response.headers.get('content-type', ''))
            raise FullTextUnavailable('Publisher redirected too many times.')
    except (httpx.HTTPError, OSError, TimeoutError, ValueError):
        raise FullTextUnavailable('Publisher/repository download failed or requires access. You can upload a library PDF instead.') from None
