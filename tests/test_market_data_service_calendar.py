"""Test V1.4.6 MarketDataService trading calendar and stock_basic."""
from __future__ import annotations

import pandas as pd
import pytest

from src.data_sources.base import MarketDataProvider
from src.data_sources.market_data_service import MarketDataService
from src.data_sources.errors import ProviderDataEmptyError
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


class _StubCalendar(MarketDataProvider):
    provider_name = "stub_cal"
    def __init__(self, name, df=None, exc=None, health_status="healthy"):
        self.provider_name = name; self._df = df if df is not None else pd.DataFrame(); self._exc = exc; self._health = health_status
    def health_check(self): return {"provider_name": self.provider_name, "status": self._health, "latency_ms": 0, "error_message": ""}
    def get_daily_bars(self, *a, **kw):
        if self._exc: raise self._exc
        return self._df.copy() if not self._df.empty else self._df
    def get_trading_calendar(self, start, end):
        if self._exc: raise self._exc
        return self._df.copy() if not self._df.empty else self._df
    def get_stock_basic(self, codes=None):
        if self._exc: raise self._exc
        return self._df.copy() if not self._df.empty else self._df
    def get_minute_bars(self, *a, **kw): raise NotImplementedError
    def get_realtime_quote(self, *a, **kw): raise NotImplementedError
    def download_history(self, *a, **kw): return self.get_daily_bars(*a, **kw)


class TestMarketDataServiceCalendar:
    def test_provider_fallback_order(self) -> None:
        import datetime
        df = pd.DataFrame({
            "trade_date": [datetime.datetime(2024, 1, 2)],
            "is_open": [True],
            "exchange": ["CN"],
            "provider_name": ["stub"],
        })
        p = _StubCalendar("stub_cal", df=df)
        svc = MarketDataService()
        # Replace all providers to avoid real providers returning data
        for key in list(svc._providers.keys()):
            svc._providers[key] = _StubCalendar(key, exc=Exception("disabled for test"))
        svc._providers["stub_cal"] = p
        result, prov = svc.get_trading_calendar("20240101", "20240105", provider_name="stub_cal")
        assert prov == "stub_cal"
        assert not result.empty

    def test_disabled_provider_skipped(self) -> None:
        import datetime
        df = pd.DataFrame({
            "trade_date": [datetime.datetime(2024, 1, 2)],
            "is_open": [True],
            "exchange": ["CN"],
            "provider_name": ["stub"],
        })
        p1 = _StubCalendar("local_cache", health_status="disabled")
        p2 = _StubCalendar("akshare", df=df)
        svc = MarketDataService()
        svc._providers["local_cache"] = p1
        svc._providers["akshare"] = p2
        result, prov = svc.get_trading_calendar("20240101", "20240105", "CN")
        assert prov == "akshare"

    def test_all_fail_raises(self) -> None:
        p = _StubCalendar("local_cache", exc=Exception("fail"))
        svc = MarketDataService()
        # Replace all providers with failing stubs
        for key in list(svc._providers.keys()):
            svc._providers[key] = _StubCalendar(key, exc=Exception("fail"))
        with pytest.raises(ProviderDataEmptyError):
            svc.get_trading_calendar("20240101", "20240105", "CN")

    def test_stock_basic_provider_fallback(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001"], "stock_name": ["Test"], "exchange": ["SZ"],
            "is_st": [False], "is_delisted": [False],
        })
        p = _StubCalendar("stub_basic", df=df)
        svc = MarketDataService()
        for key in list(svc._providers.keys()):
            svc._providers[key] = _StubCalendar(key, exc=Exception("disabled for test"))
        svc._providers["stub_basic"] = p
        result, prov = svc.get_stock_basic(provider_name="stub_basic")
        assert prov == "stub_basic"
        assert not result.empty

    def test_success_returns_df_and_provider_name(self) -> None:
        import datetime
        df = pd.DataFrame({
            "trade_date": [datetime.datetime(2024, 1, 2)],
            "is_open": [True],
            "exchange": ["CN"],
            "provider_name": ["stub"],
        })
        p = _StubCalendar("stub_cal2", df=df)
        svc = MarketDataService()
        for key in list(svc._providers.keys()):
            svc._providers[key] = _StubCalendar(key, exc=Exception("disabled for test"))
        svc._providers["stub_cal2"] = p
        result, prov = svc.get_trading_calendar("20240101", "20240105", provider_name="stub_cal2")
        assert isinstance(result, pd.DataFrame)
        assert isinstance(prov, str)
        assert prov == "stub_cal2"
