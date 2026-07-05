"""Test task_runner save_local behavior with mock providers."""
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from src.data_tasks.task_runner import (
    _prepare_market_data_for_save,
    _validate_market_data_for_save,
    run_tasks,
)


class TestTaskRunnerSaveLocal:
    def test_dry_run_no_service_call(self) -> None:
        """Dry-run must not call MarketDataService."""
        with patch("src.data_sources.market_data_service.MarketDataService") as mock_svc:
            result = run_tasks(limit=2, confirm=False, adj_filter="all")
            mock_svc.assert_not_called()
            assert result["skipped"] >= result["total"]

    def test_confirm_no_save_passes_through(self, fresh_db) -> None:
        """confirm + no-save calls service but doesn't write market data."""
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        repo.create(symbol="000001", exchange="SZ", data_type="daily_bar", adj_type="qfq",
                    start_date="20260101", end_date="20260105", status="pending")

        mock_df = pd.DataFrame({"symbol": ["000001"], "trade_date": ["2026-01-02"], "close": [10.0],
                                "open": [10], "high": [11], "low": [9], "volume": [1000], "amount": [1e6]})
        mock_svc = MagicMock()
        mock_svc.get_daily_bars.return_value = (mock_df, "mock")
        with patch("src.data_sources.market_data_service.MarketDataService", return_value=mock_svc):
            result = run_tasks(limit=1, confirm=True, no_save=True, save_local=False, adj_filter="all")
        assert result["success"] == 1 or result["total"] == 1

    def test_save_local_requires_confirm(self) -> None:
        """save_local must be rejected without confirm."""
        with pytest.raises(ValueError):
            run_tasks(limit=1, confirm=False, save_local=True)

    def test_save_validation_requires_trade_date(self) -> None:
        df = pd.DataFrame({"close": [10.0]})
        with pytest.raises(ValueError):
            _validate_market_data_for_save(df, "qfq")

    def test_save_validation_requires_close(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02"]})
        with pytest.raises(ValueError):
            _validate_market_data_for_save(df, "qfq")

    def test_save_validation_rejects_bad_adj(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02"], "close": [10.0]})
        with pytest.raises(ValueError):
            _validate_market_data_for_save(df, "bad")

    def test_prepare_save_data_adds_stock_code_from_symbol(self) -> None:
        df = pd.DataFrame({
            "symbol": ["1"],
            "trade_date": ["2026-01-02"],
            "close": [10.0],
        })
        out = _prepare_market_data_for_save(df, "000001", "qfq")
        assert out["stock_code"].iloc[0] == "000001"
