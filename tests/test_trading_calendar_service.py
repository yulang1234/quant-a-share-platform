"""Test trading calendar service."""
import pytest
from datetime import datetime
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.trading_calendar.trading_calendar_service import TradingCalendarService


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestCalendar:
    def test_upsert_trading_day(self) -> None:
        svc = TradingCalendarService()
        svc.upsert_trading_day("2026-01-02", "CN", is_open=True)
        dates = svc.list_open_dates("2026-01-01", "2026-01-05")
        assert len(dates) >= 1

    def test_generate_weekdays(self) -> None:
        svc = TradingCalendarService()
        svc.generate_weekdays("20260701", "20260707", "CN")
        dates = svc.list_open_dates("2026-07-01", "2026-07-05")
        assert len(dates) > 0  # weekdays

    def test_no_duplicate_on_reinsert(self) -> None:
        svc = TradingCalendarService()
        svc.upsert_trading_day("2026-01-02")
        svc.upsert_trading_day("2026-01-02")  # no error
        dates = svc.list_open_dates("2026-01-01", "2026-01-05")
        assert len(dates) == 1  # one unique date

    def test_adjacent_dates(self) -> None:
        svc = TradingCalendarService()
        svc.generate_weekdays("20260701", "20260710", "CN")
        dates = svc.list_open_dates("2026-07-01", "2026-07-10")
        for i in range(1, len(dates) - 1):
            assert dates[i].pre_trade_date is not None
            assert dates[i].next_trade_date is not None
