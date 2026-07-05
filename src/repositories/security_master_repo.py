"""SecurityMasterRepository — CRUD for security_master table."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.schema_meta import SecurityMaster
from src.repositories.meta_db import get_session


class SecurityMasterRepository:
    def __init__(self, session: Session | None = None):
        self._session = session or get_session()

    def add_or_update(self, symbol: str, exchange: str, **kwargs) -> SecurityMaster:
        existing = self._session.query(SecurityMaster).filter_by(
            symbol=str(symbol).zfill(6), exchange=exchange.upper(),
        ).first()
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            self._session.commit()
            return existing
        sec = SecurityMaster(
            symbol=str(symbol).zfill(6), exchange=exchange.upper(), **kwargs,
        )
        self._session.add(sec)
        self._session.commit()
        return sec

    def find_by_symbol(self, symbol: str, exchange: str) -> SecurityMaster | None:
        return self._session.query(SecurityMaster).filter_by(
            symbol=str(symbol).zfill(6), exchange=exchange.upper(),
        ).first()

    def list_all(self, limit: int = 500) -> list[SecurityMaster]:
        return self._session.query(SecurityMaster).limit(limit).all()

    def count(self) -> int:
        return self._session.query(SecurityMaster).count()
