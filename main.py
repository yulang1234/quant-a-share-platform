#!/usr/bin/env python
"""
Quant A-Share Research Platform entry point.

Usage::

    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from config.logging_config import setup_logging
from config.settings import APP_ENV, ensure_dirs, get_duckdb_path, get_parquet_root, get_stock_pool_path
from src.storage.duckdb_repo import close_connection, init_database, query_df

__version__ = "1.2.0"
__app_name__ = "Quant A-Share Platform"

# ── DuckDB lock / startup-error signals ───────────────────────────────
# Substrings (lower-cased) that indicate the DB file is held by another
# process rather than a genuine corruption / schema error.  Matching any
# one of these triggers the friendly "close other processes" hint.
_DB_LOCK_SIGNALS = (
    "cannot open file",
    "another process is using this file",
    "being used by another process",
)


def handle_startup_error(error: BaseException, db_path: Path) -> int:
    """Print an actionable, ASCII-safe message for a startup failure.

    Detects the "DuckDB file locked by another process" condition (which
    happens when e.g. a Streamlit or data-update process is holding the
    ``*.duckdb`` file) and emits a short, recoverable hint rather than a
    raw traceback.  Returns a non-zero exit code in every case so the
    caller (``sys.exit``) signals failure without crashing.

    Parameters
    ----------
    error : BaseException
        The exception caught during startup.
    db_path : Path
        Path of the DuckDB file, shown to the user for diagnostics.

    Returns
    -------
    int
        Always 1 (non-zero => failure).
    """
    msg = str(error).lower()
    is_lock = any(sig in msg for sig in _DB_LOCK_SIGNALS)

    print()
    if is_lock:
        print("[ERROR] DuckDB database is currently locked by another process.")
        print("[INFO] Please close other Python, Streamlit, or data update "
              "processes and try again.")
        print("[INFO] Database file: " + str(db_path))
        print("[INFO] Do not run multiple DuckDB writers concurrently.")
    else:
        print("[ERROR] Startup failed: " + f"{type(error).__name__}: {error}")
        print("[INFO] Database file: " + str(db_path))
    print()
    return 1


def main() -> int:
    """Initialise the project environment and display summary information.

    Returns
    -------
    int
        0 on success, 1 on a startup failure (e.g. DuckDB locked).
    """
    setup_logging()
    ensure_dirs()
    db_path = get_duckdb_path()

    try:
        init_database()
    except Exception as exc:
        # Startup / DB-open failure: exit cleanly without a traceback.
        return handle_startup_error(exc, db_path)

    # Stock pool status
    try:
        count_df = query_df("SELECT COUNT(*) AS cnt FROM stock_pool")
        total = count_df.iloc[0]["cnt"] if not count_df.empty else 0
        active_df = query_df(
            "SELECT COUNT(*) AS cnt FROM stock_pool WHERE is_active = TRUE AND is_blacklisted = FALSE"
        )
        active = active_df.iloc[0]["cnt"] if not active_df.empty else 0
    except Exception:
        total = 0
        active = 0

    # Historical data status
    try:
        raw_df = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_raw")
        raw_cnt = raw_df.iloc[0]["cnt"] if not raw_df.empty else 0
        qfq_df = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_qfq")
        qfq_cnt = qfq_df.iloc[0]["cnt"] if not qfq_df.empty else 0
        log_df = query_df("SELECT COUNT(*) AS cnt FROM data_update_log")
        log_cnt = log_df.iloc[0]["cnt"] if not log_df.empty else 0
        quality_df = query_df("SELECT COUNT(*) AS cnt FROM data_quality_report")
        quality_cnt = quality_df.iloc[0]["cnt"] if not quality_df.empty else 0
    except Exception:
        raw_cnt = 0
        qfq_cnt = 0
        log_cnt = 0
        quality_cnt = 0

    # Summary (ASCII-safe only)
    print()
    print("=" * 60)
    print(f"  {__app_name__}")
    print(f"  Version: v{__version__} (V1.2 Backtest Evaluation)")
    print("=" * 60)
    print()
    print(f"  DuckDB path:      {db_path}")
    print(f"  Parquet root:     {get_parquet_root()}")
    print(f"  Stock pool path:  {get_stock_pool_path()}")
    print(f"  Environment:      {APP_ENV}")
    print()
    print("  Stock pool:")
    print(f"    - Total records:  {total}")
    print(f"    - Active stocks:  {active}")
    print()
    print("  Historical data:")
    print(f"    - stock_daily_raw:      {raw_cnt:,} rows")
    print(f"    - stock_daily_qfq:      {qfq_cnt:,} rows")
    print(f"    - data_update_log:      {log_cnt:,} rows")
    print(f"    - data_quality_report:  {quality_cnt:,} rows")
    print()

    if total == 0:
        print("  [INFO] Stock pool is empty.")
        print("         Please import core_500.csv before running historical loader.")
        print("         Option 1: streamlit run ui/streamlit_app.py -> Stock Pool -> Import")
        print(
            '         Option 2: python -c "from src.universe.stock_pool import '
            "load_stock_pool_from_csv, save_stock_pool_to_db; "
            'df = load_stock_pool_from_csv(); print(save_stock_pool_to_db(df))"'
        )
        print()

    print("  [INFO] V1.2 scope: backtest evaluation metrics.")
    print("  [INFO] Next step: run quality_report checks.")
    print()

    close_connection()
    return 0


if __name__ == "__main__":
    sys.exit(main())
