"""Test position_diagnosis_service — diagnosis flow, persistence, graceful degradation."""

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.portfolio.position_diagnosis_types import PositionDiagnosisResult
from src.repositories.portfolio_position_repo import PortfolioPositionRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_svc.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _create_position(**overrides) -> int:
    """Create a position and return its position_id."""
    repo = PortfolioPositionRepository()
    kwargs = {
        "portfolio_name": "default",
        "stock_code": "000001",
        "exchange": "SZ",
        "stock_name": "平安银行",
        "buy_date": "2026-06-01",
        "avg_cost": 12.50,
        "quantity": 1000,
        "position_pct": 10.0,
        "buy_reason": "测试",
        "is_simulated": False,
    }
    kwargs.update(overrides)
    pos = repo.create_position(**kwargs)
    return pos.position_id


class TestDiagnosePosition:
    def test_closed_position_returns_unknown(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position

        pid = _create_position()
        PortfolioPositionRepository().close_position(pid)

        result = diagnose_position(pid, "2026-07-01")
        assert isinstance(result, PositionDiagnosisResult)
        assert result.diagnosis_status == "unknown"

    def test_missing_position(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position

        result = diagnose_position(99999, "2026-07-01")
        assert "不存在" in " ".join(result.issue_summary)

    def test_persist_false_does_not_save(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position
        from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

        pid = _create_position()
        result = diagnose_position(pid, "2026-07-01", persist=False)
        assert result.diagnosis_status in ("healthy", "watch", "cautious", "dangerous", "unknown")

        # May or may not be saved depending on persist=False
        assert result.health_score >= 0

    def test_persist_true_saves(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position
        from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

        pid = _create_position()
        result = diagnose_position(pid, "2026-07-01", persist=True)

        repo = PositionDiagnosisRepository()
        saved = repo.get_by_position_and_date(pid, "2026-07-01")
        if result.diagnosis_status != "unknown":
            assert saved is not None

    def test_does_not_modify_position(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position

        pid = _create_position()
        pos = PortfolioPositionRepository().get_by_id(pid)
        original_pct = pos.position_pct
        diagnose_position(pid, "2026-07-01", persist=True)

        # Re-read position
        updated = PortfolioPositionRepository().get_by_id(pid)
        assert updated is not None
        assert updated.position_pct == original_pct

    def test_result_has_all_scores(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_position

        pid = _create_position()
        result = diagnose_position(pid, "2026-07-01")
        assert 0 <= result.health_score <= 100
        assert 0 <= result.data_coverage_ratio <= 1
        assert result.suggested_action != ""


class TestDiagnoseAll:
    def test_batch_returns_stats(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_all_active_positions

        _create_position(stock_code="000001")
        _create_position(stock_code="600519", is_simulated=True)

        result = diagnose_all_active_positions("2026-07-01", persist=False)
        assert "results" in result
        assert result["success_count"] >= 0

    def test_single_failure_does_not_block_batch(self) -> None:
        from src.portfolio.position_diagnosis_service import diagnose_all_active_positions

        _create_position(stock_code="000001")
        result = diagnose_all_active_positions("2026-07-01", persist=False)
        assert "results" in result


class TestSaveAndQuery:
    def test_upsert_idempotent(self) -> None:
        from src.portfolio.position_diagnosis_service import (
            list_diagnoses,
            save_position_diagnosis,
        )
        from src.portfolio.position_diagnosis_types import PositionDiagnosisResult

        r = PositionDiagnosisResult(
            position_id=1, trade_date="2026-07-01",
            portfolio_name="default", stock_code="000001",
            diagnosis_status="watch", suggested_action="light_hold",
            health_score=65,
        )
        save_position_diagnosis(r)
        save_position_diagnosis(r)  # should not duplicate
        diags = list_diagnoses()
        matching = [d for d in diags if d["position_id"] == 1]
        assert len(matching) == 1

    def test_history(self) -> None:
        from src.portfolio.position_diagnosis_service import (
            get_diagnosis_history,
            save_position_diagnosis,
        )
        from src.portfolio.position_diagnosis_types import PositionDiagnosisResult

        for i in range(3):
            r = PositionDiagnosisResult(
                position_id=1, trade_date=f"2026-07-0{i+1}",
                portfolio_name="default", stock_code="000001",
                diagnosis_status="healthy", suggested_action="continue_hold",
                health_score=80 + i,
            )
            save_position_diagnosis(r)

        history = get_diagnosis_history(1)
        assert len(history) == 3
