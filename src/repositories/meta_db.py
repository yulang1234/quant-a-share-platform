"""V1.4.1 Meta-database repository utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.meta_engine import get_meta_session


def get_session() -> Session:
    """Return a new meta-database session."""
    return get_meta_session()
