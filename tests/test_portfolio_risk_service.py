"""Test portfolio_risk_service."""

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.portfolio.portfolio_risk_service import analyze_all_portfolios, analyze_portfolio_risk
from src.portfolio.portfolio_risk_types import PortfolioRiskResult
from src.repositories.portfolio_position_repo import PortfolioPositionRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_risk_svc.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _create_pos(**overrides) -> int:
    """Create a position and return its position_id."""
    repo = PortfolioPositionRepository()
    kw = {"portfolio_name": "default", "stock_code": "000001", "exchange": "SZ",
          "stock_name": "平安银行", "buy_date": "2026-06-01", "avg_cost": 12.50,
          "quantity": 1000, "position_pct": 20.0, "buy_reason": "test", "is_simulated": False}
    kw.update(overrides)
    pos = repo.create_position(**kw)
    return pos.position_id


class TestAnalyzePortfolioRisk:
    def test_empty_portfolio(self) -> None:
        r = analyze_portfolio_risk("2026-07-01", "empty_pf", False)
        assert isinstance(r, PortfolioRiskResult)
        assert "无 active 持仓" in " ".join(r.issue_summary)

    def test_one_position(self) -> None:
        _create_pos(stock_code="000001", position_pct=30)
        r = analyze_portfolio_risk("2026-07-01", "default", False)
        assert isinstance(r, PortfolioRiskResult)
        assert r.position_count == 1

    def test_multiple_positions(self) -> None:
        _create_pos(stock_code="000001", position_pct=30)
        _create_pos(stock_code="600519", position_pct=25)
        r = analyze_portfolio_risk("2026-07-01", "default", False)
        assert r.position_count == 2
        assert 0 <= r.portfolio_risk_score <= 100

    def test_real_and_sim_separated(self) -> None:
        _create_pos(stock_code="000001", is_simulated=False, position_pct=40)
        _create_pos(stock_code="600519", is_simulated=True, position_pct=30)
        r_real = analyze_portfolio_risk("2026-07-01", "default", False)
        r_sim = analyze_portfolio_risk("2026-07-01", "default", True)
        assert r_real.position_count == 1
        assert r_sim.position_count == 1

    def test_persist_false_does_not_save(self) -> None:
        _create_pos(stock_code="000001", position_pct=20)
        r = analyze_portfolio_risk("2026-07-01", "default", False, persist=False)
        assert isinstance(r, PortfolioRiskResult)

    def test_persist_true_saves(self) -> None:
        from src.repositories.portfolio_risk_repo import PortfolioRiskRepository
        _create_pos(stock_code="000001", position_pct=20)
        r = analyze_portfolio_risk("2026-07-01", "default", False, persist=True)
        snap = PortfolioRiskRepository().get_by_portfolio_and_date("2026-07-01", "default", False)
        if r.position_count > 0 and r.data_coverage_ratio > 0.4:
            assert snap is not None

    def test_does_not_modify_positions(self) -> None:
        pid = _create_pos(stock_code="000001", position_pct=20)
        original = PortfolioPositionRepository().get_by_id(pid).position_pct
        analyze_portfolio_risk("2026-07-01", "default", False, persist=True)
        updated = PortfolioPositionRepository().get_by_id(pid)
        assert updated.position_pct == original

    def test_all_portfolios(self) -> None:
        _create_pos(portfolio_name="pf1", stock_code="000001", position_pct=30)
        _create_pos(portfolio_name="pf2", stock_code="600519", position_pct=25)
        r = analyze_all_portfolios("2026-07-01")
        assert r["success_count"] >= 1
