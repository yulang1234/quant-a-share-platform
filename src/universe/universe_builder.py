"""V1.4.2 Universe builder — build universe_all_a from security_master."""

from __future__ import annotations

import sys


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Build universe_all_a from security_master")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--include-empty-status", action="store_true", default=False)
    args = p.parse_args()

    from src.repositories.universe_repo import UniverseRepository
    from src.repositories.security_master_repo import SecurityMasterRepository

    sec_repo = SecurityMasterRepository()
    uni_repo = UniverseRepository()

    # Get all stock-type securities
    all_secs = sec_repo.list_all(limit=args.limit or 5000)
    stocks = [s for s in all_secs if s.asset_type == "stock"]
    if not args.include_empty_status:
        stocks = [s for s in stocks if s.status in ("active", "listed", "normal")]

    if not stocks:
        print("[WARN] No valid stock securities found in security_master.")
        return 0

    if args.confirm:
        u = uni_repo.add_universe(
            "universe_all_a",
            "All A-share stocks from current security_master scope",
            "stock",
        )
        for sec in stocks:
            uni_repo.add_member(u.universe_id, sec.symbol, sec.exchange, status="active")
        print(f"[WRITTEN] {len(stocks)} members added to universe_all_a.")
    else:
        print(f"[DRY-RUN] Would add {len(stocks)} members to universe_all_a.")
        for sec in stocks[:10]:
            print(f"  {sec.symbol}.{sec.exchange}  {sec.security_name}")
        if len(stocks) > 10:
            print(f"  ... and {len(stocks) - 10} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
