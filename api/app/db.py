from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
import sqlite3

from app.config import get_settings


def _database_url() -> str:
    return get_settings().database_url


def is_sqlite() -> bool:
    return _database_url().startswith("sqlite")


def _sqlite_path() -> str:
    parsed = urlparse(_database_url())
    if parsed.path in ("", "/:memory:"):
        return ":memory:"
    path = parsed.path
    if parsed.netloc:
        path = f"/{parsed.netloc}{parsed.path}"
    if path.startswith("/") and not _database_url().startswith("sqlite:////"):
        path = path[1:]
    return path or "canopy.db"


def _postgres_url() -> str:
    return _database_url().replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def connection() -> Iterator:
    if is_sqlite():
        db_path = _sqlite_path()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
        return

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_postgres_url(), row_factory=dict_row) as conn:
        yield conn


def initialize_database() -> None:
    import os
    from alembic import command
    from alembic.config import Config

    current_dir = os.path.dirname(os.path.abspath(__file__))
    api_dir = os.path.dirname(current_dir)
    alembic_cfg = Config(os.path.join(api_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(api_dir, "alembic"))

    # Run Alembic migrations programmatically
    command.upgrade(alembic_cfg, "head")


