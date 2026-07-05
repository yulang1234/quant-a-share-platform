"""V1.4.1 Meta-database engine — PostgreSQL with SQLite fallback."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_meta_db_url, get_project_root

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_meta_engine() -> Engine:
    """Return the SQLAlchemy engine for the meta database.

    Lazy-initialised; safe to call multiple times.
    """
    global _engine
    if _engine is None:
        url = get_meta_db_url()
        logger.info("Meta DB engine: %s", _split_url_for_log(url))
        _engine = create_engine(url, echo=False)
    return _engine


def get_meta_session() -> Session:
    """Return a new SQLAlchemy Session for the meta database."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_meta_engine())
    return _SessionLocal()


def reset_meta_engine() -> None:
    """Close and reset the engine (mainly for testing)."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def _split_url_for_log(url: str) -> str:
    """Return a safe version of the DB URL for logging (no password)."""
    if "@" in url:
        prefix, suffix = url.split("@", 1)
        return f"{prefix.split(':')[0]}:****@{suffix}"
    return url
