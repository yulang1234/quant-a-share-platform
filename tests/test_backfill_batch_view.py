"""Test V1.4.9 backfill_batch_view data helpers (read-only, no Streamlit)."""
from __future__ import annotations

import pandas as pd
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


def _seed(batch_id="fbv_1", universe="core_50", status="success",
          provider="akshare", created=None):
    from src.backfill.batch_repo import BatchRepository
    repo = BatchRepository()
    repo.create_batch(
        batch_id=batch_id, batch_name="T", universe_name=universe,
        adj_type="all", start_date="20240101", end_date="20240131",
        planned_task_count=10, success_count=8, failed_count=2, empty_count=0,
        status=status, provider_name=provider,
        started_at=pd.Timestamp("2024-01-01 09:00"),
        finished_at=pd.Timestamp("2024-01-01 09:01"),
    )


class TestLoadBatches:
    def test_empty_db_returns_empty_df(self) -> None:
        from ui.components.backfill_batch_view import load_batches, BATCH_COLUMNS
        df = load_batches()
        assert df.empty
        assert list(df.columns) == list(BATCH_COLUMNS)

    def test_returns_canonical_columns(self) -> None:
        _seed()
        from ui.components.backfill_batch_view import load_batches, BATCH_COLUMNS
        df = load_batches()
        assert not df.empty
        for c in BATCH_COLUMNS:
            assert c in df.columns

    def test_status_filter(self) -> None:
        _seed(batch_id="fbv_a", status="success")
        _seed(batch_id="fbv_b", status="failed")
        from ui.components.backfill_batch_view import load_batches
        df = load_batches(status="failed")
        assert (df["status"] == "failed").all()
        assert (df["batch_id"] == "fbv_b").all()

    def test_created_date_filter(self) -> None:
        _seed(batch_id="fbv_old")
        from ui.components.backfill_batch_view import load_batches
        all_df = load_batches()
        assert not all_df.empty
        # Force a far-future filter — should yield empty.
        df_future = load_batches(created_from="2099-01-01")
        assert df_future.empty


class TestLoadFailedTasks:
    def test_empty_returns_canonical_columns(self) -> None:
        from ui.components.backfill_batch_view import (
            load_failed_tasks, FAILED_TASK_COLUMNS,
        )
        df = load_failed_tasks(batch_id="nonexistent")
        assert df.empty
        assert list(df.columns) == list(FAILED_TASK_COLUMNS)

    def test_returns_failed(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        BatchRepository().create_batch(batch_id="fbv_ft", batch_name="T",
                                       universe_name="core_50")
        DataLoadTaskRepository().create(
            symbol="000001", exchange="SZ", data_type="daily_bar",
            adj_type="qfq", start_date="20240101", end_date="20240131",
            batch_id="fbv_ft", status="failed", attempt_count=1,
            max_attempts=5, error_type="TimeoutError",
            error_message="timed out", provider_preference="akshare",
        )
        from ui.components.backfill_batch_view import load_failed_tasks
        df = load_failed_tasks(batch_id="fbv_ft")
        assert not df.empty
        assert df.iloc[0]["symbol"] == "000001"
        assert bool(df.iloc[0]["retryable"]) is True
        assert df.iloc[0]["suggested_retry_command"]


class TestLoadProviderFailure:
    def test_empty_batch_ids(self) -> None:
        from ui.components.backfill_batch_view import (
            load_provider_failure, PROVIDER_COLUMNS,
        )
        df = load_provider_failure([])
        assert df.empty
        assert list(df.columns) == list(PROVIDER_COLUMNS)


class TestOverviewMetrics:
    def test_empty(self) -> None:
        from ui.components.backfill_batch_view import overview_metrics
        m = overview_metrics(pd.DataFrame())
        assert m["batch_count"] == 0
        assert m["avg_failure_rate"] is None

    def test_aggregates(self) -> None:
        df = pd.DataFrame([
            {"total_tasks": 10, "success_tasks": 8, "failed_tasks": 2,
             "empty_tasks": 0, "retryable_tasks": 1, "coverage_delta": 0.1},
            {"total_tasks": 4, "success_tasks": 2, "failed_tasks": 2,
             "empty_tasks": 0, "retryable_tasks": 1, "coverage_delta": -0.05},
        ])
        from ui.components.backfill_batch_view import overview_metrics
        m = overview_metrics(df)
        assert m["batch_count"] == 2
        assert m["total_tasks"] == 14
        assert m["failed_tasks"] == 4
        assert m["retryable_tasks"] == 2
        assert abs(m["avg_failure_rate"] - 4 / 14) < 1e-6
        assert abs(m["avg_coverage_delta"] - 0.025) < 1e-6


class TestToCsvBytes:
    def test_bom_utf8(self) -> None:
        from ui.components.backfill_batch_view import to_csv_bytes
        b = to_csv_bytes(pd.DataFrame({"a": [1], "b": ["x"]}))
        assert b.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        assert b"a,b" in b

    def test_empty_df_no_crash(self) -> None:
        from ui.components.backfill_batch_view import to_csv_bytes
        b = to_csv_bytes(pd.DataFrame())
        assert isinstance(b, bytes) and b.startswith(b"\xef\xbb\xbf")


class TestBatchSuggestedCommand:
    def test_default_dry_run(self) -> None:
        from ui.components.backfill_batch_view import batch_suggested_command
        cmd = batch_suggested_command("fbv_x")
        assert "fbv_x" in cmd
        assert "--dry-run" in cmd
        assert "--confirm" not in cmd