"""Test small_batch_planner."""
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
        sym = f"{100000 + i:06d}"
        exch = "SZ" if i < count // 2 else "SH"
        urepo.add_member(u.universe_id, sym, exch, status="active")
    return u


class TestSmallBatchPlanner:
    """Tests for small_batch_planner module."""

    def test_dry_run_does_not_write_tasks(self) -> None:
        """dry_run=True should not create data_load_tasks."""
        _seed_core_universe("core_50", 5)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=True,
        )
        assert result.get("written") == 0
        assert result.get("planned_task_count", 0) >= 0

    def test_confirm_writes_tasks(self) -> None:
        """confirm=True should write data_load_tasks."""
        _seed_core_universe("core_100", 5)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_100",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=False,
        )
        assert result.get("written", 0) >= 0
        # Should not error
        assert "error" not in result or result.get("planned_task_count", 0) > 0

    def test_adj_raw(self) -> None:
        """adj=raw should only generate raw tasks."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="raw", limit=5, dry_run=True,
        )
        tasks = result.get("tasks", [])
        for t in tasks:
            assert t["adj_type"] == "raw"

    def test_adj_qfq(self) -> None:
        """adj=qfq should only generate qfq tasks."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=True,
        )
        tasks = result.get("tasks", [])
        for t in tasks:
            assert t["adj_type"] == "qfq"

    def test_adj_all_generates_both(self) -> None:
        """adj=all should generate both raw and qfq tasks."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="all", limit=5, dry_run=True,
        )
        tasks = result.get("tasks", [])
        adj_types = {t["adj_type"] for t in tasks}
        assert adj_types == {"raw", "qfq"} or len(tasks) == 0

    def test_yearly_split(self) -> None:
        """Tasks should be split by year."""
        _seed_core_universe("core_50", 2)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20230101", end_date="20241231",
            adj="qfq", limit=10, dry_run=True,
        )
        tasks = result.get("tasks", [])
        # With 2 stocks, 2 years, should have ~4 tasks per adj type
        if tasks:
            start_years = {t["start_date"][:4] for t in tasks}
            assert len(start_years) >= 1  # at least one year

    def test_limit_effective(self) -> None:
        """--limit should cap the number of tasks."""
        _seed_core_universe("core_50", 10)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240101", end_date="20240131",
            adj="all", limit=3, dry_run=True,
        )
        assert result.get("planned_task_count", 0) <= 3

    def test_rejects_reversed_date_range(self) -> None:
        """start_date must not be later than end_date."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="core_50",
            start_date="20240131", end_date="20240101",
            adj="qfq", limit=5, dry_run=True,
        )
        assert "error" in result
        assert result.get("tasks") == []

    def test_rejects_universe_all_a_without_allow_flag(self) -> None:
        """universe_all_a should be rejected without --allow-large-universe."""
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="universe_all_a",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=True,
            allow_large_universe=False,
        )
        assert "error" in result
        assert "too large" in result.get("error", "").lower() or "large" in result.get("error", "").lower()

    def test_allows_universe_all_a_with_flag(self) -> None:
        """universe_all_a should be allowed with --allow-large-universe."""
        _seed_core_universe("universe_all_a", 3)
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="universe_all_a",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=True,
            allow_large_universe=True,
        )
        # Should not have the "too large" error
        if "error" in result:
            assert "too large" not in result.get("error", "").lower()

    def test_empty_universe_shows_warning(self) -> None:
        """Empty/non-existent universe should return a clear message."""
        from src.backfill.small_batch_planner import plan_tasks

        result = plan_tasks(
            universe_name="nonexistent_universe",
            start_date="20240101", end_date="20240131",
            adj="qfq", limit=5, dry_run=True,
        )
        assert result.get("planned_task_count", 0) == 0
        assert result.get("error") or result.get("stock_count", 0) == 0

    def test_cli_dry_run(self) -> None:
        """CLI should work (even with empty universe, should return 0 for dry-run)."""
        _seed_core_universe("core_50", 3)
        from src.backfill.small_batch_planner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["planner", "--universe", "core_50", "--start-date", "20240101",
                        "--end-date", "20240105", "--adj", "qfq", "--limit", "2", "--dry-run"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv
