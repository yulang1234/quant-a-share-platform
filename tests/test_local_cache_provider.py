"""Test LocalCacheProvider."""
import pandas as pd
from src.data_sources.local_cache_provider import LocalCacheProvider


class TestLocalCache:
    def test_instantiate(self) -> None:
        p = LocalCacheProvider()
        assert p.provider_name == "local_cache"

    def test_health_check(self) -> None:
        p = LocalCacheProvider()
        h = p.health_check()
        assert h["status"] in ("healthy", "degraded", "down")

    def test_get_daily_bars_empty(self) -> None:
        p = LocalCacheProvider()
        df = p.get_daily_bars("999999", "20200101", "20200105", "qfq")
        assert df.empty

    def test_get_daily_bars_returns_standard_fields(self) -> None:
        p = LocalCacheProvider()
        df = p.get_daily_bars("000001", "20260101", "20260105", "qfq")
        if not df.empty:
            for col in ["symbol", "exchange", "trade_date", "close", "provider_name"]:
                assert col in df.columns
