"""Test V1.4.7 batch_planner."""
from __future__ import annotations

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _seed_universe(name: str = "core_500", count: int = 10):
    from src.repositories.universe_repo import UniverseRepository
    urepo = UniverseRepository()
    u = urepo.add_universe(name, f"Test {name}", "stock")
    for i in range(count):
        sym = f"{600000 + i:06d}"
        urepo.add_member(u.universe_id, sym, "SH", status="active")
    return u


class TestBatchPlanner:
    def test_dry_run_does_not_write_batch(self) -> None:
        _seed_universe("core_50", 5)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_50", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=5, dry_run=True)
        assert result.get("written", 0) == 0

    def test_dry_run_does_not_write_tasks(self) -> None:
        _seed_universe("core_50", 5)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_50", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=5, dry_run=True)
        assert result.get("planned_task_count", 0) > 0
        assert result.get("written_task_count", 0) == 0

    def test_confirm_writes_batch_and_tasks(self) -> None:
        _seed_universe("core_50", 5)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_50", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=3, dry_run=False)
        assert result.get("written", 0) > 0

    def test_core_500_requires_allow_flag(self) -> None:
        _seed_universe("core_500", 10)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_500", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=5, dry_run=False,
                           allow_core_500_plan=False)
        assert "error" in result
        assert "allow-core-500-plan" in result.get("error", "").lower()

    def test_core_500_dry_run_allowed_without_flag(self) -> None:
        _seed_universe("core_500", 10)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_500", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=5, dry_run=True,
                           allow_core_500_plan=False)
        assert "error" not in result
        assert result.get("planned_task_count", 0) > 0
        assert result.get("written_task_count", 0) == 0

    def test_core_500_allowed_with_flag(self) -> None:
        _seed_universe("core_500", 10)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_500", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=3, dry_run=False,
                           allow_core_500_plan=True)
        assert "error" not in result or result.get("written", 0) > 0

    def test_universe_all_a_rejected(self) -> None:
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="universe_all_a", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=5, dry_run=True)
        assert "error" in result
        assert "universe_all_a" in result.get("error", "").lower()

    def test_limit_effective(self) -> None:
        _seed_universe("core_50", 10)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_50", start_date="20240101",
                           end_date="20240131", adj="all", limit=3, dry_run=True)
        assert result.get("planned_task_count", 0) <= 3

    def test_batch_id_generated(self) -> None:
        _seed_universe("core_50", 5)
        from src.backfill.batch_planner import plan_batch
        result = plan_batch(universe_name="core_50", start_date="20240101",
                           end_date="20240131", adj="qfq", limit=3, dry_run=True)
        bid = result.get("batch_id", "")
        assert bid.startswith("bf_")

    def test_cli_dry_run(self) -> None:
        _seed_universe("core_50", 5)
        from src.backfill.batch_planner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["planner", "--universe", "core_50", "--start-date", "20240101",
                        "--end-date", "20240105", "--adj", "qfq", "--limit", "3", "--dry-run"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv
