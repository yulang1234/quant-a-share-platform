"""Test coverage scanner — SQLite fallback, no external calls."""
import pytest
from unittest.mock import patch, MagicMock
from src.data_quality.coverage_scanner import _read_local_dates


class TestReadLocalDates:
    def test_returns_set(self) -> None:
        """Should return empty set when table doesn't exist."""
        result = _read_local_dates("nonexistent_table", "000001", "20200101", "20201231")
        assert isinstance(result, set)
        assert len(result) == 0

    def test_empty_on_error(self) -> None:
        """Should not crash on any error."""
        result = _read_local_dates("stock_daily_qfq", "999999", "20200101", "20201231")
        assert isinstance(result, set)


class TestCoverageScanner:
    def test_dry_run_no_db_write(self, monkeypatch, tmp_path) -> None:
        """Dry-run should not write to DB."""
        url = f"sqlite:///{tmp_path / 'test.db'}"
        monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
        from src.db.meta_engine import reset_meta_engine
        from src.db.migrations import init_meta_db
        reset_meta_engine(); init_meta_db()

        from src.data_quality.coverage_repo import CoverageReportRepository
        repo = CoverageReportRepository()
        before = len(repo.list_all(limit=1000))

        # run with default dry-run
        from src.data_quality.coverage_scanner import main
        rc = main(["--limit", "2", "--dry-run"])
        assert rc == 0

        after = len(repo.list_all(limit=1000))
        assert after == before  # no writes

        reset_meta_engine()

    def test_limit_zero_rejected(self) -> None:
        rc = __import__('src.data_quality.coverage_scanner', fromlist=['main']).main(
            ["--limit", "0"])
        assert rc == 1

    def test_no_external_calls(self) -> None:
        """Coverage scanner must not call MarketDataService or external providers."""
        import inspect
        src = inspect.getsource(__import__('src.data_quality.coverage_scanner', fromlist=['main']))
        assert "MarketDataService" not in src
        assert "miniqmt" not in src.lower()
        assert "akshare" not in src.lower()
        assert "tushare" not in src.lower()
