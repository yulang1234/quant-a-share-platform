"""Test TushareProvider — no real token or API calls."""
import os
from unittest.mock import patch

import pytest

from src.data_sources.tushare_provider import TushareProvider
from src.data_sources.errors import ProviderUnavailableError


class TestTushareProvider:
    def test_instantiate(self) -> None:
        p = TushareProvider()
        assert p.provider_name == "tushare"

    def test_health_check_disabled_without_token(self, monkeypatch) -> None:
        monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
        p = TushareProvider()
        h = p.health_check()
        assert h["status"] == "disabled"

    def test_get_daily_bars_skeleton(self) -> None:
        p = TushareProvider()
        with pytest.raises(ProviderUnavailableError, match="not implemented"):
            p.get_daily_bars("000001", "20260101", "20260105", "raw")

    def test_not_trigger_real_network(self) -> None:
        """TushareProvider must not make network calls in V1.4.1."""
        p = TushareProvider()
        with pytest.raises(ProviderUnavailableError):
            p.get_minute_bars("000001", "20260101", "20260105")
        with pytest.raises(ProviderUnavailableError):
            p.get_realtime_quote("000001")
        with pytest.raises(ProviderUnavailableError):
            p.get_trading_calendar("20260101", "20260105")
        with pytest.raises(ProviderUnavailableError):
            p.get_stock_basic(["000001"])
        with pytest.raises(ProviderUnavailableError):
            p.download_history("000001", "20260101", "20260105")
