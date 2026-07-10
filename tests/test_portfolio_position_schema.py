"""Test PortfolioPosition schema — table creation, idempotence, constraints."""

import pytest
from sqlalchemy import inspect, text

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.migrations import init_meta_db
from src.db.schema_meta import ALL_TABLES, PortfolioPosition


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_schema.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestPortfolioPositionSchema:
    """Verify that portfolio_position table is created and behaves correctly."""

    def test_init_meta_db_creates_portfolio_position(self) -> None:
        engine = get_meta_engine()
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "portfolio_position" in table_names

    def test_init_meta_db_idempotent(self) -> None:
        """Calling init_meta_db twice should not error."""
        # First call already done in fixture; second call should be safe
        init_meta_db()
        engine = get_meta_engine()
        inspector = inspect(engine)
        assert "portfolio_position" in inspector.get_table_names()

    def test_all_tables_includes_portfolio_position(self) -> None:
        assert PortfolioPosition in ALL_TABLES

    def test_table_has_expected_columns(self) -> None:
        engine = get_meta_engine()
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("portfolio_position")}
        expected = {
            "position_id", "portfolio_name", "stock_code", "exchange",
            "stock_name", "buy_date", "avg_cost", "quantity", "position_pct",
            "buy_reason", "sector_name", "original_strategy",
            "entry_snapshot_json", "snapshot_version", "user_note",
            "is_simulated", "source", "status", "closed_at",
            "created_at", "updated_at",
        }
        assert expected.issubset(columns)

    def test_does_not_affect_existing_tables(self) -> None:
        """Existing tables like security_master should still exist."""
        engine = get_meta_engine()
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "security_master" in table_names
        assert "universe_config" in table_names

    def test_sqlite_can_insert_and_query(self) -> None:
        """Basic insert/query to verify ORM-SQLite compatibility."""
        from datetime import date

        from src.db.meta_engine import get_meta_session

        session = get_meta_session()
        pos = PortfolioPosition(
            portfolio_name="default",
            stock_code="000001",
            exchange="SZ",
            stock_name="平安银行",
            buy_date=date(2026, 1, 15),
            avg_cost=12.50,
            quantity=1000,
            position_pct=10.0,
            buy_reason="测试买入理由",
            is_simulated=False,
        )
        session.add(pos)
        session.commit()

        found = session.query(PortfolioPosition).filter_by(stock_code="000001").first()
        assert found is not None
        assert found.stock_name == "平安银行"
        assert found.position_pct == 10.0
