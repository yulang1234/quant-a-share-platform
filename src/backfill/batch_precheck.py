"""V1.4.8 Batch Precheck — validate environment before real execution.

Usage::

    python -m src.backfill.batch_precheck --batch-id <batch_id>
"""

from __future__ import annotations

import sys
from typing import Any


def run_precheck(batch_id: str) -> dict[str, Any]:
    """Run pre-execution checks for a batch. Returns dict of check results."""
    result: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_exists": False,
        "batch_status": None,
        "universe": None,
        "pending_tasks": 0,
        "failed_tasks": 0,
        "empty_tasks": 0,
        "real_calendar": False,
        "calendar_source": None,
        "duckdb_ok": False,
        "duckdb_stock_tables": False,
        "parquet_writable": True,
        "provider_available": False,
        "provider_names": [],
        "warnings": [],
        "safe_to_run": False,
    }

    # ── Batch check ────────────────────────────────────────────────────
    try:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        batch = repo.get_batch(batch_id)
        if batch is None:
            result["warnings"].append("Batch not found")
            return result

        result["batch_exists"] = True
        result["batch_status"] = batch.status
        result["universe"] = batch.universe_name

        # Task counts
        from src.data_tasks.task_repo import DataLoadTaskRepository
        trepo = DataLoadTaskRepository()
        from sqlalchemy import func
        from src.db.schema_meta import DataLoadTask
        from src.repositories.meta_db import get_session
        s = get_session()
        for st in ("pending", "failed", "empty"):
            cnt = s.query(func.count()).filter(
                DataLoadTask.batch_id == batch_id, DataLoadTask.status == st,
            ).scalar() or 0
            result[f"{st}_tasks"] = cnt
    except Exception as e:
        result["warnings"].append(f"Batch check error: {e}")
        return result

    # ── Calendar check ─────────────────────────────────────────────────
    try:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        csvc = TradingCalendarService()
        cal_info = csvc.get_calendar_source_info("CN")
        result["real_calendar"] = cal_info.get("is_real_calendar", False)
        result["calendar_source"] = cal_info.get("calendar_source", "none")
        if not result["real_calendar"]:
            result["warnings"].append("Not using real trading calendar — coverage may be inaccurate")
    except Exception as e:
        result["warnings"].append(f"Calendar check error: {e}")

    # ── DuckDB check ───────────────────────────────────────────────────
    try:
        from src.storage.duckdb_repo import query_df
        df = query_df("SELECT 1")
        result["duckdb_ok"] = not df.empty
        # Check if daily tables exist
        tables_df = query_df("SELECT table_name FROM information_schema.tables WHERE table_name IN ('stock_daily_raw', 'stock_daily_qfq')")
        result["duckdb_stock_tables"] = len(tables_df) >= 1
        if not result["duckdb_stock_tables"]:
            result["warnings"].append("DuckDB daily tables not found (save-local will create them)")
    except Exception as e:
        result["duckdb_ok"] = False
        result["warnings"].append(f"DuckDB check error: {e}")

    # ── Parquet check ──────────────────────────────────────────────────
    try:
        from pathlib import Path
        from config.settings import get_data_root
        data_root = get_data_root() if hasattr(__import__('config.settings'), 'get_data_root') else Path("data/parquet")
        p = Path(data_root)
        p.mkdir(parents=True, exist_ok=True)
        # Try writing a temp file
        test_file = p / ".precheck_test"
        test_file.touch()
        test_file.unlink()
        result["parquet_writable"] = True
    except Exception as e:
        result["parquet_writable"] = False
        result["warnings"].append(f"Parquet write check failed: {e}")

    # ── Provider check ─────────────────────────────────────────────────
    try:
        from src.data_sources.market_data_service import MarketDataService
        svc = MarketDataService()
        providers = svc.check_all_providers()
        available = [p for p in providers if p.get("status") in ("healthy", "degraded")]
        result["provider_available"] = len(available) > 0
        result["provider_names"] = [p.get("provider_name", "?") for p in available]
        if not result["provider_available"]:
            result["warnings"].append("No healthy providers available")
    except Exception as e:
        result["warnings"].append(f"Provider check error: {e}")

    # ── Safety assessment ──────────────────────────────────────────────
    checks_ok = (
        result["batch_exists"]
        and result["pending_tasks"] > 0
        and result["duckdb_ok"]
        and result["provider_available"]
    )
    result["safe_to_run"] = checks_ok

    # Add critical warning if not safe
    if not checks_ok:
        if not result["batch_exists"]:
            result["warnings"].insert(0, "CRITICAL: Batch does not exist")
        elif result["pending_tasks"] == 0:
            result["warnings"].insert(0, "No pending tasks to execute")

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.8 Batch Precheck")
    p.add_argument("--batch-id", required=True)
    args = p.parse_args()

    result = run_precheck(args.batch_id)

    print(f"\nPrecheck result:")
    print(f"  batch_exists     : {result['batch_exists']}")
    print(f"  batch_status     : {result['batch_status']}")
    print(f"  pending_tasks    : {result['pending_tasks']}")
    print(f"  failed_tasks     : {result['failed_tasks']}")
    print(f"  empty_tasks      : {result['empty_tasks']}")
    print(f"  real_calendar    : {result['real_calendar']}")
    print(f"  calendar_source  : {result['calendar_source']}")
    print(f"  duckdb_ok        : {result['duckdb_ok']}")
    print(f"  duckdb_tables    : {result['duckdb_stock_tables']}")
    print(f"  parquet_writable : {result['parquet_writable']}")
    print(f"  provider_ok      : {result['provider_available']}")
    print(f"  safe_to_run      : {result['safe_to_run']}")

    if result["warnings"]:
        print(f"\n  Warnings:")
        for w in result["warnings"]:
            print(f"    - {w}")

    if not result["safe_to_run"]:
        print(f"\n[WARN] Not safe to run. Fix issues above before executing.")
    else:
        print(f"\n[OK] Safe to run. Proceed with batch_runner.")

    return 0 if result["safe_to_run"] else 1


if __name__ == "__main__":
    sys.exit(main())
