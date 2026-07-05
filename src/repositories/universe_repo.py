"""UniverseRepository — CRUD for universe_config and universe_member."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.schema_meta import UniverseConfig, UniverseMember
from src.repositories.meta_db import get_session


class UniverseRepository:
    def __init__(self, session: Session | None = None):
        self._session = session or get_session()

    def add_universe(self, name: str, description: str = "", asset_type: str = "stock") -> UniverseConfig:
        existing = self._session.query(UniverseConfig).filter_by(universe_name=name).first()
        if existing:
            return existing
        u = UniverseConfig(universe_name=name, description=description, asset_type=asset_type)
        self._session.add(u)
        self._session.commit()
        return u

    def list_universes(self) -> list[UniverseConfig]:
        return self._session.query(UniverseConfig).all()

    def add_member(self, universe_id: int, symbol: str, exchange: str, **kwargs) -> UniverseMember:
        existing = self._session.query(UniverseMember).filter_by(
            universe_id=universe_id,
            symbol=str(symbol).zfill(6),
            exchange=exchange.upper(),
        ).first()
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            self._session.commit()
            return existing
        m = UniverseMember(
            universe_id=universe_id, symbol=str(symbol).zfill(6),
            exchange=exchange.upper(), **kwargs,
        )
        self._session.add(m)
        self._session.commit()
        return m

    def list_members(self, universe_id: int) -> list[UniverseMember]:
        return self._session.query(UniverseMember).filter_by(universe_id=universe_id).all()

    def count_members(self, universe_id: int) -> int:
        return self._session.query(UniverseMember).filter_by(universe_id=universe_id).count()
