"""PMC first, then bounded DOI-based open-copy discovery. No model calls."""
import asyncio
from urllib.parse import quote

import httpx2 as httpx
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.models.pubmed import PubMedArticle
from app.services.document_download import download_document
from app.services.full_text import FullTextUnavailable, retrieve_full_text
from app.services.pubmed import PubMedClient, PubMedError
from app.services.study_documents import StudyDocument, extract_html, extract_pdf, pdf_links

MAX_CANDIDATES = 4


def doi_value(value: str) -> str:
    return value.removeprefix('https://doi.org/').removeprefix('http://doi.org/').strip().casefold()


async def discover_locations(article: PubMedArticle, settings: Settings, client: httpx.AsyncClient) -> tuple[list[str], list[str]]:
    if not article.doi:
        return [], ['This PubMed record has no DOI for publisher/repository discovery.']
    doi = quote(article.doi, safe='')
    candidates, notes = [], []
    headers = {'Authorization': f'Bearer {settings.openalex_api_key.get_secret_value()}'} if settings.openalex_api_key else {}
    try:
        response = await client.get(f'https://api.openalex.org/works/https://doi.org/{doi}', headers=headers)
        if response.status_code != 404:
            response.raise_for_status()
            work = response.json()
            if doi_value(work.get('doi') or '') != doi_value(article.doi):
                raise ValueError('DOI mismatch')
            locations = [work.get('best_oa_location')] + (work.get('locations') or [])
            for location in locations:
                if isinstance(location, dict) and location.get('is_oa'):
                    candidates.extend([location.get('pdf_url'), location.get('landing_page_url')])
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        notes.append('OpenAlex discovery was unavailable or returned invalid metadata.')
    email = settings.unpaywall_email or settings.ncbi_email
    if email:
        try:
            response = await client.get(f'https://api.unpaywall.org/v2/{doi}', params={'email': email})
            if response.status_code != 404:
                response.raise_for_status()
                work = response.json()
                if doi_value(work.get('doi') or '') != doi_value(article.doi):
                    raise ValueError('DOI mismatch')
                locations = [work.get('best_oa_location')] + (work.get('oa_locations') or [])
                for location in locations:
                    if isinstance(location, dict):
                        candidates.extend([location.get('url_for_pdf'), location.get('url_for_landing_page'), location.get('url')])
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            notes.append('Unpaywall discovery was unavailable or returned invalid metadata.')
    else:
        notes.append('Unpaywall was not checked because no contact email is configured.')
    return list(dict.fromkeys(url for url in candidates if isinstance(url, str) and url.startswith('https://')))[:MAX_CANDIDATES], notes


async def retrieve_study_document(client: PubMedClient, article: PubMedArticle) -> StudyDocument:
    notes = []
    try:
        text = await retrieve_full_text(client, article)
        return StudyDocument(text, f'https://pmc.ncbi.nlm.nih.gov/articles/{article.pmc_id}/', 'pmc',
            'PMC article body and abstract, including text tables and captions. Figure images, external supplements and reference lists are not assessed.')
    except (FullTextUnavailable, PubMedError) as exc:
        # Do not expose upstream exception URLs/keys in the UI.
        notes.append(str(exc) if isinstance(exc, FullTextUnavailable) else 'PMC retrieval failed.')
    try:
        async with asyncio.timeout(90):
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
                urls, discovery_notes = await discover_locations(article, get_settings(), http)
            notes.extend(discovery_notes)
            visited = set()
            while urls and len(visited) < MAX_CANDIDATES:
                url = urls.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                try:
                    download = await download_document(url)
                    if download.content.startswith(b'%PDF-'):
                        return await run_in_threadpool(extract_pdf, download.content, article, download.url)
                    if 'html' not in download.content_type:
                        raise FullTextUnavailable('A discovered copy was not a supported PDF or HTML document.')
                    try:
                        return await run_in_threadpool(extract_html, download.content, article, download.url)
                    except FullTextUnavailable:
                        urls[0:0] = await run_in_threadpool(pdf_links, download.content, download.url)
                        raise
                except FullTextUnavailable as exc:
                    notes.append(str(exc))
    except TimeoutError:
        notes.append('Full-text discovery reached its time limit.')
    # Preserve informative failures without claiming the article does not exist.
    detail = ' '.join(dict.fromkeys(notes))
    raise FullTextUnavailable('Automatic full-text retrieval did not find a usable copy. ' + detail +
        ' Upload a text-based PDF obtained from the publisher, repository or your library. No model call was made.')
