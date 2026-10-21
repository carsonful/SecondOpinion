"""Bounded document extraction and identity checks, without model calls."""

from dataclasses import dataclass
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from app.models.pubmed import PubMedArticle

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
# One bounded model request for an uploaded PDF; never truncate a paper and call it a full review.
MAX_STUDY_CHARACTERS = 60_000


class FullTextUnavailable(Exception):
    pass


@dataclass(frozen=True)
class StudyDocument:
    text: str
    source_url: str | None
    source_kind: str
    coverage_note: str


def normalized_title(value: str) -> str:
    value = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(c for c in value if c.isalnum())


def verify_title(text: str, article: PubMedArticle) -> None:
    title = normalized_title(article.title)
    if len(title) < 20 or title not in normalized_title(text):
        raise FullTextUnavailable('The document title could not be matched to this study. No model call was made.')


def check_body(text: str) -> str:
    if len(text.strip()) < 1500:
        raise FullTextUnavailable('Too little article text was extracted; this may be an abstract, scanned PDF or access page. No model call was made.')
    if len(text) > MAX_STUDY_CHARACTERS:
        raise FullTextUnavailable("This study exceeds the prototype's 60,000-character assessment budget. No model call was made.")
    # Require article-body sections, not only an abstract and bibliography.
    headings = re.findall(r'(?im)^\s*(?:\d+[.\s]*)?(?:materials and methods|methods|methodology|results|discussion|conclusions?|background|introduction)\b[^\n]{0,120}$', text)
    if len(headings) < 2:
        raise FullTextUnavailable('Full article sections could not be identified. Try a text-based publisher PDF. No model call was made.')
    return text


def extract_pdf(content: bytes, article: PubMedArticle, source_url: str | None = None) -> StudyDocument:
    if len(content) > MAX_DOCUMENT_BYTES:
        raise FullTextUnavailable('PDF exceeds the 10 MB upload/download limit.')
    if not content.startswith(b'%PDF-'):
        raise FullTextUnavailable('The supplied file is not a PDF.')
    # Isolate complex PDF parsing with a deadline and, on Unix, memory/CPU limits.
    try:
        process = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('pdf_extract.py'))],
            input=content, capture_output=True, timeout=25, check=False,
        )
        if process.returncode != 0:
            raise ValueError('PDF parser failed')
        payload = json.loads(process.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        raise FullTextUnavailable('PDF could not be read within the extraction limits. Use an unencrypted, text-based PDF of at most 100 pages.') from None
    verify_title(payload['identity_text'], article)
    text = check_body(payload['text'])
    return StudyDocument(text, source_url, 'downloaded_pdf' if source_url else 'uploaded_pdf',
        'PDF text extraction; page markers are included. Images, scanned pages and external supplements are not read. Table layout may be imperfect; quotations are checked against extracted text.')
