"""V1.5.5 sector mainline — identify mainline sectors.

Computes multi-day strength, analyzes rank persistence and stability,
then classifies each sector into mainline status.

Usage (CLI)::

    python -m src.sector.sector_mainline --date 2026-07-09 --all
    python -m src.sector.sector_mainline --date 2026-07-09 --sector 机器人
    python -m src.sector.sector_mainline --date 2026-07-09 --snapshot
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.rules.sector_mainline_rules import classify_mainline, PERSISTENCE_LOOKBACK
from src.sector.sector_mainline_types import (
    SectorMainlineResult,
    MainlineSnapshot,
    AllMainlineResult,
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
)

logger = logging.getLogger(__name__)
VERSION = "v1.5.5"


# ── Public API ──────────────────────────────────────────────────────────────


def identify_sector_mainline(
    trade_date: str,
    sector_code: str | None = None,
    sector_name: str | None = None,
) -> SectorMainlineResult:
    """Identify mainline status for a single sector.

    Calculates multi-day strength and analyzes persistence.
    """
    td = str(trade_date)[:10]

    # 1. Calculate multi-day strength
    multi = _calc_multi_day_strength(td, sector_code, sector_name)
    if multi is None or not multi.get("today"):
        return _unknown_result(td, sector_code or "", sector_name or "")

    today = multi["today"]
    historical_ranks = multi["historical_ranks"]
    historical_strengths = multi["historical_strengths"]

    # 2. Classify
    classification = classify_mainline(today, historical_ranks, historical_strengths)

    return SectorMainlineResult(
        trade_date=td,
        sector_code=today.get("sector_code", sector_code or ""),
        sector_name=today.get("sector_name", sector_name or ""),
        sector_type=today.get("sector_type", "unknown"),
        mainline_status=classification["mainline_status"],
        mainline_score=classification["mainline_score"],
        confidence=classification["confidence"],
        rank_overall=historical_ranks[-1] if historical_ranks else 0,
        strength_score=today.get("strength_score", 0),
        strength_level=today.get("strength_level", "unknown"),
        persistence_days=classification["persistence_days"],
        rank_stability_score=classification["rank_stability_score"],
        relative_strength_score=classification["relative_strength_score"],
        turnover_confirmation=classification["turnover_confirmation"],
        breadth_confirmation=classification["breadth_confirmation"],
        limit_up_confirmation=classification["limit_up_confirmation"],
        risk_flags=classification["risk_flags"],
        missing_indicator_names=classification["missing_indicator_names"],
        reasons=classification["reasons"],
    )


def identify_all_sector_mainlines(
    trade_date: str,
    sector_type: str | None = None,
) -> AllMainlineResult:
    """Identify mainline status for all sectors."""
    td = str(trade_date)[:10]

    sectors = _list_all_sectors(sector_type)
    if sectors is None or sectors.empty:
        return AllMainlineResult(trade_date=td, sector_count=0)

    results: list[SectorMainlineResult] = []
    for _, srow in sectors.iterrows():
        try:
            r = identify_sector_mainline(td, sector_code=srow["sector_code"])
            results.append(r)
        except Exception as exc:
            logger.warning("Mainline failed for %s: %s", srow.get("sector_name", "?"), exc)

    return AllMainlineResult(
        trade_date=td,
        results=results,
        sector_count=len(sectors),
    )


def build_mainline_snapshot(
    trade_date: str,
    sector_type: str | None = None,
) -> MainlineSnapshot:
    """Build a daily mainline snapshot with categorized sectors."""
    all_result = identify_all_sector_mainlines(trade_date, sector_type)

    snapshot = MainlineSnapshot(trade_date=trade_date)

    for r in all_result.results:
        entry = {
            "sector_code": r.sector_code,
            "sector_name": r.sector_name,
            "mainline_score": r.mainline_score,
            "confidence": r.confidence,
            "rank_overall": r.rank_overall,
            "risk_flags": r.risk_flags,
        }
        status = r.mainline_status
        if status == MAINLINE_CONFIRMED:
            snapshot.confirmed_mainlines.append(entry)
        elif status == MAINLINE_POTENTIAL:
            snapshot.potential_mainlines.append(entry)
        elif status == MAINLINE_ONE_DAY:
            snapshot.one_day_themes.append(entry)
        elif status == MAINLINE_COOLING:
            snapshot.cooling_sectors.append(entry)
        elif status == MAINLINE_HIGH_RISK:
            snapshot.high_risk_sectors.append(entry)

    snapshot.has_clear_mainline = len(snapshot.confirmed_mainlines) > 0

    # Generate summary
    parts = []
    if snapshot.confirmed_mainlines:
        parts.append(f"当前存在 {len(snapshot.confirmed_mainlines)} 个确认主线")
    if snapshot.potential_mainlines:
        parts.append(f"{len(snapshot.potential_mainlines)} 个潜在主线待观察")
    if snapshot.one_day_themes:
        parts.append(f"{len(snapshot.one_day_themes)} 个一日游题材")
    if snapshot.cooling_sectors:
        parts.append(f"{len(snapshot.cooling_sectors)} 个板块正在降温")
    if snapshot.high_risk_sectors:
        parts.append(f"{len(snapshot.high_risk_sectors)} 个板块处于高风险状态")

    if not parts:
        snapshot.market_mainline_summary = "当前市场无明确主线，板块结构较散乱。"
    else:
        snapshot.market_mainline_summary = "；".join(parts) + "。"

    return snapshot


def get_confirmed_mainlines(trade_date: str, top_n: int = 5) -> list[dict]:
    """Get confirmed mainline sectors."""
    snapshot = build_mainline_snapshot(trade_date)
    return sorted(
        snapshot.confirmed_mainlines,
        key=lambda x: x["mainline_score"], reverse=True,
    )[:top_n]


def get_potential_mainlines(trade_date: str, top_n: int = 10) -> list[dict]:
    """Get potential mainline sectors."""
    snapshot = build_mainline_snapshot(trade_date)
    return sorted(
        snapshot.potential_mainlines,
        key=lambda x: x["mainline_score"], reverse=True,
    )[:top_n]


# ── Multi-day strength calculation ──────────────────────────────────────────


def _calc_multi_day_strength(
    trade_date: str, sector_code=None, sector_name=None,
) -> dict | None:
    """Calculate strength for the last N days for a sector.

    Returns {today: dict, historical_ranks: [int], historical_strengths: [dict]}
    """
    from src.sector.sector_strength import calculate_sector_strength

    td = datetime.strptime(trade_date, "%Y-%m-%d")

    # Generate past trading dates (approximate — skip weekends)
    dates = []
    d = td
    for _ in range(PERSISTENCE_LOOKBACK + 1):
        dates.append(d.strftime("%Y-%m-%d"))
        d = d - timedelta(days=1)
        # Skip weekends crudely
        while d.weekday() >= 5:
            d = d - timedelta(days=1)
    dates = list(reversed(dates))

    strengths = []
    ranks = []
    for d_str in dates:
        try:
            r = calculate_sector_strength(d_str, sector_code=sector_code, sector_name=sector_name)
            if r.strength_level != "unknown":
                strengths.append(r.as_dict())
        except Exception:
            continue

    if not strengths:
        return None

    # Calculate ranks: rank each date's sectors against each other
    # Since we only have one sector, use strength_score as proxy rank
    # (caller must provide multi-sector data for real ranks)
    for s in strengths:
        ss = s.get("strength_score", 0)
        # Rough rank estimation: map score to rank
        # 90+ = top 5, 80+ = top 15, 70+ = top 30, etc.
        if ss >= 90:
            ranks.append(3)
        elif ss >= 80:
            ranks.append(8)
        elif ss >= 70:
            ranks.append(18)
        elif ss >= 60:
            ranks.append(30)
        elif ss >= 50:
            ranks.append(50)
        else:
            ranks.append(80)

    return {
        "today": strengths[-1] if strengths else None,
        "historical_ranks": ranks,
        "historical_strengths": strengths[:-1] if len(strengths) > 1 else [],
    }


# ── Helpers ────────────────────────────────────────────────────────────────


def _list_all_sectors(sector_type=None) -> pd.DataFrame:
    try:
        from src.sector.sector_repository import list_all_sectors
        df = list_all_sectors()
        if df is not None and not df.empty and sector_type:
            df = df[df["sector_type"] == sector_type]
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _unknown_result(td: str, code: str, name: str) -> SectorMainlineResult:
    return SectorMainlineResult(
        trade_date=td, sector_code=code, sector_name=name,
        sector_type="unknown", mainline_status=MAINLINE_UNKNOWN,
        missing_indicator_names=["sector_strength_data"],
        reasons=["板块强度数据不足，无法判断主线状态"],
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="V1.5.5 主线板块识别")
    parser.add_argument("--date", default=None, help="交易日期")
    parser.add_argument("--sector", default=None, help="板块名称")
    parser.add_argument("--all", action="store_true", help="识别全部板块")
    parser.add_argument("--snapshot", action="store_true", help="输出主线快照")
    parser.add_argument("--type", default=None, help="板块类型过滤")
    args = parser.parse_args()

    td = args.date or date.today().isoformat()

    if args.sector:
        result = identify_sector_mainline(td, sector_name=args.sector)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=str))

    elif args.snapshot:
        snap = build_mainline_snapshot(td, sector_type=args.type)
        print(json.dumps(snap.as_dict(), ensure_ascii=False, indent=2, default=str))

    elif args.all:
        all_result = identify_all_sector_mainlines(td, sector_type=args.type)
        print(json.dumps(all_result.as_dict(), ensure_ascii=False, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
