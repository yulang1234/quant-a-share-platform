"""Test PositionDiagnosisRepository — upsert, query, history, idempotence."""

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_diag_repo.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _make_kwargs(**overrides):
    d = {
        "position_id": 1,
        "trade_date": "2026-07-01",
        "portfolio_name": "default",
        "stock_code": "000001",
        "stock_name": "平安银行",
        "sector_name": "银行",
        "diagnosis_status": "healthy",
        "suggested_action": "continue_hold",
        "thesis_status": "valid",
        "health_score": 85.0,
        "data_coverage_ratio": 0.9,
        "market_support_score": 80.0,
        "sentiment_support_score": 75.0,
        "sector_support_score": 90.0,
        "leader_support_score": 85.0,
        "trend_health_score": 88.0,
        "condition_support_score": 80.0,
        "thesis_score": 80.0,
        "reason_summary": "",
        "risk_warnings_json": "[]",
        "observation_conditions_json": "[]",
        "invalidation_conditions_json": "[]",
        "evidence_json": "[]",
        "current_context_json": "{}",
        "data_quality_status": "ok",
        "issue_summary": "",
           }
    d.update(overrides)
    return d


class TestUpsert:
    def test_create_diagnosis(self) -> None:
        repo = PositionDiagnosisRepository()
        diag = repo.upsert_diagnosis(**_make_kwargs())
        assert diag.diagnosis_id is not None
        assert diag.diagnosis_status == "healthy"

    def test_upsert_idempotent(self) -> None:
        repo = PositionDiagnosisRepository()
        d1 = repo.upsert_diagnosis(**_make_kwargs())
        d2 = repo.upsert_diagnosis(**_make_kwargs(health_score=90.0))
        assert d1.diagnosis_id == d2.diagnosis_id
        assert d2.health_score == 90.0

    def test_different_dates_create_separate_rows(self) -> None:
        repo = PositionDiagnosisRepository()
        d1 = repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-01"))
        d2 = repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-02"))
        assert d1.diagnosis_id != d2.diagnosis_id


class TestQuery:
    def test_get_by_position_and_date(self) -> None:
        repo = PositionDiagnosisRepository()
        repo.upsert_diagnosis(**_make_kwargs())
        diag = repo.get_by_position_and_date(1, "2026-07-01")
        assert diag is not None
        assert diag.stock_code == "000001"

    def test_get_latest(self) -> None:
        repo = PositionDiagnosisRepository()
        repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-01", health_score=70))
        repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-02", health_score=80))
        latest = repo.get_latest_by_position(1)
        assert latest.health_score == 80

    def test_list_by_status(self) -> None:
        repo = PositionDiagnosisRepository()
        repo.upsert_diagnosis(**_make_kwargs(position_id=1, diagnosis_status="healthy"))
        repo.upsert_diagnosis(**_make_kwargs(position_id=2, stock_code="600519", diagnosis_status="cautious"))
        healthy = repo.list_diagnoses(diagnosis_status="healthy")
        assert len(healthy) == 1

    def test_list_by_trade_date(self) -> None:
        repo = PositionDiagnosisRepository()
        repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-01"))
        repo.upsert_diagnosis(**_make_kwargs(trade_date="2026-07-02", position_id=2))
        diags = repo.list_diagnoses(trade_date="2026-07-01")
        assert len(diags) == 1

    def test_list_history(self) -> None:
        repo = PositionDiagnosisRepository()
        for i in range(3):
            repo.upsert_diagnosis(**_make_kwargs(
                trade_date=f"2026-07-0{i+1}", health_score=70 + i,
            ))
        history = repo.list_history(1)
        assert len(history) == 3

    def test_limit_applied(self) -> None:
        repo = PositionDiagnosisRepository()
        for i in range(5):
            repo.upsert_diagnosis(**_make_kwargs(
                position_id=i + 1, stock_code=f"{i:06d}", trade_date=f"2026-07-0{i+1}",
            ))
        result = repo.list_diagnoses(limit=3)
        assert len(result) <= 3

    def test_count_by_status(self) -> None:
        repo = PositionDiagnosisRepository()
        repo.upsert_diagnosis(**_make_kwargs(position_id=1, diagnosis_status="healthy"))
        repo.upsert_diagnosis(**_make_kwargs(position_id=2, diagnosis_status="cautious", stock_code="600519"))
        repo.upsert_diagnosis(**_make_kwargs(position_id=3, diagnosis_status="healthy", stock_code="000002"))
        counts = repo.count_by_status()
        assert counts.get("healthy", 0) >= 2
