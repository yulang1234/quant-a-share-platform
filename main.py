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

__version__ = "0.2.0"
__app_name__ = "A股量化研究平台 (Quant A-Share Research Platform)"


def main() -> None:
    """Initialise the project environment and display summary information."""
    setup_logging()
    ensure_dirs()
    init_database()

    # ── Stock pool status ───────────────────────────────────────────
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

    # ── Summary ─────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  {__app_name__}")
    print(f"  Version: v{__version__} (股票池管理)")
    print("=" * 60)
    print()
    print(f"  DB 路径:        {get_duckdb_path()}")
    print(f"  Parquet 根目录:  {get_parquet_root()}")
    print(f"  股票池路径:      {get_stock_pool_path()}")
    print(f"  运行环境:        {APP_ENV}")
    print()
    print(f"  股票池统计:")
    print(f"    ├─ 总记录数:   {total}")
    print(f"    └─ 活跃股票:   {active}")
    print()

    if total == 0:
        print("  [!] 股票池为空")
        print("     运行以下命令导入默认股票池:")
        print("     python -c \"from src.universe.stock_pool import load_stock_pool_from_csv, save_stock_pool_to_db;")
        print("     df = load_stock_pool_from_csv(); print(save_stock_pool_to_db(df))\"")
        print()

    print("  V0.2 scope complete (stock pool management).")
    print("  Run `pytest` to verify.")
    print()

    close_connection()


if __name__ == "__main__":
    main()
