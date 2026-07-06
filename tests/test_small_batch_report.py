"""Test small_batch_report."""
from __future__ import annotations

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    """Patch meta DB to use a temp SQLite file for each test."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _seed_core_universe(universe_name: str = "core_50", count: int = 10):
    """Helper: create a universe with test stocks."""
    from src.repositories.universe_repo import UniverseRepository
    urepo = UniverseRepository()
    u = urepo.add_universe(universe_name, f"Test {universe_name}", "stock")
    for i in range(count):
        sym = f"{600000 + i:06d}"
        exch = "SH"
        urepo.add_member(u.universe_id, sym, exch, status="active")
    return u


class TestSmallBatchReport:
    """Tests for small_batch_report module."""

    def test_handles_empty_data(self) -> None:
        """Empty universe / no data should not crash."""
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="nonexistent_universe",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5,
        )
        assert isinstance(report, dict)
        # Should gracefully report empty
        assert report.get("stock_count", 0) == 0

    def test_coverage_fields_present(self) -> None:
        """Report should contain all required coverage fields."""
        _seed_core_universe("core_50", 5)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5,
        )
        required_keys = [
            "universe", "adj_type", "start_date", "end_date",
            "stock_count", "complete_count", "partial_count",
            "empty_count", "calendar_missing_count",
            "avg_coverage_rate", "min_coverage_rate", "max_coverage_rate",
        ]
        for key in required_keys:
            assert key in report, f"Missing key: {key}"

    def test_top_missing_stocks_present(self) -> None:
        """Report should include top_missing_stocks list."""
        _seed_core_universe("core_50", 5)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, top_n=3,
        )
        assert "top_missing_stocks" in report
        assert isinstance(report["top_missing_stocks"], list)

    def test_adj_raw(self) -> None:
        """Should work with adj=raw."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="raw", limit=3,
        )
        assert "error" not in report or report.get("stock_count", 0) > 0

    def test_adj_qfq(self) -> None:
        """Should work with adj=qfq."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=3,
        )
        assert "error" not in report or report.get("stock_count", 0) > 0

    def test_adj_all(self) -> None:
        """Should work with adj=all."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="all", limit=3,
        )
        assert "error" not in report or report.get("stock_count", 0) > 0

    def test_provider_stats_present(self) -> None:
        """Provider stats section should be in report."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=3,
        )
        assert "provider_stats" in report
        assert isinstance(report["provider_stats"], dict)

    def test_calendar_missing_shows_warning(self) -> None:
        """When trading_calendar is empty, should be noted."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import generate_report

        report = generate_report(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=3,
        )
        # calendar_missing_count may be > 0 if no calendar data
        assert "calendar_missing_count" in report
        # calendar_available indicates if we have calendar
        assert "calendar_available" in report

    def test_cli_runs(self) -> None:
        """CLI should not error with a seeded universe."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_report import main as cli_main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["report", "--universe", "core_50", "--start-date", "20240101",
                        "--end-date", "20240105", "--adj", "qfq", "--limit", "5"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv
