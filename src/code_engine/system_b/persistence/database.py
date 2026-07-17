"""Database engine/session helpers for Atlas SQLite persistence."""
from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///data/code_atlas.db"
ATLAS_SCHEMA_HEAD = "0010_role_workspaces"


def database_url(value: str | None = None) -> str:
    return value or os.environ.get("ATLAS_DATABASE_URL") or DEFAULT_DATABASE_URL


def sqlite_path_from_url(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.removeprefix("sqlite:///"))


def ensure_sqlite_parent(url: str) -> None:
    path = sqlite_path_from_url(url)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(stat.S_IRWXU)
    except OSError:
        pass


def create_atlas_engine(url: str | None = None) -> Engine:
    resolved = database_url(url)
    ensure_sqlite_parent(resolved)
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    engine = create_engine(resolved, future=True, connect_args=connect_args)

    if resolved.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sqlite_health(engine: Engine) -> dict:
    with engine.connect() as conn:
        integrity = conn.execute(text("PRAGMA integrity_check")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar()
        version = None
        try:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            version = None
    return {
        "status": "ok" if integrity == "ok" and foreign_keys == 1 else "failed",
        "integrity_check": integrity,
        "foreign_keys": foreign_keys,
        "journal_mode": journal_mode,
        "busy_timeout": busy_timeout,
        "synchronous": synchronous,
        "schema_version": version,
    }


def protect_database_file(url: str) -> None:
    path = sqlite_path_from_url(url)
    if not path or not path.exists():
        return
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
