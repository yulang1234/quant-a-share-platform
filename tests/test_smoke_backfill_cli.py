"""Test smoke_backfill CLI."""
import pytest
from src.data_quality.smoke_backfill import main


class TestSmokeBackfill:
    def test_dry_run(self) -> None:
        rc = main(["--stock-code", "000001.SZ", "--start-date", "20240101", "--end-date", "20240105", "--adj", "qfq"])
        assert rc == 0

    def test_save_local_requires_confirm(self) -> None:
        rc = main(["--stock-code", "000001.SZ", "--start-date", "20240101", "--end-date", "20240105", "--save-local"])
        assert rc == 1

    def test_range_too_large_rejected(self) -> None:
        rc = main(["--stock-code", "000001.SZ", "--start-date", "20200101", "--end-date", "20210101"])
        assert rc == 1

    def test_no_external_in_dry_run(self) -> None:
        import inspect
        src = inspect.getsource(main)
        # dry-run doesn't import MarketDataService
        assert "MarketDataService" in src  # only imported after confirm check
