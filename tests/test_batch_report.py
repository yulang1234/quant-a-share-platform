"""Test V1.4.7 batch_report."""
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


class TestBatchReport:
    def test_missing_batch_id(self) -> None:
        from src.backfill.batch_report import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["report", "--batch-id", "nonexistent_batch"]
            rc = cli_main()
            assert rc == 1
        finally:
            sys.argv = old_argv

    def test_empty_batch_not_crash(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_rpt", batch_name="Empty", universe_name="core_500")

        from src.backfill.batch_report import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["report", "--batch-id", "bf_test_rpt"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv

    def test_report_shows_snapshots(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_rpt2", batch_name="With Snap", universe_name="core_500")
        repo.create_snapshot(batch_id="bf_test_rpt2", snapshot_type="before",
                            avg_coverage_rate=0.5, is_real_calendar=True)
        repo.create_snapshot(batch_id="bf_test_rpt2", snapshot_type="after",
                            avg_coverage_rate=0.8, is_real_calendar=True)

        from src.backfill.batch_report import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["report", "--batch-id", "bf_test_rpt2"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv

    def test_next_suggested_action(self) -> None:
        from src.backfill.batch_report import _next_suggested_action

        # tasks_written
        action = _next_suggested_action({"status": "tasks_written", "batch_id": "bf_x"}, None, None)
        assert "batch_runner" in action

        # success
        action = _next_suggested_action({"status": "success", "success_count": 10, "failed_count": 0, "empty_count": 0}, None, None)
        assert "complete" in action.lower()

        # with failures
        action = _next_suggested_action({"status": "partial_success", "success_count": 5, "failed_count": 3, "empty_count": 0}, None, None)
        assert "retry" in action.lower() or "failed" in action.lower()
