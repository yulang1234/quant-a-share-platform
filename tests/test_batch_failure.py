"""Test V1.4.9 batch_failure governance helpers (read-only)."""
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


# ── classify_retry_reason ───────────────────────────────────────────────────

class TestClassifyRetryReason:
    def test_timeout_is_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("TimeoutError", "request timed out")
        assert ok is True

    def test_connection_error_is_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("ConnectionError", "failed to connect")
        assert ok is True

    def test_rate_limit_is_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("RateLimitError", "rate limit exceeded")
        assert ok is True

    def test_http_5xx_is_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("HTTPError", "provider returned 503")
        assert ok is True

    def test_invalid_symbol_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("ValidationError", "invalid symbol 999999")
        assert ok is False

    def test_non_trading_day_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("CalendarError", "non trading day")
        assert ok is False

    def test_delisted_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("ProviderError", "stock delisted")
        assert ok is False

    def test_schema_error_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("SchemaError", "schema mismatch write failed")
        assert ok is False

    def test_empty_on_valid_day_is_retryable(self) -> None:
        # No permanent signal present → empty status is retryable.
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason(None, None, status="empty")
        assert ok is True

    def test_empty_with_delisted_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("Empty", "delisted stock returned no data",
                                       status="empty")
        assert ok is False

    def test_unclassified_is_non_retryable(self) -> None:
        from src.backfill.batch_failure import classify_retry_reason
        ok, _ = classify_retry_reason("SomeUnknownType", "weird thing happened")
        assert ok is False


# ── is_task_retryable (attempt_count AND category) ─────────────────────────

class TestIsTaskRetryable:
    def _task(self, **kw):
        class _T:
            pass
        t = _T()
        t.attempt_count = kw.get("attempt_count", 0)
        t.max_attempts = kw.get("max_attempts", 5)
        t.error_type = kw.get("error_type", "TimeoutError")
        t.error_message = kw.get("error_message", "timed out")
        t.status = kw.get("status", "failed")
        return t

    def test_transient_under_budget_is_retryable(self) -> None:
        from src.backfill.batch_failure import is_task_retryable
        assert is_task_retryable(self._task(attempt_count=1)) is True

    def test_transient_over_budget_is_not_retryable(self) -> None:
        from src.backfill.batch_failure import is_task_retryable
        assert is_task_retryable(self._task(attempt_count=5, max_attempts=5)) is False

    def test_permanent_under_budget_is_not_retryable(self) -> None:
        from src.backfill.batch_failure import is_task_retryable
        assert is_task_retryable(self._task(error_type="ValidationError",
                                            error_message="invalid symbol")) is False


# ── build_suggested_retry_command ────────────────────────────────────────────

class TestSuggestedCommand:
    def test_contains_batch_id(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf_test123")
        assert "bf_test123" in cmd
        assert "--batch-id" in cmd
        assert "batch_runner" in cmd

    def test_defaults_to_dry_run(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf_test123")
        assert "--dry-run" in cmd
        assert "--confirm" not in cmd

    def test_no_save_by_default(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf_test123")
        assert "--no-save" in cmd
        assert "--save-local" not in cmd

    def test_save_local_hint(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf_test123", save_local=True, dry_run=True)
        assert "--save-local" in cmd
        assert "--dry-run" in cmd
        assert "--confirm" not in cmd

    def test_includes_core_protection_flag(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf_test123")
        assert "--allow-core-500-run" in cmd

    def test_quotes_unsafe_batch_id(self) -> None:
        from src.backfill.batch_failure import build_suggested_retry_command
        cmd = build_suggested_retry_command("bf test;rm")
        assert "'bf test;rm'" in cmd
        assert "--confirm" not in cmd


# ── list_batches_with_coverage ───────────────────────────────────────────────

def _seed_batch(batch_id="bf_cov", universe="core_50", status="success"):
    from src.backfill.batch_repo import BatchRepository
    repo = BatchRepository()
    repo.create_batch(
        batch_id=batch_id, batch_name="T", universe_name=universe,
        adj_type="all", start_date="20240101", end_date="20240131",
        planned_task_count=10, success_count=8, failed_count=2, empty_count=0,
        status=status, provider_name="akshare",
        started_at=pd.Timestamp("2024-01-01 09:00"),
        finished_at=pd.Timestamp("2024-01-01 09:01"),
    )


class TestListBatchesWithCoverage:
    def test_returns_required_fields(self) -> None:
        _seed_batch()
        from src.backfill.batch_failure import list_batches_with_coverage, _BATCH_FIELDS
        rows = list_batches_with_coverage(limit=10)
        assert rows, "expected at least one batch"
        for f in _BATCH_FIELDS:
            assert f in rows[0], f"missing field {f}"

    def test_coverage_delta_computed(self) -> None:
        _seed_batch(batch_id="bf_cov2")
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_snapshot(batch_id="bf_cov2", snapshot_type="before",
                             avg_coverage_rate=0.5, is_real_calendar=True)
        repo.create_snapshot(batch_id="bf_cov2", snapshot_type="after",
                             avg_coverage_rate=0.8, is_real_calendar=True)
        from src.backfill.batch_failure import list_batches_with_coverage
        rows = [r for r in list_batches_with_coverage(limit=10)
                if r["batch_id"] == "bf_cov2"]
        assert rows
        assert rows[0]["coverage_before"] == 0.5
        assert rows[0]["coverage_after"] == 0.8
        assert abs(rows[0]["coverage_delta"] - 0.3) < 1e-6
        assert rows[0]["duration_seconds"] == 60.0

    def test_filter_by_status(self) -> None:
        _seed_batch(batch_id="bf_s1", status="success")
        _seed_batch(batch_id="bf_s2", universe="core_50", status="failed")
        from src.backfill.batch_failure import list_batches_with_coverage
        rows = list_batches_with_coverage(limit=20, status="failed")
        assert all(r["status"] == "failed" for r in rows)
        assert any(r["batch_id"] == "bf_s2" for r in rows)


# ── list_failed_tasks ─────────────────────────────────────────────────────────

def _seed_failed_task(batch_id, *, symbol="000001", exchange="SZ", status="failed",
                     error_type="TimeoutError", error_message="timed out",
                     attempt_count=1, max_attempts=5, provider_pref="akshare"):
    from src.data_tasks.task_repo import DataLoadTaskRepository
    DataLoadTaskRepository().create(
        symbol=symbol, exchange=exchange, data_type="daily_bar",
        adj_type="qfq", start_date="20240101", end_date="20240131",
        batch_id=batch_id, status=status,
        attempt_count=attempt_count, max_attempts=max_attempts,
        error_type=error_type, error_message=error_message,
        provider_preference=provider_pref,
    )


class TestListFailedTasks:
    def test_fields_complete(self) -> None:
        _seed_batch(batch_id="bf_ft1")
        _seed_failed_task("bf_ft1", error_type="TimeoutError")
        from src.backfill.batch_failure import list_failed_tasks, _FAILED_TASK_FIELDS
        rows = list_failed_tasks(batch_id="bf_ft1")
        assert rows
        for f in _FAILED_TASK_FIELDS:
            assert f in rows[0], f"missing {f}"

    def test_retryable_flag_additive(self) -> None:
        _seed_batch(batch_id="bf_ft2")
        # transient but exhausted attempts
        _seed_failed_task("bf_ft2", symbol="000001", error_type="TimeoutError",
                          attempt_count=5, max_attempts=5)
        # transient with budget
        _seed_failed_task("bf_ft2", symbol="000002", error_type="TimeoutError",
                          attempt_count=1, max_attempts=5)
        # permanent under budget
        _seed_failed_task("bf_ft2", symbol="000003", error_type="ValidationError",
                          error_message="invalid symbol", attempt_count=1)
        from src.backfill.batch_failure import list_failed_tasks
        rows = {r["symbol"]: r for r in list_failed_tasks(batch_id="bf_ft2")}
        assert rows["000001"]["retryable"] is False   # exhausted
        assert rows["000002"]["retryable"] is True    # transient under budget
        assert rows["000003"]["retryable"] is False   # permanent

    def test_empty_status_retryable(self) -> None:
        _seed_batch(batch_id="bf_ft3")
        _seed_failed_task("bf_ft3", symbol="000010", status="empty",
                          error_type=None, error_message=None)
        from src.backfill.batch_failure import list_failed_tasks
        rows = list_failed_tasks(batch_id="bf_ft3", status="empty")
        assert rows and rows[0]["retryable"] is True

    def test_empty_status_counts_as_retryable_in_batch_summary(self) -> None:
        _seed_batch(batch_id="bf_ft3b")
        _seed_failed_task("bf_ft3b", symbol="000011", status="empty",
                          error_type=None, error_message=None)
        from src.backfill.batch_failure import list_batches_with_coverage
        rows = [r for r in list_batches_with_coverage(limit=10)
                if r["batch_id"] == "bf_ft3b"]
        assert rows
        assert rows[0]["retryable_tasks"] == 1

    def test_retryable_only_filter(self) -> None:
        _seed_batch(batch_id="bf_ft4")
        _seed_failed_task("bf_ft4", symbol="000020", error_type="TimeoutError",
                          attempt_count=1)
        _seed_failed_task("bf_ft4", symbol="000021", error_type="ValidationError",
                          error_message="invalid symbol", attempt_count=1)
        from src.backfill.batch_failure import list_failed_tasks
        rows = list_failed_tasks(batch_id="bf_ft4", retryable_only=True)
        assert len(rows) == 1 and rows[0]["symbol"] == "000020"
        assert rows[0]["suggested_retry_command"]
        # non-retryable has empty suggested command (no auto-exec)
        all_rows = list_failed_tasks(batch_id="bf_ft4")
        non_retry = [r for r in all_rows if not r["retryable"]]
        assert all(r["suggested_retry_command"] == "" for r in non_retry)

    def test_ts_code_format(self) -> None:
        _seed_batch(batch_id="bf_ft5")
        _seed_failed_task("bf_ft5", symbol="600000", exchange="SH")
        from src.backfill.batch_failure import list_failed_tasks
        rows = list_failed_tasks(batch_id="bf_ft5")
        assert rows[0]["ts_code"] == "600000.SH"


# ── compute_provider_failure ─────────────────────────────────────────────────

def _seed_log(task_id, provider, status_after, row_count=0):
    from src.data_tasks.task_repo import DataLoadTaskLogRepository
    DataLoadTaskLogRepository().log(
        task_id=task_id, status_before="pending", status_after=status_after,
        provider_used=provider, row_count=row_count, duration_ms=10,
    )


class TestComputeProviderFailure:
    def test_empty_batch_ids_returns_empty_df(self) -> None:
        from src.backfill.batch_failure import compute_provider_failure
        df = compute_provider_failure([])
        assert df.empty
        assert "failure_rate" in df.columns

    def test_aggregation_correct(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_pf", batch_name="T", universe_name="core_50")
        trepo = DataLoadTaskRepository()
        t1 = trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                         adj_type="qfq", start_date="20240101", end_date="20240131",
                         batch_id="bf_pf", status="failed", attempt_count=1,
                         max_attempts=5, error_type="TimeoutError",
                         provider_preference="akshare")
        t2 = trepo.create(symbol="000002", exchange="SZ", data_type="daily_bar",
                         adj_type="qfq", start_date="20240101", end_date="20240131",
                         batch_id="bf_pf", status="success", attempt_count=0,
                         max_attempts=5, provider_preference="akshare")
        _seed_log(t1.task_id, "akshare", "failed")
        _seed_log(t2.task_id, "akshare", "success")

        from src.backfill.batch_failure import compute_provider_failure
        df = compute_provider_failure(["bf_pf"])
        assert not df.empty
        # exactly one provider bucket for bf_pf
        assert len(df) == 1
        row = df.iloc[0]
        assert row["batch_id"] == "bf_pf"
        assert row["provider"] == "akshare"
        assert row["total_tasks"] == 2
        assert row["failed_tasks"] == 1
        assert row["success_tasks"] == 1
        assert abs(row["failure_rate"] - 0.5) < 1e-6
        # retryable: t1 is transient under budget → 1
        assert row["retryable_tasks"] == 1

    def test_provider_unknown_when_missing(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_pf2", batch_name="T", universe_name="core_50")
        trepo = DataLoadTaskRepository()
        t1 = trepo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                         adj_type="qfq", start_date="20240101", end_date="20240131",
                         batch_id="bf_pf2", status="failed", attempt_count=1,
                         max_attempts=5, error_type="TimeoutError",
                         provider_preference=None)
        _seed_log(t1.task_id, None, "failed")
        from src.backfill.batch_failure import compute_provider_failure
        df = compute_provider_failure(["bf_pf2"])
        assert not df.empty
        assert df.iloc[0]["provider"] == "unknown"
