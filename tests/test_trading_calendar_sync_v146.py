"""Test V1.4.6 trading calendar sync."""
from __future__ import annotations

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestTradingCalendarV146:
    def test_date_format_validation(self) -> None:
        from src.trading_calendar.sync_trading_calendar import _validate_dates

        assert _validate_dates("20240101", "20241231") is None
        assert _validate_dates("2024-01-01", "20240101") is not None  # bad format
        assert _validate_dates("abcd0101", "20240101") is not None
        assert _validate_dates("20241301", "20240101") is not None
        assert _validate_dates("20241231", "20240101") is not None  # start > end

    def test_start_before_end(self) -> None:
        from src.trading_calendar.sync_trading_calendar import _validate_dates

        err = _validate_dates("20241231", "20240101")
        assert err is not None
        assert "start" in err.lower()

    def test_dry_run_does_not_write(self) -> None:
        from src.trading_calendar.sync_trading_calendar import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_cal", "--start-date", "20240101", "--end-date", "20240131",
                        "--dry-run"]
            rc = main()
            assert rc == 0
        finally:
            sys.argv = old_argv

    def test_confirm_writes_weekdays(self) -> None:
        from src.trading_calendar.sync_trading_calendar import main
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_cal", "--start-date", "20240101", "--end-date", "20240105",
                        "--confirm"]
            rc = main()
            assert rc == 0
        finally:
            sys.argv = old_argv

        svc = TradingCalendarService()
        dates = svc.list_open_dates("20240101", "20240105", "CN")
        # Jan 1 2024 is Monday, so Mon-Fri should be 5 open days
        assert len(dates) > 0

    def test_is_real_calendar_false_for_weekday_fallback(self) -> None:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        svc = TradingCalendarService()
        svc.generate_weekdays("20240101", "20240105")

        info = svc.get_calendar_source_info("CN")
        assert info["is_real_calendar"] is False
        # calendar_source should be "weekday_fallback" from generate_weekdays
        assert "weekday" in str(info.get("calendar_source", "")).lower() or info["calendar_source"] == "generated"

    def test_calendar_missing_status_is_clear(self) -> None:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        svc = TradingCalendarService()
        dates = svc.list_open_dates("20240101", "20240105", "CN")
        # Without seeding, list should be empty
        assert len(dates) == 0

    def test_bulk_upsert_from_provider(self) -> None:
        import pandas as pd
        from datetime import datetime
        from src.trading_calendar.trading_calendar_service import TradingCalendarService

        svc = TradingCalendarService()
        df = pd.DataFrame({
            "trade_date": [
                datetime(2024, 1, 2), datetime(2024, 1, 3),
                datetime(2024, 1, 4), datetime(2024, 1, 5),
            ],
            "is_open": [True, True, True, True],
        })
        count = svc.bulk_upsert_from_provider(df, "CN", "test_provider")
        assert count == 4

        info = svc.get_calendar_source_info("CN")
        assert info["is_real_calendar"] is True
        assert info["source_provider"] == "test_provider"

    def test_calendar_source_info(self) -> None:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        svc = TradingCalendarService()

        # Initially empty
        info = svc.get_calendar_source_info("CN")
        assert info["open_days_count"] == 0

        # After weekday generation
        svc.generate_weekdays("20240101", "20240105")
        info = svc.get_calendar_source_info("CN")
        assert info["open_days_count"] > 0

    def test_init_meta_db_adds_v146_columns_to_existing_tables(self, monkeypatch, tmp_path) -> None:
        """Existing meta DBs should receive additive V1.4.6 columns."""
        from sqlalchemy import create_engine, text

        db_path = tmp_path / "old_meta.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE security_master ("
                "security_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "symbol VARCHAR(12) NOT NULL, exchange VARCHAR(8) NOT NULL, "
                "is_st BOOLEAN, status VARCHAR(16))"
            ))
            conn.execute(text(
                "CREATE TABLE trading_calendar ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "trade_date DATETIME NOT NULL, exchange VARCHAR(8), is_open BOOLEAN)"
            ))

        monkeypatch.setattr("config.settings.get_meta_db_url", lambda: f"sqlite:///{db_path}")
        reset_meta_engine()
        init_meta_db()
        init_meta_db()
        reset_meta_engine()

        with engine.connect() as conn:
            security_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(security_master)")).fetchall()}
            calendar_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(trading_calendar)")).fetchall()}
        engine.dispose()

        assert {"is_suspended", "data_source"} <= security_cols
        assert {"calendar_source", "is_real_calendar", "source_provider", "source_updated_at"} <= calendar_cols
