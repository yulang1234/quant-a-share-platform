"""Test AkShareProvider wrapper — mock external calls."""
from unittest.mock import patch, MagicMock

import pandas as pd

from src.data_sources.akshare_provider import AkShareProvider
from src.data_sources.errors import ProviderError


class TestAkShareProvider:
    def test_instantiate(self) -> None:
        p = AkShareProvider()
        assert p.provider_name == "akshare"

    def test_get_daily_bars_mocked(self) -> None:
        mock_df = pd.DataFrame({
            "stock_code": ["000001"], "trade_date": ["2026-01-02"],
            "open": [10], "close": [10.5], "high": [11], "low": [9.5],
            "volume": [1000], "amount": [1e6],
        })
        with patch.object(AkShareProvider, "__init__", lambda self: setattr(self, "_client", MagicMock())):
            p = AkShareProvider()
            p._client.fetch_stock_daily = MagicMock(return_value=mock_df)
            df = p.get_daily_bars("000001", "20260101", "20260105", "raw")
            assert not df.empty
            assert "symbol" in df.columns

    def test_error_wrapped(self) -> None:
        with patch.object(AkShareProvider, "__init__", lambda self: setattr(self, "_client", MagicMock())):
            p = AkShareProvider()
            p._client.fetch_stock_daily = MagicMock(side_effect=ConnectionError("proxy"))
            try:
                p.get_daily_bars("000001", "20260101", "20260105", "raw")
            except ProviderError:
                pass  # expected
            except Exception:
                assert False, "Should raise ProviderError"
