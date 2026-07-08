"""Test V1.4.8 batch_precheck."""
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


class TestBatchPrecheck:
    def test_missing_batch(self) -> None:
        from src.backfill.batch_precheck import run_precheck
        result = run_precheck("nonexistent")
        assert result["batch_exists"] is False
        assert result["safe_to_run"] is False

    def test_batch_no_pending_tasks(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_pc_empty", batch_name="E", universe_name="core_50")

        from src.backfill.batch_precheck import run_precheck
        result = run_precheck("bf_pc_empty")
        assert result["batch_exists"] is True
        assert result["pending_tasks"] == 0

    def test_batch_with_pending_tasks(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_pc_pend", batch_name="P", universe_name="core_50")
        trepo = DataLoadTaskRepository()
        trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    batch_id="bf_pc_pend", status="pending")

        from src.backfill.batch_precheck import run_precheck
        result = run_precheck("bf_pc_pend")
        assert result["pending_tasks"] == 1

    def test_real_calendar_detected(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_pc_cal", batch_name="C", universe_name="core_50")

        from src.backfill.batch_precheck import run_precheck
        result = run_precheck("bf_pc_cal")
        # calendar may be false if no data
        assert "real_calendar" in result

    def test_cli_runs(self) -> None:
        from src.backfill.batch_precheck import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["precheck", "--batch-id", "nonexistent"]
            rc = cli_main()
            assert rc == 1  # not safe
        finally:
            sys.argv = old_argv
