"""PositionDiagnosisRepository — CRUD for portfolio_position_diagnosis (V1.7.2)."""

from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.db.schema_meta import PortfolioPositionDiagnosis


class PositionDiagnosisRepository:
    """Repository for portfolio_position_diagnosis (SQLite via SQLAlchemy)."""

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

    # ── Read ─────────────────────────────────────────────────────────────

    def get_by_id(self, diagnosis_id: int) -> PortfolioPositionDiagnosis | None:
        return (
            self._session.query(PortfolioPositionDiagnosis)
            .filter_by(diagnosis_id=diagnosis_id)
            .first()
        )

    def get_by_position_and_date(
        self, position_id: int, trade_date: str
    ) -> PortfolioPositionDiagnosis | None:
        td = _to_date(trade_date)
        return (
            self._session.query(PortfolioPositionDiagnosis)
            .filter_by(position_id=position_id, trade_date=td)
            .first()
        )

    def get_latest_by_position(
        self, position_id: int
    ) -> PortfolioPositionDiagnosis | None:
        return (
            self._session.query(PortfolioPositionDiagnosis)
            .filter_by(position_id=position_id)
            .order_by(PortfolioPositionDiagnosis.trade_date.desc())
            .first()
        )

    def list_diagnoses(
        self,
        trade_date: str | None = None,
        portfolio_name: str | None = None,
        stock_code: str | None = None,
        diagnosis_status: str | None = None,
        suggested_action: str | None = None,
        limit: int = 500,
    ) -> list[PortfolioPositionDiagnosis]:
        q = self._session.query(PortfolioPositionDiagnosis)
        if trade_date:
            q = q.filter_by(trade_date=_to_date(trade_date))
        if portfolio_name:
            q = q.filter_by(portfolio_name=portfolio_name)
        if stock_code:
            q = q.filter_by(stock_code=stock_code)
        if diagnosis_status:
            q = q.filter_by(diagnosis_status=diagnosis_status)
        if suggested_action:
            q = q.filter_by(suggested_action=suggested_action)
        q = q.order_by(
            PortfolioPositionDiagnosis.trade_date.desc(),
            PortfolioPositionDiagnosis.health_score.desc(),
        )
        return q.limit(limit).all()

    def list_history(self, position_id: int, limit: int = 100) -> list[PortfolioPositionDiagnosis]:
        return (
            self._session.query(PortfolioPositionDiagnosis)
            .filter_by(position_id=position_id)
            .order_by(PortfolioPositionDiagnosis.trade_date.desc())
            .limit(limit)
            .all()
        )

    def count_by_status(
        self,
        trade_date: str | None = None,
        portfolio_name: str | None = None,
    ) -> dict[str, int]:
        q = self._session.query(PortfolioPositionDiagnosis)
        if trade_date:
            q = q.filter_by(trade_date=_to_date(trade_date))
        if portfolio_name:
            q = q.filter_by(portfolio_name=portfolio_name)

        counts: dict[str, int] = {}
        for row in q.all():
            status = row.diagnosis_status or "unknown"
            counts[status] = counts.get(status, 0) + 1
            action = row.suggested_action or "unknown"
            counts[f"action_{action}"] = counts.get(f"action_{action}", 0) + 1
        return counts

    # ── Write ────────────────────────────────────────────────────────────

    def upsert_diagnosis(self, **kwargs: Any) -> PortfolioPositionDiagnosis:
        """Insert or update a diagnosis for the same (position_id, trade_date).

        Idempotent: if a diagnosis already exists for this position+date,
        the existing row is updated instead of inserting a duplicate.
        """
        position_id = kwargs.get("position_id")
        trade_date = kwargs.get("trade_date")

        if isinstance(trade_date, str):
            td = _to_date(trade_date)
        else:
            td = trade_date

        existing = (
            self._session.query(PortfolioPositionDiagnosis)
            .filter_by(position_id=position_id, trade_date=td)
            .first()
        )

        if existing:
            # Update all fields except primary key
            for key, value in kwargs.items():
                if hasattr(existing, key) and key not in ("diagnosis_id",):
                    if key == "trade_date" and isinstance(value, str):
                        value = _to_date(value)
                    setattr(existing, key, value)
            existing.updated_at = datetime.now()
            self._commit()
            return existing

        pos = PortfolioPositionDiagnosis(**kwargs)
        if isinstance(pos.trade_date, str):
            pos.trade_date = _to_date(pos.trade_date)
        self._session.add(pos)
        self._commit()
        return pos


def _to_date(value: str | None) -> date_type | None:
    """Convert a YYYY-MM-DD string to a date object."""
    if not value:
        return None
    if isinstance(value, date_type):
        return value
    try:
        return date_type.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
