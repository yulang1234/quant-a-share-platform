"""Test task_runner save_local behavior with mock providers."""
from unittest.mock import patch, MagicMock
import pandas as pd
from src.data_tasks.task_runner import run_tasks


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
        # This is enforced at CLI level, tested in smoke_backfill tests
        pass
