"""Test V1.4.10 quality_dashboard read-only helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'meta.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    # Keep DuckDB on a tmp path too so storage health tests don't touch real data.
    duck_path = tmp_path / "duckdb" / "test.duckdb"
    # duckdb_repo binds get_duckdb_path at import, so patch the bound name there.
    monkeypatch.setattr("config.settings.get_duckdb_path", lambda: duck_path)
    monkeypatch.setattr("src.storage.duckdb_repo.get_duckdb_path", lambda: duck_path)
    monkeypatch.setattr(
        "config.settings.get_parquet_root",
        lambda: tmp_path / "parquet",
    )
    monkeypatch.setattr(
        "src.data_quality.quality_dashboard.get_parquet_root",
        lambda: tmp_path / "parquet",
        raising=False,
    )
    reset_meta_engine()
    init_meta_db()
    # Initialise DuckDB schema in the tmp path. We must close any cached
    # connection (from earlier tests pointing at the real DB) first.
    from src.storage.duckdb_repo import close_connection, get_connection
    from src.storage.schema import CREATE_TABLE_SQL
    import os
    os.makedirs(tmp_path / "duckdb", exist_ok=True)
    close_connection()
    con = get_connection(duck_path)  # duck_path is a pathlib.Path
    for ddl in CREATE_TABLE_SQL:
        con.execute(ddl)
    close_connection()
    yield
    reset_meta_engine()
    close_connection()


# ── helpers ────────────────────────────────────────────────────────────────

def _add_universe(name: str, members=1):
    """Create a universe and return a dict with its universe_id (not an
    ORM object — those get detached after commit)."""
    from src.repositories.universe_repo import UniverseRepository
    repo = UniverseRepository()
    u = repo.add_universe(name=name)
    uid = u.universe_id
    for i in range(members):
        repo.add_member(uid, symbol=f"00000{i}", exchange="SZ")
    return uid


def _add_coverage_row(universe_id, adj_type, expected, actual, missing=None,
                      status="partial"):
    from src.data_quality.coverage_repo import CoverageReportRepository
    CoverageReportRepository().upsert(
        universe_id=universe_id, security_id=1, symbol="000001",
        exchange="SZ", asset_type="stock", data_type="daily_bar",
        adj_type=adj_type, start_date="20240101", end_date="20240131",
        expected_trade_days=expected, actual_trade_days=actual,
        missing_trade_days=missing if missing is not None else max(0, expected - actual),
        coverage_rate=(actual / expected) if expected > 0 else None,
        first_data_date="2024-01-01", last_data_date="2024-01-31",
        status=status, source="coverage_scanner", generated_at=datetime.now(),
    )


def _add_calendar(days: list, real=True, source="akshare"):
    """Persist a list of (date_str, is_open) rows into the trading calendar."""
    from src.db.schema_meta import TradingCalendar
    from src.repositories.meta_db import get_session
    s = get_session()
    for d, is_open in days:
        s.add(TradingCalendar(
            trade_date=datetime.strptime(d, "%Y-%m-%d"),
            exchange="CN", is_open=is_open,
            is_weekend=False, is_holiday=False,
            source="manual", calendar_source=source,
            is_real_calendar=real,
            source_provider=source,
            created_at=datetime.now(),
        ))
    s.commit()


# ── coverage summary ───────────────────────────────────────────────────────

class TestCoverageSummary:
    def test_empty_returns_unknown(self) -> None:
        from src.data_quality.quality_dashboard import load_coverage_summary
        rows = load_coverage_summary()
        # DEFAULT_UNIVERSES produce unknown rows
        assert rows
        assert all(r["coverage_level"] == "unknown" for r in rows)

    def test_rate_and_level(self) -> None:
        uid = _add_universe("core_50")
        _add_coverage_row(uid, "raw", expected=100, actual=98)
        _add_coverage_row(uid, "qfq", expected=100, actual=70)
        from src.data_quality.quality_dashboard import load_coverage_summary
        rows = { (r["universe_name"], r["data_type"]): r
                 for r in load_coverage_summary(universe_names=["core_50"]) }
        raw = rows[("core_50", "raw")]
        qfq = rows[("core_50", "qfq")]
        assert abs(raw["coverage_rate"] - 0.98) < 1e-6
        assert raw["coverage_level"] == "healthy"
        assert abs(qfq["coverage_rate"] - 0.70) < 1e-6
        assert qfq["coverage_level"] == "risky"

    def test_filter_by_adj_type(self) -> None:
        uid = _add_universe("core_50")
        _add_coverage_row(uid, "raw", expected=100, actual=100)
        from src.data_quality.quality_dashboard import load_coverage_summary
        rows = load_coverage_summary(universe_names=["core_50"], adj_types=["raw"])
        assert all(r["data_type"] == "raw" for r in rows)

    def test_coverage_level_thresholds(self) -> None:
        from src.data_quality.quality_dashboard import _coverage_level
        assert _coverage_level(None) == "unknown"
        assert _coverage_level(0.99) == "healthy"
        assert _coverage_level(0.85) == "usable_with_gaps"
        assert _coverage_level(0.55) == "risky"
        assert _coverage_level(0.30) == "not_recommended"


# ── calendar health ────────────────────────────────────────────────────────

class TestCalendarHealth:
    def test_empty_calendar(self) -> None:
        from src.data_quality.quality_dashboard import load_calendar_health
        h = load_calendar_health()
        assert h["total_trade_days"] == 0
        assert h["health_status"] in ("not_recommended", "risky", "unknown")

    def test_real_calendar_recent_ok(self) -> None:
        today = datetime.now().date()
        days = [(days_str(today, -i), True) for i in range(0, 8)]
        days = days[::-1]  # ascending
        _add_calendar(days, real=True, source="akshare")
        from src.data_quality.quality_dashboard import load_calendar_health
        h = load_calendar_health()
        assert h["health_status"] in ("healthy", "usable_with_gaps")
        assert h["calendar_source"] == "akshare"

    def test_generated_calendar_is_risky(self) -> None:
        today = datetime.now().date()
        days = [(days_str(today, -i), True) for i in range(0, 8)][::-1]
        _add_calendar(days, real=False, source="generated")
        from src.data_quality.quality_dashboard import load_calendar_health
        h = load_calendar_health()
        assert h["health_status"] == "risky"

    def test_missing_recent_is_risky(self) -> None:
        # All open days are 30+ days in the past → latest is stale
        today = datetime.now().date()
        days = [(days_str(today, -40), True), (days_str(today, -35), True)]
        _add_calendar(days, real=True, source="akshare")
        from src.data_quality.quality_dashboard import load_calendar_health
        h = load_calendar_health()
        assert h["health_status"] in ("risky", "usable_with_gaps")


def days_str(today: datetime, offset: int) -> str:
    return (today + timedelta(days=offset)).strftime("%Y-%m-%d")


# ── security master health ────────────────────────────────────────────────

def _add_security(symbol="000001", exchange="SZ", name="平安银行",
                  list_date=None, delist_date=None, status="active",
                  is_st=False, is_suspended=False):
    from src.repositories.security_master_repo import SecurityMasterRepository
    return SecurityMasterRepository().add_or_update(
        symbol=symbol, exchange=exchange,
        security_name=name, list_date=list_date, delist_date=delist_date,
        status=status, is_st=is_st, is_suspended=is_suspended,
        industry="银行", market_board="主板",
    )


def _add_batch(batch_id="bf_p1", universe="core_50", status="partial_success"):
    from src.backfill.batch_repo import BatchRepository
    return BatchRepository().create_batch(
        batch_id=batch_id, batch_name="T", universe_name=universe,
        adj_type="all", start_date="20240101", end_date="20240131",
        planned_task_count=10, status=status, provider_name="akshare",
    )


def _add_task_with_log(batch_id, provider, status_after, error_type=None,
                       attempt_count=1, max_attempts=5):
    """Create a task, then log its (provider_used, status_after) outcome.

    Returns the task_id. Insert directly via a fresh session and read
    task_id after flush (before commit-expire), since the repo's create()
    commit expires its returned object.
    """
    from src.db.schema_meta import DataLoadTask, DataLoadTaskLog
    from src.repositories.meta_db import get_session
    s = get_session()
    t = DataLoadTask(
        symbol="000001", exchange="SZ", data_type="daily_bar",
        adj_type="qfq", start_date="20240101", end_date="20240131",
        batch_id=batch_id, status=status_after, attempt_count=attempt_count,
        max_attempts=max_attempts, error_type=error_type,
        provider_preference=provider,
    )
    s.add(t)
    s.flush()                 # populates t.task_id without expire
    task_id = t.task_id
    s.add(DataLoadTaskLog(
        task_id=task_id, status_before="pending", status_after=status_after,
        provider_used=provider, row_count=0, duration_ms=10,
    ))
    s.commit()
    return task_id


class TestSecurityMasterHealth:
    def test_empty_is_not_recommended(self) -> None:
        from src.data_quality.quality_dashboard import load_security_master_health
        h = load_security_master_health()
        assert h["total_securities"] == 0
        assert h["health_status"] == "not_recommended"

    def test_complete_is_healthy(self) -> None:
        for i in range(5):
            _add_security(symbol=f"00000{i}", name=f"N{i}",
                          list_date=datetime(2020, 1, 1), status="active")
        from src.data_quality.quality_dashboard import load_security_master_health
        h = load_security_master_health()
        assert h["health_status"] in ("healthy", "usable_with_gaps")
        assert h["completeness_rate"] is not None and h["completeness_rate"] >= 0.95

    def test_missing_fields_is_risky(self) -> None:
        # 5 rows, but 4 with missing name and list_date
        _add_security(symbol="000010", name="A", list_date=datetime(2020, 1, 1))
        for i in range(1, 5):
            _add_security(symbol=f"00001{i}", name=None, list_date=None)
        from src.data_quality.quality_dashboard import load_security_master_health
        h = load_security_master_health()
        assert h["health_status"] in ("risky", "not_recommended")
        assert h["missing_name_count"] >= 4
        assert h["missing_list_date_count"] >= 4

    def test_st_and_suspended_counts(self) -> None:
        _add_security(symbol="000020", name="X", list_date=datetime(2020, 1, 1),
                      is_st=True, status="active")
        _add_security(symbol="000021", name="Y", list_date=datetime(2020, 1, 1),
                      is_suspended=True)
        _add_security(symbol="000022", name="Z", list_date=datetime(2020, 1, 1),
                      status="delisted", delist_date=datetime(2024, 1, 1))
        from src.data_quality.quality_dashboard import load_security_master_health
        h = load_security_master_health()
        assert h["st_count"] >= 1
        assert h["suspended_count"] >= 1
        assert h["delisted_securities"] >= 1


# ── provider health ───────────────────────────────────────────────────────


class TestProviderHealth:
    def test_no_data_returns_unknown(self) -> None:
        from src.data_quality.quality_dashboard import load_provider_health, HEALTH_UNKNOWN
        rows = load_provider_health()
        # Without batches AND without call logs → empty list
        assert rows == []

    def test_low_failure_rate_is_healthy(self) -> None:
        _add_batch(batch_id="bf_ph1")
        # 8 success + 1 failed + 1 empty for akshare
        for _ in range(8):
            _add_task_with_log("bf_ph1", "akshare", "success")
        _add_task_with_log("bf_ph1", "akshare", "failed", error_type="TimeoutError")
        _add_task_with_log("bf_ph1", "akshare", "empty")
        from src.data_quality.quality_dashboard import load_provider_health
        rows = {r["provider"]: r for r in load_provider_health()}
        ak = rows["akshare"]
        assert ak["health_status"] == "healthy"
        assert ak["failed_tasks"] == 1
        assert ak["total_tasks"] == 10

    def test_high_failure_rate_is_risky(self) -> None:
        _add_batch(batch_id="bf_ph2")
        for _ in range(2):
            _add_task_with_log("bf_ph2", "akshare", "success")
        for _ in range(8):
            _add_task_with_log("bf_ph2", "akshare", "failed", error_type="TimeoutError")
        from src.data_quality.quality_dashboard import load_provider_health
        rows = {r["provider"]: r for r in load_provider_health()}
        ak = rows["akshare"]
        assert ak["health_status"] in ("risky", "unavailable")

    def test_all_failed_is_unavailable_or_risky(self) -> None:
        _add_batch(batch_id="bf_ph3")
        for _ in range(5):
            _add_task_with_log("bf_ph3", "akshare", "failed", error_type="LookupError")
        from src.data_quality.quality_dashboard import load_provider_health
        rows = {r["provider"]: r for r in load_provider_health()}
        assert rows["akshare"]["health_status"] in ("unavailable", "risky")


# ── batch execution health ────────────────────────────────────────────────

class TestBatchExecutionHealth:
    def test_no_batches(self) -> None:
        from src.data_quality.quality_dashboard import load_batch_execution_health
        h = load_batch_execution_health()
        assert h["total_batches"] == 0

    def test_recent_success_is_healthy(self) -> None:
        _add_batch(batch_id="bf_b1", status="success")
        from src.data_quality.quality_dashboard import load_batch_execution_health
        h = load_batch_execution_health()
        assert h["health_status"] in ("healthy", "usable_with_gaps", "unknown")
        assert h["latest_batch_id"] == "bf_b1"

    def test_latest_failed_is_risky(self) -> None:
        _add_batch(batch_id="bf_bf_old", status="success")
        _add_batch(batch_id="bf_bf_new", status="failed")
        from src.data_quality.quality_dashboard import load_batch_execution_health
        h = load_batch_execution_health()
        assert h["latest_batch_status"] == "failed"
        assert h["health_status"] == "risky"


# ── storage health ────────────────────────────────────────────────────────

class TestStorageHealth:
    def test_table_empty_is_risky(self) -> None:
        from src.data_quality.quality_dashboard import load_storage_health
        rows = {r["object_name"]: r for r in load_storage_health()
                if r["storage_type"] == "duckdb"}
        # All DuckDB tables created by CREATE_TABLE_SQL exist but are empty.
        assert rows["stock_daily_raw"]["health_status"] == "risky"
        assert rows["stock_daily_qfq"]["row_count"] == 0

    def test_table_with_rows_is_healthy(self) -> None:
        from src.storage.duckdb_repo import get_connection, close_connection
        from config.settings import get_duckdb_path
        con = get_connection(get_duckdb_path())
        con.execute("INSERT INTO stock_pool (stock_code, stock_name, exchange, pool_name) "
                    "VALUES ('000001','T','SZ','core_500')")
        close_connection()
        from src.data_quality.quality_dashboard import load_storage_health
        rows = {r["object_name"]: r for r in load_storage_health()
                if r["storage_type"] == "duckdb"}
        assert rows["stock_pool"]["row_count"] == 1
        assert rows["stock_pool"]["health_status"] == "healthy"

    def test_parquet_dir_empty_is_risky(self) -> None:
        from src.data_quality.quality_dashboard import load_storage_health
        rows = {r["object_name"]: r for r in load_storage_health()
                if r["storage_type"] == "parquet"}
        # tmp dirs created by get_parquet_root may not exist
        assert "dwd/daily_raw" in rows
        assert rows["dwd/daily_raw"]["health_status"] in ("risky", "unknown")


# ── build_quality_overview ────────────────────────────────────────────────

class TestBuildQualityOverview:
    def test_all_healthy(self) -> None:
        # Setup: complete universe, real calendar, complete security master,
        # a successful batch with all-success tasks, stocked DuckDB tables.
        uid = _add_universe("core_50")
        _add_coverage_row(uid, "raw", expected=100, actual=100, status="complete")
        _add_coverage_row(uid, "qfq", expected=100, actual=100, status="complete")
        today = datetime.now().date()
        days = [(days_str(today, -i), True) for i in range(0, 8)][::-1]
        _add_calendar(days, real=True, source="akshare")
        for i in range(5):
            _add_security(symbol=f"60000{i}", name=f"M{i}",
                          list_date=datetime(2020, 1, 1))
        _add_batch(batch_id="bf_h1", status="success")
        # Stock a DuckDB table to make storage healthy
        from src.storage.duckdb_repo import get_connection, close_connection
        from config.settings import get_duckdb_path
        con = get_connection(get_duckdb_path())
        con.execute("INSERT INTO stock_pool (stock_code, stock_name, exchange, pool_name) "
                    "VALUES ('000001','T','SZ','core_500')")
        close_connection()
        from src.data_quality.quality_dashboard import build_quality_overview
        o = build_quality_overview()
        assert o["overall_status"] in ("healthy", "usable_with_gaps")

    def test_no_calendar_is_not_recommended(self) -> None:
        # No calendar rows
        _add_batch(batch_id="bf_nc", status="success")
        from src.data_quality.quality_dashboard import build_quality_overview
        o = build_quality_overview()
        assert o["overall_status"] == "not_recommended"
        assert "关键依赖" in o["status_reason"]

    def test_top_issues_and_actions_present(self) -> None:
        from src.data_quality.quality_dashboard import build_quality_overview
        o = build_quality_overview()
        assert isinstance(o["top_issues"], list)
        assert isinstance(o["suggested_next_actions"], list)
        assert len(o["suggested_next_actions"]) >= 1
        assert len(o["top_issues"]) <= 10
        assert len(o["suggested_next_actions"]) <= 5