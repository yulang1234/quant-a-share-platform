"""Test PortfolioPositionRepository — CRUD, filters, constraints, rollback."""

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.portfolio.position_types import (
    DuplicateActivePositionError,
    PositionAlreadyClosedError,
    PositionNotFoundError,
)
from src.repositories.portfolio_position_repo import PortfolioPositionRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_repo.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _make_kwargs(**overrides):
    """Return default kwargs for creating a position."""
    defaults = {
        "portfolio_name": "default",
        "stock_code": "000001",
        "exchange": "SZ",
        "stock_name": "平安银行",
        "buy_date": "2026-06-01",
        "avg_cost": 12.50,
        "quantity": 1000,
        "position_pct": 10.0,
        "buy_reason": "测试买入",
        "is_simulated": False,
    }
    defaults.update(overrides)
    return defaults


class TestCreate:
    def test_create_real_position(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        assert pos.position_id is not None
        assert pos.status == "active"
        assert pos.is_simulated is False

    def test_create_simulated_position(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs(is_simulated=True, stock_code="600519"))
        assert pos.is_simulated is True

    def test_duplicate_active_blocked(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs())
        with pytest.raises(DuplicateActivePositionError):
            repo.create_position(**_make_kwargs())

    def test_same_stock_real_and_simulated_coexist(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs(is_simulated=False))
        repo.create_position(**_make_kwargs(is_simulated=True))
        assert repo.count_positions(status="active") == 2

    def test_reopen_after_close(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.close_position(pos.position_id)
        # Should be able to create a new active position for the same stock
        pos2 = repo.create_position(**_make_kwargs())
        assert pos2.position_id != pos.position_id
        assert pos2.status == "active"


class TestQuery:
    def test_get_by_id(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        found = repo.get_by_id(pos.position_id)
        assert found is not None
        assert found.stock_code == "000001"

    def test_get_by_id_missing(self) -> None:
        repo = PortfolioPositionRepository()
        assert repo.get_by_id(99999) is None

    def test_list_active(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs(is_simulated=True, stock_code="600519"))
        repo.create_position(**_make_kwargs(is_simulated=False))
        # Close one
        sim_pos = repo.find_active_position("default", "600519", True)
        repo.close_position(sim_pos.position_id)
        active = repo.list_positions(status="active")
        assert len(active) == 1
        assert active[0].stock_code == "000001"

    def test_list_by_portfolio(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs(portfolio_name="test_pf", stock_code="000002"))
        repo.create_position(**_make_kwargs(portfolio_name="default"))
        result = repo.list_positions(portfolio_name="test_pf")
        assert len(result) == 1
        assert result[0].stock_code == "000002"

    def test_list_by_is_simulated(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs(is_simulated=False))
        repo.create_position(**_make_kwargs(is_simulated=True, stock_code="600519"))
        sim = repo.list_positions(is_simulated=True)
        assert len(sim) == 1
        assert sim[0].stock_code == "600519"

    def test_list_by_stock_code(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs())
        repo.create_position(**_make_kwargs(stock_code="000002"))
        result = repo.list_positions(stock_code="000002")
        assert len(result) == 1

    def test_limit_applied(self) -> None:
        repo = PortfolioPositionRepository()
        for i in range(5):
            repo.create_position(**_make_kwargs(
                stock_code=f"{i:06d}", is_simulated=True,
            ))
        result = repo.list_positions(limit=3)
        assert len(result) <= 3


class TestUpdate:
    def test_update_cost(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.update_position(pos.position_id, avg_cost=15.0)
        updated = repo.get_by_id(pos.position_id)
        assert updated.avg_cost == 15.0

    def test_update_quantity(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.update_position(pos.position_id, quantity=2000)
        updated = repo.get_by_id(pos.position_id)
        assert updated.quantity == 2000

    def test_update_position_pct(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.update_position(pos.position_id, position_pct=25.0)
        updated = repo.get_by_id(pos.position_id)
        assert updated.position_pct == 25.0

    def test_update_buy_reason(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.update_position(pos.position_id, buy_reason="新理由")
        updated = repo.get_by_id(pos.position_id)
        assert updated.buy_reason == "新理由"

    def test_update_missing_position_raises(self) -> None:
        repo = PortfolioPositionRepository()
        with pytest.raises(PositionNotFoundError):
            repo.update_position(99999, avg_cost=10.0)


class TestClose:
    def test_close_position(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        closed = repo.close_position(pos.position_id)
        assert closed.status == "closed"
        assert closed.closed_at is not None

    def test_closed_position_persists(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.close_position(pos.position_id)
        found = repo.get_by_id(pos.position_id)
        assert found is not None
        assert found.status == "closed"

    def test_double_close_raises(self) -> None:
        repo = PortfolioPositionRepository()
        pos = repo.create_position(**_make_kwargs())
        repo.close_position(pos.position_id)
        with pytest.raises(PositionAlreadyClosedError):
            repo.close_position(pos.position_id)

    def test_close_missing_raises(self) -> None:
        repo = PortfolioPositionRepository()
        with pytest.raises(PositionNotFoundError):
            repo.close_position(99999)


class TestSummary:
    def test_build_summary(self) -> None:
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs(is_simulated=False))
        repo.create_position(**_make_kwargs(is_simulated=True, stock_code="600519"))
        summary = repo.build_summary()
        assert summary.total_count == 2
        assert summary.active_count == 2
        assert summary.real_count == 1
        assert summary.simulated_count == 1


class TestRollback:
    def test_constraint_violation_does_not_crash(self) -> None:
        """VERIFY: duplicate detection in app layer prevents DB constraint errors."""
        repo = PortfolioPositionRepository()
        repo.create_position(**_make_kwargs())
        # Duplicate raises app-level exception, not DB integrity error
        with pytest.raises(DuplicateActivePositionError):
            repo.create_position(**_make_kwargs())
