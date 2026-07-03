#!/usr/bin/env python
"""
Quant A-Share Research Platform entry point.

Usage::

    python main.py
"""

from __future__ import annotations

from config.logging_config import setup_logging
from config.settings import APP_ENV, ensure_dirs, get_duckdb_path, get_parquet_root, get_stock_pool_path
from src.storage.duckdb_repo import close_connection, init_database, query_df

__version__ = "0.3.0"
__app_name__ = "Quant A-Share Platform"


def main() -> None:
    """Initialise the project environment and display summary information."""
    setup_logging()
    ensure_dirs()
    init_database()

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
    except Exception:
        raw_cnt = 0
        qfq_cnt = 0
        log_cnt = 0

    # Summary (ASCII-safe only)
    print()
    print("=" * 60)
    print(f"  {__app_name__}")
    print(f"  Version: v{__version__} (20yr historical data init)")
    print("=" * 60)
    print()
    print(f"  DuckDB path:      {get_duckdb_path()}")
    print(f"  Parquet root:     {get_parquet_root()}")
    print(f"  Stock pool path:  {get_stock_pool_path()}")
    print(f"  Environment:      {APP_ENV}")
    print()
    print("  Stock pool:")
    print(f"    - Total records:  {total}")
    print(f"    - Active stocks:  {active}")
    print()
    print("  Historical data:")
    print(f"    - stock_daily_raw:  {raw_cnt:,} rows")
    print(f"    - stock_daily_qfq:  {qfq_cnt:,} rows")
    print(f"    - data_update_log:  {log_cnt:,} rows")
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

    print("  V0.3 scope complete (historical data initialisation).")
    print("  Run `pytest` to verify.")
    print()

    close_connection()


if __name__ == "__main__":
    main()
