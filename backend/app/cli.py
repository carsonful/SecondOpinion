"""Developer commands: python -m app.cli --help"""

import argparse
import json
import logging
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.db import Claim, IngestionCheckpoint, Study, StudyEmbedding, get_engine
from app.embeddings import DEFAULT_MODEL, DEFAULT_REVISION, embed_studies
from app.pubmed import import_sample, ingest_file, sync_updates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SecondOpinion PubMed data commands")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="Import a small NCBI E-utilities search result")
    sample.add_argument("--query", default="randomized controlled trial")
    sample.add_argument("--limit", type=int, default=10)
    sample.add_argument("--email", help="NCBI contact email (or NCBI_EMAIL)")
    for name in ("baseline", "updates"):
        command = commands.add_parser(name, help=f"Import local PubMed {name} XML or XML.GZ files")
        command.add_argument("paths", nargs="+", type=Path)
        command.add_argument("--batch-size", type=int, default=500)
    sync = commands.add_parser("sync-updates", help="Fetch and apply official PubMed daily updates")
    sync.add_argument("--directory", type=Path, default=Path("pubmed-updatefiles"))
    sync.add_argument("--start-at", help="First update filename to apply, e.g. pubmed26n1335.xml.gz")
    sync.add_argument("--max-files", type=int)
    sync.add_argument("--batch-size", type=int, default=500)
    embeddings = commands.add_parser("embed", help="Generate or refresh 384-dimension study embeddings")
    embeddings.add_argument("--batch-size", type=int, default=64)
    embeddings.add_argument("--limit", type=int)
    embeddings.add_argument("--model", default=DEFAULT_MODEL)
    embeddings.add_argument("--revision", default=DEFAULT_REVISION)
    commands.add_parser("stats", help="Report database counts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    engine = get_engine()
    if args.command == "sample":
        email = args.email or get_settings().ncbi_email
        if not email:
            raise SystemExit("Set NCBI_EMAIL or pass --email for NCBI E-utilities")
        result = import_sample(engine, email, args.query, args.limit, get_settings().ncbi_api_key)
    elif args.command in ("baseline", "updates"):
        paths = sorted(path for entry in args.paths for path in
                       (entry.iterdir() if entry.is_dir() else [entry])
                       if path.name.endswith((".xml", ".xml.gz")))
        if not paths:
            raise SystemExit("No .xml or .xml.gz files found")
        result = [ingest_file(engine, path, args.batch_size) for path in paths]
    elif args.command == "sync-updates":
        result = sync_updates(engine, args.directory, args.start_at, args.max_files, args.batch_size)
    elif args.command == "embed":
        result = embed_studies(engine, args.model, args.revision, args.batch_size, args.limit)
    else:
        with engine.connect() as connection:
            result = {
                "claims": connection.scalar(select(func.count()).select_from(Claim)),
                "studies_active": connection.scalar(select(func.count()).select_from(Study).where(Study.is_deleted.is_(False))),
                "studies_deleted": connection.scalar(select(func.count()).select_from(Study).where(Study.is_deleted.is_(True))),
                "embeddings": connection.scalar(select(func.count()).select_from(StudyEmbedding)),
                "completed_sources": connection.scalar(select(func.count()).select_from(IngestionCheckpoint).where(IngestionCheckpoint.completed.is_(True))),
            }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
