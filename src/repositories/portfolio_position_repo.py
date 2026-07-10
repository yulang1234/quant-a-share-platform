"""PortfolioPositionRepository — CRUD for portfolio_position table (V1.7.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.db.schema_meta import PortfolioPosition
from src.portfolio.position_types import (
    DuplicateActivePositionError,
    PositionAlreadyClosedError,
    PositionNotFoundError,
    PositionSummary,
)


class PortfolioPositionRepository:
    """Repository for portfolio_position (SQLite via SQLAlchemy).

    Session can be injected; otherwise a new session is obtained from
    ``src.repositories.meta_db.get_session``.
    """

    def __init__(self, session: Session | None = None) -> None:
        from src.repositories.meta_db import get_session

        self._session = session or get_session()
        self._own_session = session is None

    # ── helpers ──────────────────────────────────────────────────────────

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    # ── queries ──────────────────────────────────────────────────────────

    def get_by_id(self, position_id: int) -> PortfolioPosition | None:
        """Return a single position by primary key, or None."""
        return (
            self._session.query(PortfolioPosition)
            .filter_by(position_id=position_id)
            .first()
        )

    def find_active_position(
        self, portfolio_name: str, stock_code: str, is_simulated: bool
    ) -> PortfolioPosition | None:
        """Return the active position for a given stock in a portfolio, if any."""
        return (
            self._session.query(PortfolioPosition)
            .filter_by(
                portfolio_name=portfolio_name,
                stock_code=stock_code,
                is_simulated=is_simulated,
                status="active",
            )
            .first()
        )

    def exists_active_position(
        self, portfolio_name: str, stock_code: str, is_simulated: bool
    ) -> bool:
        """Return True if an active position already exists for this stock."""
        return self.find_active_position(portfolio_name, stock_code, is_simulated) is not None

    def list_positions(
        self,
        portfolio_name: str | None = None,
        status: str | None = None,
        is_simulated: bool | None = None,
        stock_code: str | None = None,
        sector_name: str | None = None,
        limit: int = 500,
    ) -> list[PortfolioPosition]:
        """List positions with optional filters, ordered by active-first then buy_date desc."""
        q = self._session.query(PortfolioPosition)
        if portfolio_name:
            q = q.filter_by(portfolio_name=portfolio_name)
        if status:
            q = q.filter_by(status=status)
        if is_simulated is not None:
            q = q.filter_by(is_simulated=is_simulated)
        if stock_code:
            q = q.filter_by(stock_code=stock_code)
        if sector_name:
            q = q.filter_by(sector_name=sector_name)
        q = q.order_by(
            PortfolioPosition.status.asc(),  # "active" < "closed" alphabetically
            PortfolioPosition.buy_date.desc(),
            PortfolioPosition.created_at.desc(),
        )
        return q.limit(limit).all()

    def count_positions(
        self,
        portfolio_name: str | None = None,
        status: str | None = None,
        is_simulated: bool | None = None,
    ) -> int:
        """Return count of positions matching the given filters."""
        q = self._session.query(PortfolioPosition)
        if portfolio_name:
            q = q.filter_by(portfolio_name=portfolio_name)
        if status:
            q = q.filter_by(status=status)
        if is_simulated is not None:
            q = q.filter_by(is_simulated=is_simulated)
        return q.count()

    def build_summary(
        self,
        portfolio_name: str | None = None,
        is_simulated: bool | None = None,
    ) -> PositionSummary:
        """Build a summary with counts and total position_pct."""
        positions = self.list_positions(
            portfolio_name=portfolio_name,
            is_simulated=is_simulated,
            limit=10000,
        )
        active = [p for p in positions if p.status == "active"]
        closed = [p for p in positions if p.status == "closed"]
        real = [p for p in positions if not p.is_simulated]
        sim = [p for p in positions if p.is_simulated]
        total_pct = sum(p.position_pct or 0 for p in active)
        return PositionSummary(
            total_count=len(positions),
            active_count=len(active),
            closed_count=len(closed),
            real_count=len(real),
            simulated_count=len(sim),
            total_position_pct=round(total_pct, 2),
            position_pct_ok=total_pct <= 100,
        )

    # ── mutations ────────────────────────────────────────────────────────

    def create_position(self, **kwargs: Any) -> PortfolioPosition:
        """Create a new position row.

        Raises:
            DuplicateActivePositionError: if an active position already exists
                for the same (portfolio_name, stock_code, is_simulated).
        """
        portfolio_name = kwargs.get("portfolio_name", "default")
        stock_code = kwargs["stock_code"]
        is_simulated = kwargs.get("is_simulated", True)

        if self.exists_active_position(portfolio_name, stock_code, is_simulated):
            raise DuplicateActivePositionError(portfolio_name, stock_code, is_simulated)

        # Convert buy_date string to date object if needed
        if "buy_date" in kwargs and isinstance(kwargs["buy_date"], str):
            from datetime import date as date_type
            kwargs["buy_date"] = date_type.fromisoformat(kwargs["buy_date"])

        pos = PortfolioPosition(**kwargs)
        self._session.add(pos)
        self._commit()
        return pos

    def update_position(self, position_id: int, **changes: Any) -> PortfolioPosition:
        """Update allowed fields on an existing position.

        Raises:
            PositionNotFoundError: if the position does not exist.
        """
        pos = self.get_by_id(position_id)
        if pos is None:
            raise PositionNotFoundError(position_id)

        allowed = {
            "portfolio_name",
            "stock_name",
            "avg_cost",
            "quantity",
            "position_pct",
            "buy_reason",
            "sector_name",
            "original_strategy",
            "user_note",
        }
        for key, value in changes.items():
            if key in allowed and value is not None:
                setattr(pos, key, value)

        self._commit()
        return pos

    def close_position(
        self, position_id: int, closed_at: datetime | None = None
    ) -> PortfolioPosition:
        """Mark a position as closed. Data is preserved — no physical delete.

        Raises:
            PositionNotFoundError: if the position does not exist.
            PositionAlreadyClosedError: if the position is already closed.
        """
        pos = self.get_by_id(position_id)
        if pos is None:
            raise PositionNotFoundError(position_id)
        if pos.status == "closed":
            raise PositionAlreadyClosedError(position_id)

        pos.status = "closed"
        pos.closed_at = closed_at or datetime.now()
        self._commit()
        return pos

    def _delete_for_test(self, position_id: int) -> None:
        """Physical delete — for test maintenance only. Not exposed in UI."""
        pos = self.get_by_id(position_id)
        if pos is not None:
            self._session.delete(pos)
            self._commit()
