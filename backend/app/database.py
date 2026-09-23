import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


DATABASE_URL = os.getenv("DATABASE_URL")
engine: Engine | None = create_engine(DATABASE_URL) if DATABASE_URL else None


def get_session() -> Iterator[Session]:
    if engine is None:
        raise RuntimeError("DATABASE_URL must be set before using the database")

    with Session(engine) as session:
        yield session
