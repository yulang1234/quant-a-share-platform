"""V1.4.1 Meta-database migrations.

Usage::

    python -m src.db.migrations init_meta_db
"""

from __future__ import annotations

import sys

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.schema_meta import ALL_TABLES, Base, DataProviderConfig


def init_meta_db() -> None:
    """Create all meta-database tables if they do not exist."""
    engine = get_meta_engine()
    Base.metadata.create_all(engine)

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
