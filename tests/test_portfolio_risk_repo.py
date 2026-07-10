"""Test PortfolioRiskRepository — upsert, query, history."""

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.portfolio_risk_repo import PortfolioRiskRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_risk_repo.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _kw(**overrides):
    d = {"trade_date": "2026-07-01", "portfolio_name": "default", "is_simulated": False,
         "portfolio_risk_score": 45.0, "portfolio_risk_level": "medium", "portfolio_permission": "watch",
         "position_count": 5, "total_position_pct": 60.0,
         "risk_flags_json": "[]", "recommendations_json": "[]",
         "observation_conditions_json": "[]", "risk_release_conditions_json": "[]", "evidence_json": "[]"}
    d.update(overrides)
    return d


class TestRepo:
    def test_create(self) -> None:
        repo = PortfolioRiskRepository()
        snap = repo.upsert_snapshot(**_kw())
        assert snap.risk_snapshot_id is not None

    def test_upsert_idempotent(self) -> None:
        repo = PortfolioRiskRepository()
        s1 = repo.upsert_snapshot(**_kw())
        s2 = repo.upsert_snapshot(**_kw(portfolio_risk_score=55.0))
        assert s1.risk_snapshot_id == s2.risk_snapshot_id
        assert s2.portfolio_risk_score == 55.0

    def test_different_dates_separate(self) -> None:
        repo = PortfolioRiskRepository()
        s1 = repo.upsert_snapshot(**_kw(trade_date="2026-07-01"))
        s2 = repo.upsert_snapshot(**_kw(trade_date="2026-07-02"))
        assert s1.risk_snapshot_id != s2.risk_snapshot_id

    def test_real_and_sim_separate(self) -> None:
        repo = PortfolioRiskRepository()
        s1 = repo.upsert_snapshot(**_kw(is_simulated=False))
        s2 = repo.upsert_snapshot(**_kw(is_simulated=True))
        assert s1.risk_snapshot_id != s2.risk_snapshot_id

    def test_get_latest(self) -> None:
        repo = PortfolioRiskRepository()
        repo.upsert_snapshot(**_kw(trade_date="2026-07-01", portfolio_risk_score=30))
        repo.upsert_snapshot(**_kw(trade_date="2026-07-02", portfolio_risk_score=60))
        latest = repo.get_latest("default", False)
        assert latest.portfolio_risk_score == 60

    def test_list_history(self) -> None:
        repo = PortfolioRiskRepository()
        for i in range(3):
            repo.upsert_snapshot(**_kw(trade_date=f"2026-07-0{i+1}"))
        assert len(repo.list_history()) == 3

    def test_list_daily(self) -> None:
        repo = PortfolioRiskRepository()
        repo.upsert_snapshot(**_kw(trade_date="2026-07-01", portfolio_name="pf1"))
        repo.upsert_snapshot(**_kw(trade_date="2026-07-02", portfolio_name="pf1"))
        daily = repo.list_daily_snapshots("2026-07-01")
        assert len(daily) == 1

    def test_limit(self) -> None:
        repo = PortfolioRiskRepository()
        for i in range(5):
            repo.upsert_snapshot(**_kw(trade_date=f"2026-07-0{i+1}", portfolio_name=f"pf{i}"))
        assert len(repo.list_history()) <= 5
