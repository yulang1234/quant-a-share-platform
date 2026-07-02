#!/usr/bin/env python
"""
Quant A-Share Research Platform entry point.

Usage::

    python main.py
"""

from __future__ import annotations

from config.logging_config import setup_logging
from config.settings import APP_ENV, ensure_dirs, get_duckdb_path, get_parquet_root, get_stock_pool_path
from src.storage.duckdb_repo import close_connection, init_database

__version__ = "0.1.0"
__app_name__ = "A股量化研究平台 (Quant A-Share Research Platform)"


def main() -> None:
    """Initialise the project environment and display summary information."""
    setup_logging()
    ensure_dirs()
    init_database()

    print()
    print("=" * 60)
    print(f"  {__app_name__}")
    print(f"  Version: v{__version__} (项目骨架)")
    print("=" * 60)
    print()
    print(f"  DB 路径:       {get_duckdb_path()}")
    print(f"  Parquet 根目录: {get_parquet_root()}")
    print(f"  股票池路径:     {get_stock_pool_path()}")
    print(f"  运行环境:       {APP_ENV}")
    print()
    print("  [OK] 数据库初始化完成")
    print()
    print("  下一步: 进入 V0.2 股票池管理")
    print()

    close_connection()


if __name__ == "__main__":
    main()
