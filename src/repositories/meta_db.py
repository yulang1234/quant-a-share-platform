"""V1.4.1 Meta-database repository utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.meta_engine import get_meta_engine, get_meta_session


_ready_engine_id: int | None = None


def _ensure_meta_schema_ready() -> None:
    """Apply idempotent meta DB migrations before handing out sessions."""
    global _ready_engine_id
    engine = get_meta_engine()
    engine_id = id(engine)
    if _ready_engine_id == engine_id:
        return
    from src.db.migrations import init_meta_db
    init_meta_db()
    _ready_engine_id = engine_id


def get_session() -> Session:
    """Return a new meta-database session."""
    _ensure_meta_schema_ready()
    return get_meta_session()
