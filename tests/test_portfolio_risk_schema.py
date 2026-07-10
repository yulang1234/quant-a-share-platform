"""Test PortfolioRiskSnapshot schema."""

import pytest
from sqlalchemy import inspect

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.migrations import init_meta_db
from src.db.schema_meta import ALL_TABLES, PortfolioRiskSnapshot


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_risk_schema.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestRiskSchema:
    def test_table_created(self) -> None:
        assert "portfolio_risk_snapshot" in inspect(get_meta_engine()).get_table_names()

    def test_in_all_tables(self) -> None:
        assert PortfolioRiskSnapshot in ALL_TABLES

    def test_idempotent(self) -> None:
        init_meta_db()
        assert "portfolio_risk_snapshot" in inspect(get_meta_engine()).get_table_names()

    def test_does_not_drop_other_tables(self) -> None:
        tables = inspect(get_meta_engine()).get_table_names()
        assert "portfolio_position" in tables
        assert "portfolio_position_diagnosis" in tables

    def test_expected_columns(self) -> None:
        cols = {c["name"] for c in inspect(get_meta_engine()).get_columns("portfolio_risk_snapshot")}
        assert "risk_snapshot_id" in cols
        assert "portfolio_risk_score" in cols
        assert "average_pairwise_correlation" in cols
