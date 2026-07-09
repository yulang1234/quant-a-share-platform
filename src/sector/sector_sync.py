"""V1.5.3 sector sync — fetch sector data from AkShare and persist to DuckDB.

Uses AkShare's East-Money sector APIs:
- ``ak.stock_board_industry_name_em()``  → industry board list
- ``ak.stock_board_concept_name_em()``   → concept board list
- ``ak.stock_board_industry_cons_em()``  → industry board constituents
- ``ak.stock_board_concept_cons_em()``   → concept board constituents

Supports:
- ``--dry-run`` / ``--confirm`` protection
- ``--source`` to tag data origin
- Graceful degradation when AkShare is unavailable

Usage (CLI)::

    python -m src.sector.sector_sync --sync-basic --source akshare --dry-run
    python -m src.sector.sector_sync --sync-basic --source akshare --confirm
    python -m src.sector.sector_sync --sync-map --source akshare --dry-run
    python -m src.sector.sector_sync --sync-map --source akshare --confirm
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from src.sector.sector_types import (
    SECTOR_INDUSTRY, SECTOR_CONCEPT, SOURCE_AKSHARE,
)

logger = logging.getLogger(__name__)

VERSION = "v1.5.3"

# ── AkShare sync ────────────────────────────────────────────────────────────


def _fetch_sector_list_akshare(sector_type: str) -> pd.DataFrame | None:
    """Fetch sector list from AkShare.

    Args:
        sector_type: 'industry' or 'concept'

    Returns:
        DataFrame with columns [sector_code, sector_name] or None on failure.
    """
    try:
        import akshare as ak

        if sector_type == SECTOR_INDUSTRY:
            df = ak.stock_board_industry_name_em()
        elif sector_type == SECTOR_CONCEPT:
            df = ak.stock_board_concept_name_em()
        else:
            logger.warning("Unknown sector_type: %s", sector_type)
            return None

        if df is None or df.empty:
            logger.warning("AkShare returned empty data for sector_type=%s", sector_type)
            return None

        # Normalise columns (EM APIs use different column names)
        result = pd.DataFrame()
        if "板块名称" in df.columns:
            result["sector_name"] = df["板块名称"].astype(str)
        elif "name" in df.columns:
            result["sector_name"] = df["name"].astype(str)
        else:
            logger.warning("Cannot find sector name column for sector_type=%s", sector_type)
            return None

        if "板块代码" in df.columns:
            result["sector_code"] = df["板块代码"].astype(str)
        elif "code" in df.columns:
            result["sector_code"] = df["code"].astype(str)
        else:
            # Generate codes from names if not available
            result["sector_code"] = result["sector_name"].apply(
                lambda x: f"SEC_{hash(x) & 0xFFFFFF:06X}"
            )

        result["sector_type"] = sector_type
        return result
    except ImportError:
        logger.warning("akshare not installed — cannot fetch sector list")
        return None
    except Exception as exc:
        logger.warning("AkShare sector list fetch failed: %s", exc)
        return None


def _fetch_sector_constituents_akshare(sector_name: str) -> pd.DataFrame | None:
    """Fetch constituents of a sector from AkShare.

    Tries industry first, then concept.
    """
    try:
        import akshare as ak

        # Try industry
        try:
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is not None and not df.empty:
                return _normalise_constituents_df(df, sector_name)
        except Exception:
            pass

        # Try concept
        try:
            df = ak.stock_board_concept_cons_em(symbol=sector_name)
            if df is not None and not df.empty:
                return _normalise_constituents_df(df, sector_name)
        except Exception:
            pass

        return None
    except ImportError:
        return None
    except Exception as exc:
        logger.debug("AkShare constituents fetch failed for %s: %s", sector_name, exc)
        return None


def _normalise_constituents_df(
    df: pd.DataFrame, sector_name: str,
) -> pd.DataFrame:
    """Normalise AkShare constituent DataFrame to standard columns."""
    result = pd.DataFrame()

    # Map common column names
    code_col = None
    name_col = None
    for c in df.columns:
        c_lower = str(c).lower().strip()
        if c_lower in ("代码", "code", "stock_code", "symbol", "品种代码"):
            code_col = c
        elif c_lower in ("名称", "name", "stock_name", "品种名称"):
            name_col = c

    if code_col is None:
        # Try the first column as code
        code_col = df.columns[0]
    if name_col is None and len(df.columns) > 1:
        name_col = df.columns[1]

    result["stock_code"] = df[code_col].astype(str).str.zfill(6) if code_col else ""
    result["stock_name"] = df[name_col].astype(str) if name_col else ""
    result["sector_name"] = sector_name

    return result


def sync_sector_basic(
    source: str = SOURCE_AKSHARE,
    trade_date: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Sync sector basic info from external source to DuckDB.

    Args:
        source: Data source identifier (default: 'akshare')
        trade_date: Not used currently, kept for interface consistency.
        dry_run: If True, only preview, don't write.

    Returns:
        dict with sync summary.
    """
    td = trade_date or datetime.now().strftime("%Y-%m-%d")

    if source == SOURCE_AKSHARE:
        result = _sync_sector_basic_akshare(dry_run)
    else:
        return {
            "status": "error",
            "source": source,
            "message": f"Unsupported source: {source}",
            "sectors_synced": 0,
            "dry_run": dry_run,
            "version": VERSION,
        }

    result["source"] = source
    result["trade_date"] = td
    result["dry_run"] = dry_run
    result["version"] = VERSION
    return result


def _sync_sector_basic_akshare(dry_run: bool) -> dict[str, Any]:
    """Sync sector basic info from AkShare."""
    industry_df = _fetch_sector_list_akshare(SECTOR_INDUSTRY)
    concept_df = _fetch_sector_list_akshare(SECTOR_CONCEPT)

    if industry_df is None and concept_df is None:
        return {
            "status": "error",
            "message": "AkShare 不可用或返回空数据，无法同步板块基础信息",
            "sectors_synced": 0,
        }

    all_sectors = []
    if industry_df is not None:
        all_sectors.append(industry_df)
    if concept_df is not None:
        all_sectors.append(concept_df)

    combined = pd.concat(all_sectors, ignore_index=True)
    combined["source"] = SOURCE_AKSHARE
    combined["source_sector_code"] = combined["sector_code"]
    combined["is_active"] = True
    combined["updated_at"] = datetime.now().isoformat(timespec="seconds")

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"预览：将同步 {len(combined)} 个板块（行业 {len(industry_df) if industry_df is not None else 0}，概念 {len(concept_df) if concept_df is not None else 0}）",
            "sectors_synced": len(combined),
            "preview": combined[["sector_code", "sector_name", "sector_type"]].head(10).to_dict("records"),
        }

    try:
        from src.sector.sector_repository import (
            upsert_sector_basic, delete_sector_basic_by_source,
        )
        delete_sector_basic_by_source(SOURCE_AKSHARE)
        count = upsert_sector_basic(combined)
        return {
            "status": "ok",
            "message": f"已同步 {count} 个板块基础信息",
            "sectors_synced": count,
        }
    except Exception as exc:
        logger.warning("Failed to upsert sector basic: %s", exc)
        return {
            "status": "error",
            "message": f"写入板块基础信息失败：{exc}",
            "sectors_synced": 0,
        }


def sync_stock_sector_map(
    source: str = SOURCE_AKSHARE,
    trade_date: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Sync stock-sector mappings from external source to DuckDB.

    Args:
        source: Data source identifier.
        trade_date: Not used currently.
        dry_run: If True, only preview.

    Returns:
        dict with sync summary.
    """
    td = trade_date or datetime.now().strftime("%Y-%m-%d")

    if source == SOURCE_AKSHARE:
        result = _sync_stock_sector_map_akshare(dry_run)
    else:
        return {
            "status": "error",
            "source": source,
            "message": f"Unsupported source: {source}",
            "mappings_synced": 0,
            "dry_run": dry_run,
            "version": VERSION,
        }

    result["source"] = source
    result["trade_date"] = td
    result["dry_run"] = dry_run
    result["version"] = VERSION
    return result


def _sync_stock_sector_map_akshare(dry_run: bool) -> dict[str, Any]:
    """Sync stock-sector mappings from AkShare.

    Strategy:
    1. Fetch sector list from local DB (must already be synced)
    2. For each sector, fetch constituents via AkShare
    3. Build stock_sector_map rows
    """
    try:
        from src.sector.sector_repository import list_all_sectors
        sectors_df = list_all_sectors()
    except Exception as exc:
        return {
            "status": "error",
            "message": f"无法读取板块列表：{exc}。请先运行 --sync-basic",
            "mappings_synced": 0,
        }

    if sectors_df is None or sectors_df.empty:
        # Try fetching directly from AkShare
        return _sync_map_direct_akshare(dry_run)

    all_mappings = []
    errors = 0
    sector_names = sectors_df["sector_name"].tolist()

    for sname in sector_names:
        try:
            cons_df = _fetch_sector_constituents_akshare(sname)
            if cons_df is not None and not cons_df.empty:
                cons_df["sector_code"] = sectors_df[
                    sectors_df["sector_name"] == sname
                ]["sector_code"].values[0] if sname in sectors_df["sector_name"].values else ""
                cons_df["sector_type"] = sectors_df[
                    sectors_df["sector_name"] == sname
                ]["sector_type"].values[0] if sname in sectors_df["sector_name"].values else "unknown"
                all_mappings.append(cons_df)
        except Exception:
            errors += 1
            continue

    if not all_mappings:
        return {
            "status": "error",
            "message": "无法获取任何板块成分股数据",
            "mappings_synced": 0,
        }

    combined = pd.concat(all_mappings, ignore_index=True)
    combined["source"] = SOURCE_AKSHARE
    combined["weight"] = 1.0
    combined["is_active"] = True
    combined["updated_at"] = datetime.now().isoformat(timespec="seconds")

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"预览：将同步 {len(combined)} 条股票板块映射（覆盖 {len(all_mappings)} 个板块）",
            "mappings_synced": len(combined),
            "preview": combined.head(10).to_dict("records"),
        }

    try:
        from src.sector.sector_repository import (
            upsert_stock_sector_map, delete_sector_mappings_by_source,
        )
        delete_sector_mappings_by_source(SOURCE_AKSHARE)
        count = upsert_stock_sector_map(combined)
        return {
            "status": "ok",
            "message": f"已同步 {count} 条股票板块映射",
            "mappings_synced": count,
        }
    except Exception as exc:
        logger.warning("Failed to upsert stock sector map: %s", exc)
        return {
            "status": "error",
            "message": f"写入股票板块映射失败：{exc}",
            "mappings_synced": 0,
        }


def _sync_map_direct_akshare(dry_run: bool) -> dict[str, Any]:
    """Direct sync from AkShare without pre-synced sector list."""
    # First sync sector basic
    basic_result = _sync_sector_basic_akshare(dry_run)
    if basic_result["status"] not in ("ok", "dry_run"):
        return {
            "status": "error",
            "message": "无法同步板块基础信息，跳过映射同步",
            "mappings_synced": 0,
        }

    if dry_run:
        return {
            "status": "dry_run",
            "message": "预览模式：需先确认板块基础信息同步后再运行映射同步",
            "mappings_synced": 0,
        }

    # Re-sync with now-populated sector list
    return _sync_stock_sector_map_akshare(dry_run=False)


# ── Service CLI ─────────────────────────────────────────────────────────────

def main_service() -> None:
    """CLI for querying sector data.

    Usage::

        python -m src.sector.sector_service --stock 000001
        python -m src.sector.sector_service --sector 银行
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description="V1.5.3 板块查询")
    parser.add_argument("--stock", default=None, help="股票代码")
    parser.add_argument("--sector", default=None, help="板块名称")
    parser.add_argument("--code", default=None, help="板块代码")
    parser.add_argument("--validate", action="store_true", help="验证板块映射完整性")
    parser.add_argument("--json", action="store_true", default=True, help="JSON输出")
    args = parser.parse_args()

    if args.validate:
        result = validate_sector_mapping()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.stock:
        result = get_sectors_by_stock(args.stock)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=str))
        return

    if args.sector or args.code:
        result = get_stocks_by_sector(sector_name=args.sector, sector_code=args.code)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=str))
        return

    parser.print_help()


# ── Sync CLI ────────────────────────────────────────────────────────────────


def main_sync() -> None:
    """CLI for syncing sector data.

    Usage::

        python -m src.sector.sector_sync --sync-basic --source akshare --dry-run
        python -m src.sector.sector_sync --sync-basic --source akshare --confirm
        python -m src.sector.sector_sync --sync-map --source akshare --dry-run
        python -m src.sector.sector_sync --sync-map --source akshare --confirm
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description="V1.5.3 板块数据同步")
    parser.add_argument("--sync-basic", action="store_true", help="同步板块基础信息")
    parser.add_argument("--sync-map", action="store_true", help="同步股票板块映射")
    parser.add_argument("--source", default=SOURCE_AKSHARE, help="数据源")
    parser.add_argument("--date", default=None, help="交易日期")
    parser.add_argument("--dry-run", action="store_true", default=True, help="预览模式")
    parser.add_argument("--confirm", action="store_true", default=False, help="确认写入")
    args = parser.parse_args()

    # If --confirm is passed, override dry_run
    dry_run = not args.confirm

    if args.sync_basic:
        result = sync_sector_basic(source=args.source, trade_date=args.date, dry_run=dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    if args.sync_map:
        result = sync_stock_sector_map(source=args.source, trade_date=args.date, dry_run=dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main_sync()
