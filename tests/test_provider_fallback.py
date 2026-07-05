"""Test provider fallback chain."""
import pandas as pd
import pytest
from src.data_sources.base import MarketDataProvider
from src.data_sources.market_data_service import MarketDataService
from src.data_sources.errors import ProviderDataEmptyError


class _StubProvider(MarketDataProvider):
    provider_name = "stub"
    def __init__(self, name, df=None, exc=None, health_status="healthy"):
        self.provider_name = name
        self._df = df if df is not None else pd.DataFrame()
        self._exc = exc; self._health = health_status
    def health_check(self): return {"provider_name": self.provider_name, "status": self._health, "latency_ms": 0, "error_message": ""}
    def get_daily_bars(self, *a, **kw):
        if self._exc: raise self._exc
        return self._df.copy() if not self._df.empty else self._df
    def get_minute_bars(self, *a, **kw): raise NotImplementedError
    def get_realtime_quote(self, *a, **kw): raise NotImplementedError
    def get_trading_calendar(self, *a, **kw): raise NotImplementedError
    def get_stock_basic(self, *a, **kw): raise NotImplementedError
    def download_history(self, *a, **kw): return self.get_daily_bars(*a, **kw)


class TestFallback:
    def test_empty_falls_to_next(self) -> None:
        df = pd.DataFrame({"symbol": ["000001"], "trade_date": ["2026-01-02"], "close": [10.0]})
        svc = MarketDataService()
        svc._providers["local_cache"] = _StubProvider("local_cache", df=pd.DataFrame())
        svc._providers["akshare"] = _StubProvider("akshare", df=df)
        _, provider = svc.get_daily_bars("000001", "20260101", "20260105", "raw")
        assert provider == "akshare"

    def test_fail_falls_to_next(self) -> None:
        df = pd.DataFrame({"symbol": ["000001"], "trade_date": ["2026-01-02"], "close": [10.0]})
        svc = MarketDataService()
        svc._providers["local_cache"] = _StubProvider("local_cache", exc=Exception("fail"))
        svc._providers["akshare"] = _StubProvider("akshare", df=df)
        _, provider = svc.get_daily_bars("000001", "20260101", "20260105", "raw")
        assert provider == "akshare"

    def test_all_fail_raises(self) -> None:
        svc = MarketDataService()
        svc._providers["local_cache"] = _StubProvider("local_cache", exc=Exception("fail"))
        svc._providers["akshare"] = _StubProvider("akshare", exc=Exception("fail2"))
        with pytest.raises(ProviderDataEmptyError):
            svc.get_daily_bars("000001", "20260101", "20260105", "raw")

    def test_disabled_skipped_then_next(self) -> None:
        df = pd.DataFrame({"symbol": ["000001"], "trade_date": ["2026-01-02"], "close": [10.0]})
        svc = MarketDataService()
        svc._providers["local_cache"] = _StubProvider("local_cache", health_status="disabled")
        svc._providers["akshare"] = _StubProvider("akshare", df=df)
        _, provider = svc.get_daily_bars("000001", "20260101", "20260105", "raw")
        assert provider == "akshare"
