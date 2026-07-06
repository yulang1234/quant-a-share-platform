"""V1.4.1 Meta-database migrations.

Usage::

    python -m src.db.migrations init_meta_db
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.schema_meta import ALL_TABLES, Base, DataProviderConfig


def _column_type(engine, logical_type: str) -> str:
    """Return a portable SQL type for lightweight additive migrations."""
    if logical_type == "bool":
        return "BOOLEAN DEFAULT 0" if engine.dialect.name == "sqlite" else "BOOLEAN DEFAULT FALSE"
    if logical_type == "datetime":
        return "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP"
    return logical_type


def _add_column_if_missing(engine, table_name: str, column_name: str, column_type: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    if column_name in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def _apply_additive_migrations(engine) -> None:
    """Add V1.4.6 columns to existing meta DBs without touching old data."""
    for column_name, column_type in {
        "is_suspended": _column_type(engine, "bool"),
        "data_source": "VARCHAR(32)",
    }.items():
        _add_column_if_missing(engine, "security_master", column_name, column_type)

    for column_name, column_type in {
        "calendar_source": "VARCHAR(32) DEFAULT 'generated'",
        "is_real_calendar": _column_type(engine, "bool"),
        "source_provider": "VARCHAR(32)",
        "source_updated_at": _column_type(engine, "datetime"),
    }.items():
        _add_column_if_missing(engine, "trading_calendar", column_name, column_type)

    for column_name, column_type in {
        "supports_calendar": _column_type(engine, "bool"),
        "supports_stock_basic": _column_type(engine, "bool"),
    }.items():
        _add_column_if_missing(engine, "data_provider_config", column_name, column_type)

    # V1.4.7: batch_id on data_load_task
    _add_column_if_missing(engine, "data_load_task", "batch_id", "VARCHAR(64)")


def init_meta_db() -> None:
    """Create all meta-database tables if they do not exist."""
    engine = get_meta_engine()
    Base.metadata.create_all(engine)
    _apply_additive_migrations(engine)

    # Seed default provider configs
    from sqlalchemy.orm import Session
    defaults = [
        ("local_cache", "local", 1),
        ("miniqmt", "remote", 2),
        ("tushare", "remote", 3),
        ("akshare", "remote", 4),
    ]
    with Session(engine) as session:
        for name, ptype, pri in defaults:
            existing = session.query(DataProviderConfig).filter_by(provider_name=name).first()
            if not existing:
                session.add(DataProviderConfig(
                    provider_name=name, provider_type=ptype, priority=pri,
                    enabled=True, supports_daily=True,
                ))
        session.commit()
    print(f"Meta DB initialised: {len(ALL_TABLES)} tables created, 4 default providers seeded.")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "init_meta_db":
        print("Usage: python -m src.db.migrations init_meta_db")
        return 1
    init_meta_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
