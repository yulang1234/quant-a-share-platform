"""V1.4.5 Core Universe Builder — build core_50 / core_100 small-batch stock pools.

Usage::

    python -m src.backfill.core_universe_builder --core-size 50 --dry-run
    python -m src.backfill.core_universe_builder --core-size 50 --confirm
    python -m src.backfill.core_universe_builder --core-size 100 --dry-run
    python -m src.backfill.core_universe_builder --core-size 100 --confirm
"""

from __future__ import annotations

import sys
from typing import Any


# ── Constants ────────────────────────────────────────────────────────────────

VALID_CORE_SIZES: frozenset[int] = frozenset({50, 100, 500})

# Patterns to exclude (pessimistic matching)
_BLACKLIST_KEYWORDS: tuple[str, ...] = ("ST", "*ST", "PT", "退市", "摘牌")
_INVALID_CODE_PREFIXES: tuple[str, ...] = ("000000", "999999")


# ── Pure helpers ─────────────────────────────────────────────────────────────

def _is_valid_stock(symbol: str, exchange: str, status: str = "active",
                    security_name: str = "", is_st: bool = False) -> bool:
    """Return False for obviously bad / excluded stocks."""
    code = str(symbol).strip().zfill(6)
    exch = str(exchange).strip().upper()

    # Empty code / exchange
    if not code or code == "000000":
        return False
    if len(code) != 6 or not code.isdigit():
        return False
    if not exch or exch not in ("SZ", "SH", "BJ"):
        return False

    # Blacklist keywords in name
    name_upper = str(security_name).upper().strip()
    if any(kw in name_upper for kw in _BLACKLIST_KEYWORDS):
        return False

    # ST flag
    if is_st:
        return False

    # Delisted / inactive
    if str(status).lower() in ("delisted", "inactive", "suspended", "removed"):
        return False

    return True


def _select_core_stocks(
    candidates: list[dict[str, Any]],
    core_size: int,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select *core_size* stocks from candidates, trying to diversify by exchange.

    Returns ``(selected, skipped)``.
    """
    if core_size not in VALID_CORE_SIZES:
        raise ValueError(f"core_size must be 50, 100, or 500, got {core_size}")

    valid: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for c in candidates:
        if not _is_valid_stock(
            str(c.get("symbol", "")),
            str(c.get("exchange", "")),
            str(c.get("status", "active")),
            str(c.get("security_name", "")),
            bool(c.get("is_st", False)),
        ):
            skipped.append(c)
            continue
        valid.append(c)

    # Try to diversify: interleave SZ and SH
    sz_stocks = [s for s in valid if str(s.get("exchange", "")).upper() == "SZ"]
    sh_stocks = [s for s in valid if str(s.get("exchange", "")).upper() == "SH"]
    bj_stocks = [s for s in valid if str(s.get("exchange", "")).upper() == "BJ"]

    selected: list[dict[str, Any]] = []
    max_sz = max(len(sz_stocks), core_size)
    max_sh = max(len(sh_stocks), core_size)
    i_sz = i_sh = i_bj = 0

    while len(selected) < core_size:
        added = False
        if i_sz < len(sz_stocks):
            selected.append(sz_stocks[i_sz])
            i_sz += 1
            added = True
        if len(selected) >= core_size:
            break
        if i_sh < len(sh_stocks):
            selected.append(sh_stocks[i_sh])
            i_sh += 1
            added = True
        if len(selected) >= core_size:
            break
        if i_bj < len(bj_stocks):
            selected.append(bj_stocks[i_bj])
            i_bj += 1
            added = True
        if not added:
            break  # exhausted all candidates

    # Apply limit
    if limit is not None and limit > 0:
        selected = selected[:limit]

    return selected, skipped


# ── Data-source helpers ──────────────────────────────────────────────────────

def _get_candidates_from_security_master(limit: int | None = None) -> list[dict[str, Any]]:
    """Read candidates from security_master table."""
    try:
        from src.repositories.security_master_repo import SecurityMasterRepository
        repo = SecurityMasterRepository()
        all_secs = repo.list_all(limit=limit or 5000)
        candidates: list[dict[str, Any]] = []
        for s in all_secs:
            if getattr(s, "asset_type", "stock") != "stock":
                continue
            candidates.append({
                "symbol": str(s.symbol).zfill(6),
                "exchange": str(s.exchange).upper(),
                "security_name": getattr(s, "security_name", "") or "",
                "status": getattr(s, "status", "active") or "active",
                "is_st": bool(getattr(s, "is_st", False)),
                "source": "security_master",
            })
        return candidates
    except Exception:
        return []


def _get_candidates_from_universe(universe_name: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Read candidates from an existing universe."""
    try:
        from src.repositories.universe_repo import UniverseRepository
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uid = None
        for u in unis:
            if u.universe_name == universe_name:
                uid = u.universe_id
                break
        if uid is None:
            return []
        members = urepo.list_members(uid)
        candidates: list[dict[str, Any]] = []
        for m in members:
            candidates.append({
                "symbol": str(m.symbol).zfill(6),
                "exchange": str(m.exchange).upper(),
                "security_name": "",
                "status": getattr(m, "status", "active") or "active",
                "is_st": False,
                "source": f"universe:{universe_name}",
            })
        if limit and limit > 0:
            candidates = candidates[:limit]
        return candidates
    except Exception:
        return []


def _get_candidates_from_stock_pool(limit: int | None = None) -> list[dict[str, Any]]:
    """Read candidates from DuckDB stock_pool (fallback)."""
    try:
        from src.storage.duckdb_repo import query_df
        sql = "SELECT stock_code, exchange, stock_name, is_active FROM stock_pool"
        if limit and limit > 0:
            sql += f" LIMIT {int(limit)}"
        df = query_df(sql)
        if df.empty:
            return []
        candidates: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            candidates.append({
                "symbol": str(row.get("stock_code", "")).zfill(6),
                "exchange": str(row.get("exchange", "SZ")).upper(),
                "security_name": str(row.get("stock_name", "")),
                "status": "active" if row.get("is_active", True) else "inactive",
                "is_st": False,
                "source": "stock_pool",
            })
        return candidates
    except Exception:
        return []


# ── Core builder ─────────────────────────────────────────────────────────────

def build_core_universe(
    core_size: int = 50,
    dry_run: bool = True,
    limit: int | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """Build a core_50 or core_100 universe.

    Returns a dict with summary information suitable for both dry-run and
    confirm output.
    """
    if core_size not in VALID_CORE_SIZES:
        raise ValueError(f"core_size must be 50, 100, or 500, got {core_size}")

    universe_name = f"core_{core_size}"

    # Step 1: gather candidates
    candidates: list[dict[str, Any]] = []

    if source == "auto":
        # Priority: security_master > universe_all_a > stock_pool
        candidates = _get_candidates_from_security_master(limit=None)
        if not candidates:
            candidates = _get_candidates_from_universe("universe_all_a", limit=None)
        if not candidates:
            candidates = _get_candidates_from_stock_pool(limit=None)
    elif source == "security_master":
        candidates = _get_candidates_from_security_master(limit=None)
    elif source == "universe_all_a":
        candidates = _get_candidates_from_universe("universe_all_a", limit=None)
    elif source == "stock_pool":
        candidates = _get_candidates_from_stock_pool(limit=None)
    else:
        raise ValueError(f"Unknown source: {source}")

    if not candidates:
        return {
            "universe_name": universe_name,
            "candidates_total": 0,
            "selected_count": 0,
            "skipped_count": 0,
            "selected": [],
            "skipped": [],
            "written": False,
            "error": "No candidates found from any source.",
        }

    # Step 2: select core stocks
    selected, skipped = _select_core_stocks(candidates, core_size, limit=limit)

    result: dict[str, Any] = {
        "universe_name": universe_name,
        "candidates_total": len(candidates),
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "selected": selected,
        "skipped": skipped,
        "written": False,
    }

    # Step 3: write if confirm
    if not dry_run:
        try:
            from src.repositories.universe_repo import UniverseRepository
            urepo = UniverseRepository()
            u = urepo.add_universe(
                universe_name,
                f"Core {core_size} small-batch stock pool for backfill (V1.4.5)",
                "stock",
            )
            # Get existing members for dedup
            existing_members = urepo.list_members(u.universe_id)
            existing_symbols = {(m.symbol, m.exchange.upper()) for m in existing_members}

            new_count = 0
            updated_count = 0
            for s in selected:
                key = (str(s["symbol"]).zfill(6), str(s["exchange"]).upper())
                if key in existing_symbols:
                    updated_count += 1
                else:
                    new_count += 1
                urepo.add_member(u.universe_id, s["symbol"], s["exchange"], status="active")

            final_count = urepo.count_members(u.universe_id)
            result["written"] = True
            result["new_count"] = new_count
            result["updated_count"] = updated_count
            result["final_member_count"] = final_count
        except Exception as e:
            result["error"] = str(e)

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.5 Core Universe Builder — build core_50 / core_100 stock pools",
    )
    p.add_argument(
        "--core-size", type=int, required=True, choices=[50, 100, 500],
        help="Size of the core universe (50, 100, or 500)",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Preview only, do not write to database (default: True)",
    )
    p.add_argument(
        "--confirm", action="store_true", default=False,
        help="Actually write the universe to the database",
    )
    p.add_argument(
        "--source", default="auto",
        choices=["auto", "security_master", "universe_all_a", "stock_pool"],
        help="Candidate data source (default: auto)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Limit the number of stocks selected (for testing)",
    )
    args = p.parse_args()

    dry_run = not args.confirm

    result = build_core_universe(
        core_size=args.core_size,
        dry_run=dry_run,
        limit=args.limit,
        source=args.source,
    )

    # ── Output ──────────────────────────────────────────────────────────
    universe_name = result["universe_name"]
    selected = result.get("selected", [])
    skipped = result.get("skipped", [])

    # V1.4.7: core_500 warning
    if args.core_size == 500:
        print("[WARN] core_500 is for staged batch backfill only. It will not run full backfill automatically.")

    if dry_run:
        print(f"\n[DRY-RUN] Core Universe Builder")
        print(f"  Target universe : {universe_name}")
        print(f"  Planned stocks  : {len(selected)}")
        print(f"  First 10 stocks :")
        for s in selected[:10]:
            print(f"    {s['symbol']}.{s['exchange']}  {s.get('security_name', '')}")
        if len(selected) > 10:
            print(f"    ... and {len(selected) - 10} more")
        print(f"  Skipped stocks  : {len(skipped)}")
        if skipped:
            # Summarize skip reasons
            skip_reasons: dict[str, int] = {}
            for s in skipped:
                reason = "excluded"
                name = str(s.get("security_name", "")).upper()
                if "ST" in name:
                    reason = "ST"
                elif str(s.get("status", "")).lower() in ("delisted", "inactive"):
                    reason = s.get("status", "inactive")
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            print(f"  Skip reasons    : {dict(skip_reasons)}")
        print(f"  Will write      : No (dry-run)")
    else:
        print(f"\n[CONFIRMED] Core Universe Builder")
        print(f"  Target universe : {universe_name}")
        print(f"  Written stocks  : {len(selected)}")
        print(f"  New members     : {result.get('new_count', len(selected))}")
        print(f"  Updated members : {result.get('updated_count', 0)}")
        print(f"  Skipped         : {len(skipped)}")
        print(f"  Final members   : {result.get('final_member_count', len(selected))}")

    if result.get("error"):
        print(f"\n[ERROR] {result['error']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
