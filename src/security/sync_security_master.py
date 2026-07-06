"""V1.4.6 Sync security master from Provider (with stock_pool fallback).

Usage::

    python -m src.security.sync_security_master --provider akshare --limit 20 --dry-run
    python -m src.security.sync_security_master --provider akshare --limit 20 --confirm
    python -m src.security.sync_security_master --dry-run
"""

from __future__ import annotations

import sys


def _infer_exchange(stock_code: str) -> str:
    """Infer exchange from stock code prefix."""
    code = str(stock_code).zfill(6)
    if code.startswith("6"):
        return "SH"
    if code.startswith(("8", "4")):
        return "BJ"
    return "SZ"


def _is_st(stock_name: str) -> bool:
    """Check if stock name indicates ST/PT."""
    import re
    return bool(re.search(r'ST|\*ST|S\*ST|PT', str(stock_name).upper()))


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.6 Sync security_master — Provider-driven with fallback",
    )
    p.add_argument("--asset-type", default="stock", help="Asset type (default: stock)")
    p.add_argument("--provider", default=None, help="Preferred provider (optional)")
    p.add_argument("--limit", type=int, default=None, help="Max securities to sync")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Preview only (default: True)")
    p.add_argument("--confirm", action="store_true", default=False,
                   help="Actually write to database")
    p.add_argument("--include-delisted", action="store_true", default=False,
                   help="Include delisted stocks")
    args = p.parse_args()

    if args.confirm:
        from src.db.migrations import init_meta_db
        init_meta_db()

    from src.repositories.security_master_repo import SecurityMasterRepository
    repo = SecurityMasterRepository()

    # ── Try Provider-driven sync ───────────────────────────────────────
    df = None
    provider_used = "stock_pool"
    is_provider = False

    if args.provider or args.confirm:
        # Only attempt provider call when explicitly requested
        try:
            from src.data_sources.market_data_service import MarketDataService
            from src.data_sources.errors import ProviderDataEmptyError
            svc = MarketDataService()
            df, provider_used = svc.get_stock_basic(provider_name=args.provider)
            is_provider = True
        except (ProviderDataEmptyError, Exception) as e:
            print(f"[WARN] Provider stock_basic unavailable: {e}")
            print("[INFO] Falling back to stock_pool (DuckDB).")
            df = None
            is_provider = False

    # ── Fallback: stock_pool ───────────────────────────────────────────
    if df is None or df.empty:
        try:
            from src.storage.duckdb_repo import query_df
            sql = "SELECT stock_code, stock_name, exchange, sector FROM stock_pool WHERE is_active=TRUE"
            if args.limit:
                sql += f" LIMIT {args.limit}"
            df = query_df(sql)
            provider_used = "stock_pool"
        except Exception:
            df = None

    if df is None or df.empty:
        print("[ERROR] No securities found from any source.")
        return 1

    if args.limit and len(df) > args.limit:
        df = df.head(args.limit)

    # ── Process rows ───────────────────────────────────────────────────
    total_rows = len(df)
    valid_rows = 0
    st_count = 0
    delisted_count = 0
    suspended_count = 0
    active_count = 0
    upserted = 0
    skipped = 0

    for _, row in df.iterrows():
        code = str(row.get("stock_code", row.get("symbol", ""))).zfill(6)
        if not code.isdigit() or len(code) != 6:
            skipped += 1
            continue

        name = str(row.get("stock_name", row.get("security_name", "")))
        exch = str(row.get("exchange", "")).upper()
        if exch not in ("SZ", "SH", "BJ"):
            exch = _infer_exchange(code)

        is_st = False
        if is_provider and "is_st" in df.columns:
            is_st = bool(row.get("is_st", False))
        else:
            is_st = _is_st(name)

        is_delisted = False
        if is_provider and "is_delisted" in df.columns:
            is_delisted = bool(row.get("is_delisted", False))
        elif "delist_date" in df.columns:
            dd = row.get("delist_date")
            is_delisted = dd is not None and str(dd) != "" and str(dd) != "nan" and str(dd) != "None"

        is_suspended = False
        if is_provider and "is_suspended" in df.columns:
            is_suspended = bool(row.get("is_suspended", False))

        status = "active"
        if is_delisted:
            status = "delisted"
            delisted_count += 1
        elif is_suspended:
            status = "suspended"
            suspended_count += 1
        else:
            active_count += 1

        if is_st:
            st_count += 1

        list_date = None
        if "list_date" in df.columns:
            ld = row.get("list_date")
            if ld is not None and str(ld) not in ("", "nan", "None"):
                list_date = str(ld)[:10]

        delist_date = None
        if "delist_date" in df.columns:
            dd = row.get("delist_date")
            if dd is not None and str(dd) not in ("", "nan", "None"):
                delist_date = str(dd)[:10]

        industry = str(row.get("industry", row.get("sector", "")))
        if industry in ("nan", "None", ""):
            industry = None

        valid_rows += 1

        if not args.include_delisted and is_delisted:
            skipped += 1
            continue

        if args.confirm:
            repo.add_or_update(
                code, exch,
                security_name=name if name and name != "nan" else None,
                asset_type=args.asset_type,
                industry=industry,
                list_date=list_date,
                delist_date=delist_date,
                is_st=is_st,
                is_suspended=is_suspended,
                status=status,
                data_source=provider_used,
            )
            upserted += 1
        else:
            upserted += 1

    # ── Output ─────────────────────────────────────────────────────────
    if not args.confirm:
        print(f"\n[DRY-RUN] Security Master Sync")
    else:
        print(f"\n[CONFIRMED] Security Master Sync")
    print(f"  provider_used   : {provider_used}")
    print(f"  total_rows      : {total_rows}")
    print(f"  valid_rows      : {valid_rows}")
    print(f"  active_count    : {active_count}")
    print(f"  st_count        : {st_count}")
    print(f"  delisted_count  : {delisted_count}")
    print(f"  suspended_count : {suspended_count}")
    print(f"  upsert_count    : {upserted}")
    print(f"  skipped_count   : {skipped}")

    # Show first 10
    print(f"  first_10_rows   :")
    for i, (_, row) in enumerate(df.head(10).iterrows()):
        code = str(row.get("stock_code", row.get("symbol", ""))).zfill(6)
        name = str(row.get("stock_name", row.get("security_name", "")))
        print(f"    {code}  {name}")
    if len(df) > 10:
        print(f"    ... and {len(df) - 10} more")

    if not args.confirm:
        print(f"\n[DRY-RUN] No data written. Use --confirm to write.")
    else:
        print(f"\n[WRITTEN] {upserted} securities saved to security_master.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
