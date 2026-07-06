"""Test V1.4.7 batch_runner."""
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


class TestBatchRunner:
    def test_cli_requires_batch_id(self) -> None:
        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--limit", "5", "--dry-run"]
            # Should fail because --batch-id is required
            with pytest.raises(SystemExit):
                cli_main()
        finally:
            sys.argv = old_argv

    def test_dry_run_not_execute(self) -> None:
        """Dry-run should not execute tasks."""
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_run1", batch_name="T", universe_name="core_50")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_test_run1", "--limit", "3", "--dry-run"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv

    def test_save_local_requires_confirm(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_run2", batch_name="T", universe_name="core_50")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_test_run2", "--limit", "3", "--save-local"]
            rc = cli_main()
            assert rc == 1
        finally:
            sys.argv = old_argv

    def test_limit_enforced(self) -> None:
        """Limit should be enforced."""
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_run3", batch_name="T", universe_name="core_50")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            # limit 100 > max 50 should error
            sys.argv = ["runner", "--batch-id", "bf_test_run3", "--limit", "100", "--dry-run"]
            rc = cli_main()
            assert rc == 1
        finally:
            sys.argv = old_argv

    def test_only_executes_batch_tasks(self) -> None:
        """Should only list tasks for the specified batch_id."""
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository

        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_run4", batch_name="T", universe_name="core_50")

        trepo = DataLoadTaskRepository()
        # Task with batch_id
        trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    batch_id="bf_test_run4", status="pending")
        # Task without batch_id
        trepo.create(symbol="000002", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    status="pending")

        tasks = trepo.list_pending(limit=10, batch_id="bf_test_run4")
        assert len(tasks) == 1
        assert tasks[0].batch_id == "bf_test_run4"
