"""
Batch sector repair — fill empty ``sector`` fields in the stock pool.

Usage::

    python -m src.universe.repair_sector
    python -m src.universe.repair_sector --pool core_500 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from config.logging_config import setup_logging
from src.storage.duckdb_repo import get_connection, init_database
from src.universe.stock_pool import (
    DEFAULT_POOL,
    get_stock_pool,
    resolve_stock_sector,
)

logger = logging.getLogger(__name__)

# DuckDB lock signal substrings (lower-cased)
_LOCK_SIGNALS = (
    "cannot open file",
    "another process is using this file",
    "being used by another process",
    "io error",
)


def _is_lock_error(exc: Exception) -> bool:
    """Check whether *exc* indicates a DuckDB file-lock conflict."""
    msg = str(exc).lower()
    return any(sig in msg for sig in _LOCK_SIGNALS)


def repair_sectors(pool_name: str = DEFAULT_POOL, dry_run: bool = False) -> dict[str, int]:
    """Find stocks with missing sector and attempt to backfill.

    Only updates rows where ``sector IS NULL OR sector = '' OR sector = 'None'``.
    Already-filled sectors are never overwritten.

    Parameters
    ----------
    pool_name : str
        Pool to repair.
    dry_run : bool
        If ``True``, only report what would be changed — no writes.
        Safe even when the DB is locked by another process (read-only).

    Returns
    -------
    dict[str, int]
        ``{"total": int, "repaired": int, "skipped": int}``
    """
    try:
        con = get_connection()
    except Exception as exc:
        if _is_lock_error(exc):
            logger.warning("Database locked — cannot run repair.")
            print()
            print("[WARN] 数据库正在被 Streamlit 或其他 Python 进程占用。")
            print("[INFO] 请先关闭页面服务后再运行: python -m src.universe.repair_sector")
            print()
            return {"total": 0, "repaired": 0, "skipped": 0}
        raise

    try:
        init_database()
    except Exception as exc:
        if _is_lock_error(exc):
            logger.warning("Database locked during init — cannot run repair.")
            print()
            print("[WARN] 数据库正在被 Streamlit 或其他 Python 进程占用。")
            print("[INFO] 请先关闭页面服务后再运行: python -m src.universe.repair_sector")
            print()
            return {"total": 0, "repaired": 0, "skipped": 0}
        raise

    # Find stocks needing repair
    rows = con.execute(
        "SELECT stock_code, stock_name FROM stock_pool "
        "WHERE pool_name = ? "
        "  AND (sector IS NULL OR sector = '' OR sector = 'None')",
        [pool_name],
    ).fetchall()

    total = len(rows)
    repaired = 0
    skipped = 0

    for stock_code, stock_name in rows:
        code = str(stock_code)
        name = str(stock_name) if stock_name else ""
        logger.info("Repairing sector for %s (%s)…", code, name)

        info = resolve_stock_sector(code, name)
        sector = info["sector"]
        source = info["sector_source"]

        if sector:
            logger.info("  -> %s [%s]", sector, source)
            if not dry_run:
                try:
                    con.execute(
                        "UPDATE stock_pool SET sector = ? WHERE stock_code = ? AND pool_name = ?",
                        [sector, code, pool_name],
                    )
                except Exception as exc:
                    if _is_lock_error(exc):
                        logger.warning("Write conflict — aborting.")
                        print()
                        print("[WARN] 写入时数据库被占用，已停止。请关闭其他进程后重试。")
                        print()
                        return {"total": total, "repaired": repaired, "skipped": skipped}
                    raise
            repaired += 1
        else:
            logger.info("  -> (no sector found, skipped)")
            skipped += 1

    logger.info(
        "Repair complete: %d total, %d repaired, %d skipped.",
        total, repaired, skipped,
    )
    return {"total": total, "repaired": repaired, "skipped": skipped}


def main() -> int:
    """CLI entry point for ``python -m src.universe.repair_sector``."""
    parser = argparse.ArgumentParser(description="Batch-repair empty sectors in stock pool")
    parser.add_argument("--pool", default=DEFAULT_POOL, help="Pool name (default: core_500)")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    setup_logging()
    result = repair_sectors(pool_name=args.pool, dry_run=args.dry_run)

    print()
    print(f"Total stocks needing repair: {result['total']}")
    print(f"Repaired: {result['repaired']}")
    print(f"Skipped (no data): {result['skipped']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
