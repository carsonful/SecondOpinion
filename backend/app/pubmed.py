"""Streaming PubMed XML parser and resumable PostgreSQL importer."""

import gzip
import hashlib
import io
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import BinaryIO, Iterator

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import IngestionCheckpoint, Study, StudyEmbedding

LOG = logging.getLogger(__name__)
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UPDATEFILES = "https://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles"
MONTHS = {name.lower(): number for number, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _date(element: ET.Element | None) -> date | None:
    if element is None:
        return None
    year, month, day = (_text(element.find(part)) for part in ("Year", "Month", "Day"))
    if not all((year, month, day)):
        return None  # A partial date is metadata, never an invented calendar date.
    try:
        month_number = int(month) if month.isdigit() else MONTHS[month[:3].lower()]
        return date(int(year), month_number, int(day))
    except (ValueError, KeyError):
        return None


def parse_article(element: ET.Element) -> dict | None:
    citation = element.find("MedlineCitation")
    document = citation if citation is not None else element.find("BookDocument")
    if document is None:
        return None
    pmid = _text(document.find("PMID"))
    if not pmid or not pmid.isdigit():
        return None
    article = document.find("Article") if citation is not None else document
    if article is None:
        return None
    abstract_parts = []
    for part in article.findall("./Abstract/AbstractText"):
        content = _text(part)
        if content:
            label = part.attrib.get("Label")
            abstract_parts.append(f"{label}: {content}" if label else content)
    ids = element.findall("./PubmedData/ArticleIdList/ArticleId")
    doi = next((_text(item) for item in ids if item.attrib.get("IdType") == "doi"), None)
    if doi is None:
        doi = next((_text(item) for item in article.findall("./ELocationID")
                    if item.attrib.get("EIdType") == "doi"), None)
    pub_types = [value for item in article.findall("./PublicationTypeList/PublicationType")
                 if (value := _text(item))]
    retraction_status = None
    if "Retracted Publication" in pub_types:
        retraction_status = "retracted"
    elif "Retraction of Publication" in pub_types:
        retraction_status = "retraction_notice"
    pub_date = article.find("./Journal/JournalIssue/PubDate")
    publication_date = _date(article.find("./ArticleDate")) or _date(pub_date)
    authors = []
    for author in article.findall("./AuthorList/Author"):
        name = " ".join(filter(None, (_text(author.find("ForeName")), _text(author.find("LastName")))))
        if name:
            authors.append(name)
    mesh = [value for item in document.findall("./MeshHeadingList/MeshHeading/DescriptorName")
            if (value := _text(item))]
    metadata = {
        "publication_types": pub_types,
        "authors": authors,
        "languages": [value for item in article.findall("Language") if (value := _text(item))],
        "keywords": [value for item in document.findall("./KeywordList/Keyword") if (value := _text(item))],
        "issn": _text(article.find("./Journal/ISSN")),
        "medline_date": _text(pub_date.find("MedlineDate")) if pub_date is not None else None,
        "publication_year": _text(pub_date.find("Year")) if pub_date is not None else None,
    }
    return {
        "pmid": pmid,
        "doi": doi,
        "title": _text(article.find("ArticleTitle")) or _text(article.find("BookTitle")),
        "abstract": "\n".join(abstract_parts) or None,
        "journal": _text(article.find("./Journal/Title")),
        "publication_date": publication_date,
        "study_type": pub_types[0] if pub_types else None,
        "sample_size": None,  # PubMed has no reliable structured sample-size field.
        "retraction_status": retraction_status,
        "mesh_terms": mesh or None,
        "metadata": metadata,
        "is_deleted": False,
        "deleted_at": None,
    }


def iter_pubmed_xml(stream: BinaryIO) -> Iterator[tuple[str, dict | str]]:
    """Yield articles and deletion PMIDs while retaining at most one XML record."""
    parser = ET.iterparse(stream, events=("start", "end"))
    _, root = next(parser)
    for event, element in parser:
        if event != "end":
            continue
        if element.tag in ("PubmedArticle", "PubmedBookArticle"):
            row = parse_article(element)
            if row:
                yield "article", row
            else:
                LOG.warning("Skipping PubMed record without a valid PMID/article")
            root.clear()
        elif element.tag == "DeleteCitation":
            for item in element.findall("PMID"):
                pmid = _text(item)
                if pmid and pmid.isdigit():
                    yield "delete", pmid
            root.clear()


def _upsert_articles(connection, rows: list[dict]) -> None:
    # A single statement per batch; duplicate PMIDs inside a batch must be collapsed.
    latest = {row["pmid"]: row for row in rows}
    statement = insert(Study).values(list(latest.values()))
    changes = {column: statement.excluded[column] for column in latest[next(iter(latest))]
               if column != "pmid"}
    changes["updated_at"] = func.now()
    connection.execute(statement.on_conflict_do_update(index_elements=[Study.pmid], set_=changes))


def _apply_deletions(connection, pmids: list[str]) -> None:
    unique = list(set(pmids))
    statement = insert(Study).values([{"pmid": pmid, "is_deleted": True, "deleted_at": func.now()} for pmid in unique])
    connection.execute(statement.on_conflict_do_update(
        index_elements=[Study.pmid],
        set_={"is_deleted": True, "deleted_at": func.now(), "updated_at": func.now()},
    ))
    ids = select(Study.id).where(Study.pmid.in_(unique))
    connection.execute(delete(StudyEmbedding).where(StudyEmbedding.study_id.in_(ids)))


def _checkpoint(connection, source: str, cursor: int, processed: int, deleted: int, completed: bool):
    statement = insert(IngestionCheckpoint).values(
        source=source, cursor=cursor, processed=processed, deleted=deleted,
        completed=completed, updated_at=func.now())
    connection.execute(statement.on_conflict_do_update(
        index_elements=[IngestionCheckpoint.source],
        set_={"cursor": cursor, "processed": processed, "deleted": deleted,
              "completed": completed, "updated_at": func.now()}))


def ingest_stream(engine, stream: BinaryIO, source: str, batch_size: int = 500) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    with engine.connect() as connection:
        state = connection.execute(select(
            IngestionCheckpoint.cursor, IngestionCheckpoint.processed,
            IngestionCheckpoint.deleted, IngestionCheckpoint.completed,
        ).where(IngestionCheckpoint.source == source)).mappings().one_or_none()
        cursor, processed, deleted = (state["cursor"], state["processed"], state["deleted"]) if state else (0, 0, 0)
        if state and state["completed"]:
            return {"source": source, "processed": processed, "deleted": deleted, "resumed_from": cursor}
    resumed_from = cursor
    pending: list[tuple[str, dict | str]] = []

    def flush(items: list[tuple[str, dict | str]], complete: bool = False):
        nonlocal cursor, processed, deleted
        if not items and not complete:
            return
        # Preserve update order: a deletion and replacement can coexist in one file.
        with engine.begin() as connection:
            article_rows: list[dict] = []
            deletion_pmids: list[str] = []
            for kind, value in items:
                if kind == "article":
                    if deletion_pmids:
                        _apply_deletions(connection, deletion_pmids)
                        deletion_pmids.clear()
                    article_rows.append(value)
                else:
                    if article_rows:
                        _upsert_articles(connection, article_rows)
                        article_rows.clear()
                    deletion_pmids.append(value)
            if article_rows:
                _upsert_articles(connection, article_rows)
            if deletion_pmids:
                _apply_deletions(connection, deletion_pmids)
            cursor += len(items)
            processed += sum(kind == "article" for kind, _ in items)
            deleted += sum(kind == "delete" for kind, _ in items)
            _checkpoint(connection, source, cursor, processed, deleted, complete)
        LOG.info("%s: %d records, %d deletions committed", source, processed, deleted)

    for position, item in enumerate(iter_pubmed_xml(stream), 1):
        if position <= resumed_from:
            continue
        pending.append(item)
        if len(pending) >= batch_size:
            flush(pending)
            pending = []
    flush(pending, complete=True)
    return {"source": source, "processed": processed, "deleted": deleted, "resumed_from": resumed_from}


def ingest_file(engine, path: Path, batch_size: int = 500) -> dict:
    path = path.resolve()
    stat = path.stat()
    identity = hashlib.sha256(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()
    source = f"file:{path.name}:{identity}"
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        return ingest_stream(engine, stream, source, batch_size)


def _ncbi_request(endpoint: str, params: dict[str, str], email: str, api_key: str | None = None) -> bytes:
    params = {**params, "tool": "SecondOpinion", "email": email}
    if api_key:
        params["api_key"] = api_key
    request = urllib.request.Request(
        f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": f"SecondOpinion PubMed importer ({email})"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            time.sleep(0.11 if api_key else 0.35)
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 4:
                raise
            delay = min(2 ** attempt, 16)
            LOG.warning("NCBI request failed (%s); retrying in %ds", error, delay)
            time.sleep(delay)
    raise RuntimeError("NCBI request failed")


def import_sample(engine, email: str, query: str, limit: int = 10, api_key: str | None = None) -> dict:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    search = ET.fromstring(_ncbi_request("esearch.fcgi", {
        "db": "pubmed", "term": query, "retmax": str(limit), "retmode": "xml", "sort": "relevance"}, email, api_key))
    pmids = [node.text for node in search.findall("./IdList/Id") if node.text]
    totals = {"processed": 0, "deleted": 0}
    for offset in range(0, len(pmids), 100):
        batch = pmids[offset:offset + 100]
        payload = _ncbi_request("efetch.fcgi", {
            "db": "pubmed", "id": ",".join(batch), "retmode": "xml"}, email, api_key)
        source = f"eutils:{hashlib.sha256(','.join(batch).encode()).hexdigest()}"
        result = ingest_stream(engine, io.BytesIO(payload), source)
        totals["processed"] += result["processed"]
    return {"requested": len(pmids), **totals}


def sync_updates(engine, directory: Path, start_at: str | None = None,
                 max_files: int | None = None, batch_size: int = 500) -> list[dict]:
    """Download official daily files with checksum validation and apply in file order."""
    directory.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(f"{UPDATEFILES}/", timeout=60) as response:
                listing = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 16))
    names = sorted(set(re.findall(r'href="(pubmed\d{2}n\d{4}\.xml\.gz)"', listing)))
    if start_at:
        names = [name for name in names if name >= start_at]
    if max_files is not None:
        names = names[:max_files]
    results = []
    for name in names:
        target = directory / name
        if not target.exists():
            url = f"{UPDATEFILES}/{name}"
            for attempt in range(5):
                temporary = target.with_suffix(target.suffix + ".part")
                try:
                    with urllib.request.urlopen(url + ".md5", timeout=60) as response:
                        expected = re.search(r"[a-fA-F0-9]{32}", response.read().decode("ascii"))
                    if expected is None:
                        raise ValueError(f"No MD5 checksum for {name}")
                    digest = hashlib.md5()  # NCBI publishes MD5 for transport validation.
                    with urllib.request.urlopen(url, timeout=120) as response, open(temporary, "wb") as output:
                        while block := response.read(1024 * 1024):
                            digest.update(block)
                            output.write(block)
                    if digest.hexdigest().lower() != expected.group().lower():
                        raise ValueError(f"Checksum mismatch for {name}")
                    temporary.replace(target)
                    break
                except (OSError, ValueError, urllib.error.URLError):
                    temporary.unlink(missing_ok=True)
                    if attempt == 4:
                        raise
                    time.sleep(min(2 ** attempt, 16))
        results.append(ingest_file(engine, target, batch_size))
    return results
