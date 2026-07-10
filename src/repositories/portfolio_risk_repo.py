"""PortfolioRiskRepository — CRUD for portfolio_risk_snapshot (V1.7.3)."""

from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.db.schema_meta import PortfolioRiskSnapshot


class PortfolioRiskRepository:
    def __init__(self, session: Session | None = None) -> None:
        from src.repositories.meta_db import get_session
        self._session = session or get_session()
        self._own_session = session is None

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def get_by_id(self, risk_snapshot_id: int) -> PortfolioRiskSnapshot | None:
        return self._session.query(PortfolioRiskSnapshot).filter_by(risk_snapshot_id=risk_snapshot_id).first()

    def get_by_portfolio_and_date(
        self, trade_date: str, portfolio_name: str, is_simulated: bool
    ) -> PortfolioRiskSnapshot | None:
        td = _to_date(trade_date)
        return self._session.query(PortfolioRiskSnapshot).filter_by(
            trade_date=td, portfolio_name=portfolio_name, is_simulated=is_simulated,
        ).first()

    def get_latest(self, portfolio_name: str = "default", is_simulated: bool = False) -> PortfolioRiskSnapshot | None:
        return self._session.query(PortfolioRiskSnapshot).filter_by(
            portfolio_name=portfolio_name, is_simulated=is_simulated,
        ).order_by(PortfolioRiskSnapshot.trade_date.desc()).first()

    def list_history(
        self, portfolio_name: str = "default", is_simulated: bool = False, limit: int = 100
    ) -> list[PortfolioRiskSnapshot]:
        return self._session.query(PortfolioRiskSnapshot).filter_by(
            portfolio_name=portfolio_name, is_simulated=is_simulated,
        ).order_by(PortfolioRiskSnapshot.trade_date.desc()).limit(limit).all()

    def list_daily_snapshots(self, trade_date: str, limit: int = 500) -> list[PortfolioRiskSnapshot]:
        return self._session.query(PortfolioRiskSnapshot).filter_by(
            trade_date=_to_date(trade_date),
        ).order_by(PortfolioRiskSnapshot.portfolio_risk_score.desc()).limit(limit).all()

    def count_by_level(self, trade_date: str | None = None) -> dict[str, int]:
        q = self._session.query(PortfolioRiskSnapshot)
        if trade_date:
            q = q.filter_by(trade_date=_to_date(trade_date))
        counts: dict[str, int] = {}
        for row in q.all():
            level = row.portfolio_risk_level or "unknown"
            counts[level] = counts.get(level, 0) + 1
        return counts

    def upsert_snapshot(self, **kwargs: Any) -> PortfolioRiskSnapshot:
        trade_date = kwargs.get("trade_date")
        portfolio_name = kwargs.get("portfolio_name", "default")
        is_simulated = kwargs.get("is_simulated", True)

        td = _to_date(trade_date) if isinstance(trade_date, str) else trade_date
        existing = self._session.query(PortfolioRiskSnapshot).filter_by(
            trade_date=td, portfolio_name=portfolio_name, is_simulated=is_simulated,
        ).first()

        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key) and key not in ("risk_snapshot_id",):
                    if key == "trade_date" and isinstance(value, str):
                        value = _to_date(value)
                    setattr(existing, key, value)
            existing.updated_at = datetime.now()
            self._commit()
            return existing

        snap = PortfolioRiskSnapshot(**kwargs)
        if isinstance(snap.trade_date, str):
            snap.trade_date = _to_date(snap.trade_date)
        self._session.add(snap)
        self._commit()
        return snap


def _to_date(value: str | None) -> date_type | None:
    if not value:
        return None
    if isinstance(value, date_type):
        return value
    try:
        return date_type.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
