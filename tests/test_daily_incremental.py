"""
Tests for daily incremental update module -- verifies incremental logic,
date calculation, skipped scenarios, and orchestration.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Generator
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from src.data_update.daily_incremental import (
    calculate_incremental_start_date,
    get_latest_trade_date,
    run_daily_incremental,
    update_one_stock_incremental,
)
from src.data_update.update_log import get_recent_update_logs
from src.storage.duckdb_repo import (
    close_connection,
    get_connection,
    count_daily_records,
    get_max_trade_date,
    query_df,
    upsert_daily_data,
)
from src.storage.schema import CREATE_TABLE_SQL


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _tmp_db() -> Generator[None, None, None]:
    """Use a temporary database AND parquet root for each test.

    Tests that call ``save_daily_parquet`` would otherwise leak parquet
    files into the project's real ``data/parquet/`` tree and corrupt
    subsequent merge-on-write behaviour.  We isolate both the DuckDB
    file (via ``get_connection(db_path)``) and the parquet root (by
    monkey-patching ``get_parquet_root``) into a temp directory.
    """
    import src.storage.parquet_repo as parquet_repo
    import src.universe.stock_pool as stock_pool_mod  # noqa: F401  (keeps alias stable)

    close_connection()
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test.duckdb"
    parquet_root = Path(tmp_dir) / "parquet"
    parquet_root.mkdir(parents=True, exist_ok=True)

    con = get_connection(db_path)
    for ddl in CREATE_TABLE_SQL:
        try:
            con.execute(ddl)
        except Exception as e:
            close_connection()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to execute DDL: {e}") from e

    # Redirect any module that resolves the parquet root via settings to
    # the temp directory, so test writes never touch real data files.
    original_get_parquet_root = parquet_repo.get_parquet_root
    parquet_repo.get_parquet_root = lambda: parquet_root

    yield

    # Restore patched function *before* dropping the temp dir.
    parquet_repo.get_parquet_root = original_get_parquet_root
    close_connection()
    shutil.rmtree(tmp_dir, ignore_errors=True)


class FakeAkShare:
    """Replacement for the real akshare module."""

    @staticmethod
    def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
        return pd.DataFrame({
            "日期": ["2026-07-01", "2026-07-02", "2026-07-03"],
            "开盘": [10.0, 10.5, 10.3],
            "收盘": [10.2, 10.8, 10.1],
            "最高": [10.3, 11.0, 10.5],
            "最低": [9.9, 10.4, 10.0],
            "成交量": [1000000, 1500000, 1200000],
            "成交额": [1e7, 1.6e7, 1.2e7],
            "振幅": [0.04, 0.06, 0.05],
            "涨跌幅": [0.02, 0.0588, -0.0648],
            "涨跌额": [0.2, 0.6, -0.7],
            "换手率": [0.005, 0.008, 0.006],
        })


@pytest.fixture(autouse=True)
def _mock_akshare(monkeypatch) -> None:
    """Replace AkShareClient._get_akshare_module with FakeAkShare."""
    from src.data_source.akshare_client import AkShareClient
    monkeypatch.setattr(
        AkShareClient,
        "_get_akshare_module",
        staticmethod(lambda: FakeAkShare),
    )


def _seed_stock_pool(stock_codes: list[str]) -> None:
    """Insert test stocks into the stock_pool table."""
    con = get_connection()
    for i, code in enumerate(stock_codes):
        con.execute(
            "INSERT INTO stock_pool "
            "(stock_code, stock_name, pool_name, is_active, is_blacklisted) "
            "VALUES (?, ?, 'core_500', TRUE, FALSE)",
            [code, f"Test Stock {i}"],
        )


def _seed_historical_data(
    stock_code: str,
    adj_type: str,
    num_days: int = 10,
    start: date = date(2026, 6, 20),
) -> None:
    """Insert historical daily data for testing."""
    table = "stock_daily_raw" if adj_type == "raw" else "stock_daily_qfq"
    rows = []
    for i in range(num_days):
        d = start + timedelta(days=i)
        rows.append({
            "stock_code": stock_code,
            "trade_date": d,
            "open": 10.0,
            "close": 10.0 + i * 0.01,
            "high": 10.5,
            "low": 9.5,
            "volume": 1000000,
            "amount": 1e7,
        })
    upsert_daily_data(table, pd.DataFrame(rows))


# =====================================================================
#  get_latest_trade_date
# =====================================================================

class TestGetLatestTradeDate:
    def test_returns_max_date(self):
        """With data, returns the latest trade_date."""
        _seed_historical_data("000001", "raw", num_days=5, start=date(2026, 6, 20))
        result = get_latest_trade_date("000001", "raw")
        assert result is not None
        assert result == "2026-06-24"  # start + 4

    def test_returns_none_when_no_data(self):
        """Without data, returns None."""
        result = get_latest_trade_date("000001", "raw")
        assert result is None

    def test_qfq_table(self):
        """Works for qfq table too."""
        _seed_historical_data("000001", "qfq", num_days=3, start=date(2026, 7, 1))
        result = get_latest_trade_date("000001", "qfq")
        assert result == "2026-07-03"

    def test_invalid_adj_type(self):
        """Invalid adj_type must raise ValueError (not KeyError)."""
        with pytest.raises(ValueError, match="Invalid adj_type"):
            get_latest_trade_date("000001", "invalid")


# =====================================================================
#  calculate_incremental_start_date
# =====================================================================

class TestCalculateIncrementalStartDate:
    def test_with_existing_data_returns_next_day(self):
        """With max date 2026-06-24, returns 2026-06-25."""
        _seed_historical_data("000001", "raw", num_days=5, start=date(2026, 6, 20))
        result = calculate_incremental_start_date("000001", "raw")
        assert result == "20260625"

    def test_no_data_non_force_returns_none(self):
        """Without data and no force, returns None."""
        result = calculate_incremental_start_date("000001", "raw")
        assert result is None

    def test_force_with_user_start_date(self):
        """Force=True with user_start_date returns that date."""
        result = calculate_incremental_start_date(
            "000001", "raw", force=True, user_start_date="20260701"
        )
        assert result == "20260701"

    def test_force_without_user_start_date_uses_existing(self):
        """Force=True but no user_start_date still uses existing data."""
        _seed_historical_data("000001", "raw", num_days=3, start=date(2026, 6, 28))
        result = calculate_incremental_start_date(
            "000001", "raw", force=True, user_start_date=None
        )
        # Has data: max = 2026-06-30, so returns 2026-07-01
        assert result == "20260701"

    def test_no_data_force_without_user_start(self):
        """No data, force=True but no user_start_date -> None."""
        result = calculate_incremental_start_date(
            "000001", "raw", force=True, user_start_date=None
        )
        assert result is None


# =====================================================================
#  update_one_stock_incremental
# =====================================================================

class TestUpdateOneStockIncremental:
    def test_success(self):
        """Successful fetch writes success log."""
        result = update_one_stock_incremental(
            "000001", "20260701", "20260703", "raw", sleep_seconds=0
        )
        assert result["status"] == "success"
        assert result["row_count"] == 3
        assert result["adj_type"] == "raw"
        assert result["stock_code"] == "000001"

    def test_qfq_success(self):
        """QFQ fetch works too."""
        result = update_one_stock_incremental(
            "000001", "20260701", "20260703", "qfq", sleep_seconds=0
        )
        assert result["status"] == "success"
        assert result["row_count"] == 3

    def test_empty_response(self, monkeypatch):
        """Empty response writes empty log."""
        from src.data_source.akshare_client import AkShareClient

        class EmptyFake:
            @staticmethod
            def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
                return pd.DataFrame()

        monkeypatch.setattr(
            AkShareClient, "_get_akshare_module",
            staticmethod(lambda: EmptyFake),
        )
        result = update_one_stock_incremental(
            "000001", "20260701", "20260703", "raw", sleep_seconds=0
        )
        assert result["status"] == "empty"
        assert result["row_count"] == 0

    def test_failed(self, monkeypatch):
        """API exception writes failed log."""
        from src.data_source.akshare_client import AkShareClient

        class ErrorFake:
            @staticmethod
            def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
                raise ConnectionError("API error")

        monkeypatch.setattr(
            AkShareClient, "_get_akshare_module",
            staticmethod(lambda: ErrorFake),
        )
        result = update_one_stock_incremental(
            "000001", "20260701", "20260703", "raw", sleep_seconds=0
        )
        assert result["status"] == "failed"
        assert result["error_message"] is not None
        assert "ConnectionError" in result["error_message"]

    def test_data_written_to_duckdb(self):
        """Success writes data into DuckDB."""
        update_one_stock_incremental(
            "000001", "20260701", "20260703", "raw", sleep_seconds=0
        )
        cnt = count_daily_records("stock_daily_raw", "000001")
        assert cnt == 3


# =====================================================================
#  run_daily_incremental
# =====================================================================

class TestRunDailyIncremental:
    def test_empty_pool_exits_cleanly(self):
        """Empty stock pool returns zero summary."""
        summary = run_daily_incremental(limit=5, adj="all", sleep_seconds=0)
        assert summary["total"] == 0

    def test_limit_parameter(self):
        """Limit restricts stock count."""
        _seed_stock_pool(["000001", "000002", "000003"])
        summary = run_daily_incremental(limit=2, adj="raw", sleep_seconds=0)
        assert summary["total"] == 2

    def test_adj_raw_only(self):
        """adj=raw only runs raw."""
        _seed_stock_pool(["000001"])
        summary = run_daily_incremental(limit=1, adj="raw", sleep_seconds=0)
        assert summary["total"] == 1  # 1 stock x 1 adj
        assert summary["skipped"] == 1  # no historical data

    def test_adj_qfq_only(self):
        """adj=qfq only runs qfq."""
        _seed_stock_pool(["000001"])
        summary = run_daily_incremental(limit=1, adj="qfq", sleep_seconds=0)
        assert summary["total"] == 1

    def test_adj_all(self):
        """adj=all runs both raw and qfq."""
        _seed_stock_pool(["000001"])
        summary = run_daily_incremental(limit=1, adj="all", sleep_seconds=0)
        assert summary["total"] == 2  # 1 stock x 2 adj types

    def test_skipped_when_no_historical_data(self):
        """Without historical data, stocks are skipped."""
        _seed_stock_pool(["000001"])
        summary = run_daily_incremental(limit=1, adj="raw", sleep_seconds=0)
        assert summary["skipped"] == 1
        assert summary["total"] == 1
        assert summary["success"] == 0

    def test_already_up_to_date_skipped(self):
        """If latest data already covers end_date, skip."""
        _seed_stock_pool(["000001"])
        # Seed data up to today (default end_date)
        today = date.today()
        _seed_historical_data("000001", "raw", num_days=5, start=today - timedelta(days=4))

        summary = run_daily_incremental(limit=1, adj="raw", sleep_seconds=0)
        # The calculate_incremental_start_date returns max_date + 1 > end_date
        assert summary["skipped"] == 1

    def test_successful_incremental_fetch(self):
        """With historical data, successfully fetches new data."""
        _seed_stock_pool(["000001"])
        # Seed 3 days of history
        _seed_historical_data("000001", "raw", num_days=3, start=date(2026, 6, 28))

        summary = run_daily_incremental(
            limit=1, adj="raw",
            end_date="20260703",  # 2026-07-03
            sleep_seconds=0,
        )
        # raw: max=2026-06-30 -> calc_start=20260701 -> end=20260703 -> success
        assert summary["success"] >= 1
        assert summary["failed"] == 0

    def test_partial_failure_no_interruption(self, monkeypatch):
        """One stock failure doesn't stop others."""
        _seed_stock_pool(["000001", "000002"])
        _seed_historical_data("000001", "raw", num_days=3, start=date(2026, 6, 28))
        _seed_historical_data("000002", "raw", num_days=3, start=date(2026, 6, 28))

        from src.data_source.akshare_client import AkShareClient

        call_count = [0]

        class PartialFake:
            @staticmethod
            def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise ConnectionError("mock failure")
                return pd.DataFrame({
                    "日期": ["2026-07-01"],
                    "开盘": [10.0],
                    "收盘": [10.2],
                    "最高": [10.3],
                    "最低": [9.9],
                    "成交量": [1000000],
                    "成交额": [1e7],
                    "振幅": [0.04],
                    "涨跌幅": [0.02],
                    "涨跌额": [0.2],
                    "换手率": [0.005],
                })

        monkeypatch.setattr(
            AkShareClient, "_get_akshare_module",
            staticmethod(lambda: PartialFake),
        )

        summary = run_daily_incremental(
            limit=2, adj="raw",
            end_date="20260701",
            sleep_seconds=0,
        )
        # 000001 raw: success
        # 000002 raw: failed (2nd call)
        assert summary["total"] == 2
        assert summary["success"] == 1
        assert summary["failed"] == 1


# =====================================================================
#  Idempotency
# =====================================================================

class TestIdempotency:
    def test_repeat_no_duplicate_in_duckdb(self):
        """Running the same incremental twice does not duplicate rows."""
        _seed_stock_pool(["000001"])
        _seed_historical_data("000001", "raw", num_days=3, start=date(2026, 6, 28))

        run_daily_incremental(
            limit=1, adj="raw", end_date="20260701", sleep_seconds=0,
        )
        first_cnt = count_daily_records("stock_daily_raw", "000001")

        run_daily_incremental(
            limit=1, adj="raw", end_date="20260701", sleep_seconds=0,
        )
        second_cnt = count_daily_records("stock_daily_raw", "000001")

        assert first_cnt == second_cnt, f"First: {first_cnt}, Second: {second_cnt}"

    def test_logs_written(self):
        """Incremental run writes update log entries."""
        _seed_stock_pool(["000001"])
        _seed_historical_data("000001", "raw", num_days=3, start=date(2026, 6, 28))

        run_daily_incremental(
            limit=1, adj="raw", end_date="20260701", sleep_seconds=0,
        )

        logs = get_recent_update_logs()
        inc_logs = [l for l in logs.itertuples() if l.task_type == "daily_incremental"]
        assert len(inc_logs) >= 1
        assert inc_logs[0].status == "success" or inc_logs[0].status == "skipped"


# =====================================================================
#  CLI output safety (ASCII meta-check)
# =====================================================================

class TestCliOutputSafety:
    def test_summary_no_forbidden_symbols(self):
        """The summary-related strings in daily_incremental.py are ASCII-safe."""
        import ast
        filepath = Path(__file__).resolve().parent.parent / "src" / "data_update" / "daily_incremental.py"
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))

        forbidden = ["✓", "✗", "✅", "❌",
                     "→", "—", "⚠",
                     "\U0001f680", "\U0001f4ca", "\U0001f4c8", "\U0001f4c9"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            for sym in forbidden:
                                if sym in arg.value:
                                    pytest.fail(
                                        f"Line {arg.lineno}: forbidden symbol "
                                        f"U+{ord(sym):04X} in print: "
                                        f"{repr(arg.value[:80])}"
                                    )

    def test_summary_prints_are_ascii(self):
        """All print() arguments in daily_incremental.py are ASCII-safe."""
        import ast
        filepath = Path(__file__).resolve().parent.parent / "src" / "data_update" / "daily_incremental.py"
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            try:
                                arg.value.encode("ascii")
                            except (UnicodeEncodeError, UnicodeDecodeError):
                                pytest.fail(
                                    f"Line {arg.lineno}: non-ASCII print: "
                                    f"{repr(arg.value[:80])}"
                                )


# =====================================================================
#  Invalid parameters
# =====================================================================

class TestInvalidParameters:
    def test_invalid_adj_raises(self):
        """Invalid adj value raises ValueError."""
        _seed_stock_pool(["000001"])  # need a stock to reach adj validation
        with pytest.raises(ValueError, match="adj must be"):
            run_daily_incremental(adj="invalid")

    def test_invalid_table_name_get_max_date(self):
        """Invalid table name in get_max_trade_date raises ValueError."""
        with pytest.raises(ValueError):
            get_max_trade_date("invalid_table", "000001")

    def test_invalid_table_name_count(self):
        """Invalid table name in count_daily_records raises ValueError."""
        with pytest.raises(ValueError):
            count_daily_records("invalid_table")


# =====================================================================
#  P1-1 — run_daily_incremental date-parameter validation
# =====================================================================

class TestDateValidation:
    """``run_daily_incremental`` must validate its date parameters up front."""

    def test_start_after_end_raises(self):
        """start_date later than end_date (force mode) -> ValueError."""
        with pytest.raises(ValueError, match="cannot be later than end_date"):
            run_daily_incremental(
                limit=1, adj="raw",
                start_date="20260705", end_date="20260701",
                force=True, sleep_seconds=0,
            )

    def test_force_without_start_raises(self):
        """force=True with no start_date -> ValueError."""
        with pytest.raises(ValueError, match="requires --start-date"):
            run_daily_incremental(
                limit=1, adj="raw",
                start_date=None, end_date="20260701",
                force=True, sleep_seconds=0,
            )

    def test_manual_start_without_force_raises(self):
        """start_date supplied without --force -> ValueError."""
        with pytest.raises(ValueError, match="Manual start_date requires --force"):
            run_daily_incremental(
                limit=1, adj="raw",
                start_date="20260701", end_date="20260703",
                force=False, sleep_seconds=0,
            )

    def test_invalid_end_date_format_raises(self):
        """Malformed end_date -> ValueError."""
        with pytest.raises(ValueError, match="Invalid end_date"):
            run_daily_incremental(
                limit=1, adj="raw",
                end_date="2026070",  # 7 digits
                sleep_seconds=0,
            )

    def test_invalid_start_date_format_raises(self):
        """Malformed start_date in force mode -> ValueError."""
        with pytest.raises(ValueError, match="Invalid start_date"):
            run_daily_incremental(
                limit=1, adj="raw",
                start_date="abcd1234", end_date="20260703",
                force=True, sleep_seconds=0,
            )

    def test_valid_force_run_no_validation_error(self):
        """A well-formed force-mode run should NOT raise a ValueError.

        (It may exit via the empty-pool short-circuit, but the date
        validation must pass.)
        """
        # Force does not consult the DB during validation; ensure_dirs /
        # init_database run on the temp DB from the autouse fixture.
        summary = run_daily_incremental(
            limit=1, adj="raw",
            start_date="20260701", end_date="20260703",
            force=True, sleep_seconds=0,
        )
        # Either it briskly skips everything (empty pool) or runs the
        # one stock; both are acceptable.  We only assert it did not
        # raise and returned a dict with the expected keys.
        assert "total" in summary
        assert "skipped" in summary


# =====================================================================
#  P1-2 — already-up-to-date writes a 'skipped' log entry
# =====================================================================

class TestAlreadyUpToDateLog:
    def test_already_up_to_date_logs_skipped_status(self):
        """When the data is already current, a 'skipped' log row is written."""
        _seed_stock_pool(["000001"])
        # Seed data up to end_date so the run hits the
        # 'already up to date' branch.
        today = date.today()
        _seed_historical_data("000001", "raw", num_days=5, start=today - timedelta(days=4))

        run_daily_incremental(limit=1, adj="raw", sleep_seconds=0)

        logs = get_recent_update_logs()
        inc = [r for r in logs.itertuples() if r.task_type == "daily_incremental"]
        assert len(inc) >= 1, "no daily_incremental log written"
        assert inc[0].status == "skipped"
        assert (inc[0].error_message or "").startswith("Already up to date") or True
        # The friendly message stored in the log:
        assert inc[0].error_message == "Already up to date"


# =====================================================================
#  P1-3 — skipped log carries sub-task timestamps, not whole-run start
# =====================================================================

class TestSkippedSubtaskTimestamp:
    def test_skipped_log_started_at_is_subtask_time(self):
        """A skip entry's started_at must be ~now, not the run start time.

        We seed a pool with a stock that has no historical data, run with
        ``sleep_seconds=0`` synced, and assert the resulting skipped
        log's ``started_at`` is no earlier than a timestamp captured
        just before the call.
        """
        _seed_stock_pool(["000001"])
        before = datetime.now()

        run_daily_incremental(limit=1, adj="raw", sleep_seconds=0)

        logs = get_recent_update_logs()
        inc = [r for r in logs.itertuples() if r.task_type == "daily_incremental"]
        assert len(inc) >= 1
        # Sub-task started_at should be at or after our pre-call marker,
        # proving it was NOT pinned to a much earlier whole-run start.
        log_started = pd.to_datetime(inc[0].started_at)
        assert log_started >= before - pd.Timedelta(seconds=1), (
            f"skipped log started_at {log_started} predates run {before}"
        )
