"""Test MiniQMTProvider — no real xtquant required."""
import pytest
from unittest.mock import patch, MagicMock

import pandas as pd

from src.data_sources.miniqmt_provider import MiniQMTProvider, _try_import_xtdata
from src.data_sources.errors import ProviderUnavailableError


class TestMiniQMTProvider:
    def test_instantiate_without_xtquant(self) -> None:
        with patch("src.data_sources.miniqmt_provider._try_import_xtdata", return_value=None):
            p = MiniQMTProvider()
            assert p.provider_name == "miniqmt"

    def test_health_check_disabled_without_xtquant(self) -> None:
        with patch("src.data_sources.miniqmt_provider._try_import_xtdata", return_value=None):
            p = MiniQMTProvider()
            h = p.health_check()
            assert h["status"] in ("disabled", "down")

    def test_get_daily_bars_raises_without_xtquant(self) -> None:
        with patch("src.data_sources.miniqmt_provider._try_import_xtdata", return_value=None):
            p = MiniQMTProvider()
            with pytest.raises(ProviderUnavailableError):
                p.get_daily_bars("000001.SZ", "20240101", "20240105", "raw")

    def test_does_not_import_xttrader(self) -> None:
        """Verify xttrader is never imported in miniqmt_provider."""
        with open("src/data_sources/miniqmt_provider.py", "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "xttrader" not in stripped, f"xttrader found in: {stripped}"
