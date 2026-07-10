"""Test PortfolioPositionDiagnosis schema — table creation, idempotence, constraints."""

import pytest
from sqlalchemy import inspect

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.migrations import init_meta_db
from src.db.schema_meta import ALL_TABLES, PortfolioPositionDiagnosis


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_diag_schema.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestDiagnosisSchema:
    def test_table_created(self) -> None:
        engine = get_meta_engine()
        inspector = inspect(engine)
        assert "portfolio_position_diagnosis" in inspector.get_table_names()

    def test_all_tables_includes_diagnosis(self) -> None:
        assert PortfolioPositionDiagnosis in ALL_TABLES

    def test_init_meta_db_idempotent(self) -> None:
        init_meta_db()
        engine = get_meta_engine()
        assert "portfolio_position_diagnosis" in inspect(engine).get_table_names()

    def test_does_not_drop_portfolio_position(self) -> None:
        engine = get_meta_engine()
        inspector = inspect(engine)
        assert "portfolio_position" in inspector.get_table_names()

    def test_expected_columns(self) -> None:
        engine = get_meta_engine()
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("portfolio_position_diagnosis")}
        expected = {
            "diagnosis_id", "position_id", "trade_date", "portfolio_name",
            "stock_code", "stock_name", "sector_name", "diagnosis_status",
            "suggested_action", "thesis_status", "market_support_score",
            "sentiment_support_score", "sector_support_score",
            "leader_support_score", "trend_health_score", "condition_support_score",
            "thesis_score", "health_score", "data_coverage_ratio",
            "latest_close", "unrealized_return_pct", "drawdown_20d",
            "position_pct", "position_size_status", "reason_summary",
            "risk_warnings_json", "observation_conditions_json",
            "invalidation_conditions_json", "evidence_json",
            "current_context_json", "data_quality_status",
            "issue_summary", "rule_version", "created_at", "updated_at",
        }
        assert expected.issubset(columns)
