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
        from src.backfill.batch_report import _suggested_retry_command
        cmd = _suggested_retry_command("bf_test", save_local=False)
        assert "retryable" in cmd or "batch_runner" in cmd
        assert "--no-save" in cmd

        cmd2 = _suggested_retry_command("bf_test", save_local=True)
        assert "--save-local" in cmd2

    def test_risk_warnings(self) -> None:
        from src.backfill.batch_report import _risk_warnings
        # High failed rate
        warns = _risk_warnings({"failed_count": 4, "success_count": 0, "empty_count": 0}, None, None)
        assert len(warns) > 0

        # All good
        warns2 = _risk_warnings({"failed_count": 0, "success_count": 10, "empty_count": 0}, None, None)
        assert len(warns2) == 0

    def test_counts_include_retryable(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_retry", batch_name="R", universe_name="core_50")
        trepo = DataLoadTaskRepository()
        trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    batch_id="bf_test_retry", status="failed",
                    attempt_count=1, max_attempts=5)
        trepo.create(symbol="000002", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    batch_id="bf_test_retry", status="failed",
                    attempt_count=5, max_attempts=5)

        from src.backfill.batch_report import _compute_counts
        counts = _compute_counts("bf_test_retry")
        assert counts["retryable"] == 1
        assert counts["non_retryable"] == 1

    def test_report_with_failed_shows_retry(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_frpt", batch_name="F", universe_name="core_50")
        trepo = DataLoadTaskRepository()
        trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    batch_id="bf_test_frpt", status="failed",
                    attempt_count=1, max_attempts=5)

        from src.backfill.batch_report import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["report", "--batch-id", "bf_test_frpt"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv
