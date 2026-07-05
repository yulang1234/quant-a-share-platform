"""V1.4.2 Sync security master from provider.

Usage::

    python -m src.security.sync_security_master --asset-type stock --provider akshare --limit 20 --dry-run
"""

from __future__ import annotations

import sys


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Sync security_master from provider")
    p.add_argument("--asset-type", default="stock")
    p.add_argument("--provider", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    args = p.parse_args()

    from src.repositories.security_master_repo import SecurityMasterRepository

    repo = SecurityMasterRepository()
    # In V1.4.2, we use existing stock_pool as seed for security_master
    from src.storage.duckdb_repo import query_df
    pool = query_df("SELECT stock_code, stock_name, exchange, sector FROM stock_pool WHERE is_active=TRUE LIMIT ?", [args.limit])

    upserted = 0
    for _, row in pool.iterrows():
        sym = str(row["stock_code"]).zfill(6)
        ex = str(row.get("exchange", "SZ")).upper()
        name = str(row.get("stock_name", ""))
        sector = str(row.get("sector", ""))

        if args.confirm:
            repo.add_or_update(sym, ex, security_name=name, asset_type=args.asset_type,
                              industry=sector if sector and sector != "nan" else None)
        upserted += 1
        print(f"  {sym}.{ex}  {name}")

    print(f"\nTotal: {upserted} securities")
    if not args.confirm:
        print("[DRY-RUN] No data written. Use --confirm to write.")
    else:
        print("[WRITTEN] Data saved to security_master.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
