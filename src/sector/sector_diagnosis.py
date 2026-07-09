"""V1.5.6 sector diagnosis — integrate market/sentiment/strength/mainline.

Wires together V1.5.1 (market), V1.5.2 (sentiment), V1.5.4 (strength),
V1.5.5 (mainline) into a structured diagnosis report.

Usage (CLI)::

    python -m src.sector.sector_diagnosis --date 2026-07-09 --sector 机器人
    python -m src.sector.sector_diagnosis --date 2026-07-09 --sectors 机器人,AI算力
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from src.rules.sector_diagnosis_rules import diagnose_sector
from src.sector.sector_diagnosis_types import SectorDiagnosis

logger = logging.getLogger(__name__)
VERSION = "v1.5.6"


# ── Public API ──────────────────────────────────────────────────────────────


def diagnose_sector_by_name(
    trade_date: str,
    sector_name: str | None = None,
    sector_code: str | None = None,
) -> SectorDiagnosis:
    """Diagnose a single sector, aggregating all available signals.

    Args:
        trade_date: YYYY-MM-DD
        sector_name: e.g. "机器人"
        sector_code: e.g. "BKxxxx"

    Returns:
        SectorDiagnosis with all fields populated.
    """
    td = str(trade_date)[:10]

    # 1. Resolve sector info
    sector_info = _get_sector_info(sector_code=sector_code, sector_name=sector_name)
    if sector_info is None:
        return SectorDiagnosis(
            trade_date=td, sector_code=sector_code or "", sector_name=sector_name or "",
            sector_type="unknown", diagnosis_status="unknown",
            missing_indicator_names=["sector_info"],
            reasons=[f"未找到板块: {sector_name or sector_code}"],
            action_hint="未找到该板块信息，请检查板块名称或代码。",
        )

    sc = sector_info.get("sector_code", "")
    sn = sector_info.get("sector_name", "")
    st = sector_info.get("sector_type", "unknown")

    # 2. Gather signals from each module (graceful degradation)
    market_env = _safe_get_market_environment(td)
    sentiment = _safe_get_sentiment_cycle(td)
    strength = _safe_get_sector_strength(td, sc)
    mainline = _safe_get_sector_mainline(td, sc)

    # 3. Run diagnosis rules
    diag_dict = diagnose_sector(market_env, sentiment, strength, mainline)

    return SectorDiagnosis(
        trade_date=td,
        sector_code=sc,
        sector_name=sn,
        sector_type=st,
        diagnosis_status=diag_dict["diagnosis_status"],
        mainline_status=diag_dict["mainline_status"],
        mainline_score=diag_dict["mainline_score"],
        mainline_probability=diag_dict["mainline_probability"],
        market_fit=diag_dict["market_fit"],
        sentiment_fit=diag_dict["sentiment_fit"],
        strength_score=diag_dict["strength_score"],
        strength_level=diag_dict["strength_level"],
        strength_rank=diag_dict["strength_rank"],
        trend_stage=diag_dict["trend_stage"],
        leader_structure=diag_dict["leader_structure"],
        buy_point_odds=diag_dict["buy_point_odds"],
        risk_level=diag_dict["risk_level"],
        suggested_action=diag_dict["suggested_action"],
        action_hint=diag_dict["action_hint"],
        observation_conditions=diag_dict["observation_conditions"],
        invalidation_conditions=diag_dict["invalidation_conditions"],
        risk_flags=diag_dict["risk_flags"],
        missing_indicator_names=diag_dict["missing_indicator_names"],
        reasons=diag_dict["reasons"],
    )


def diagnose_sectors(
    trade_date: str,
    sector_names: list[str] | None = None,
    sector_codes: list[str] | None = None,
) -> list[SectorDiagnosis]:
    """Diagnose multiple sectors."""
    results: list[SectorDiagnosis] = []
    if sector_names:
        for name in sector_names:
            try:
                results.append(diagnose_sector_by_name(trade_date, sector_name=name))
            except Exception as exc:
                logger.warning("Diagnosis failed for %s: %s", name, exc)
    if sector_codes:
        for code in sector_codes:
            try:
                results.append(diagnose_sector_by_name(trade_date, sector_code=code))
            except Exception as exc:
                logger.warning("Diagnosis failed for %s: %s", code, exc)
    return results


# ── Safe signal gatherers ───────────────────────────────────────────────────


def _safe_get_market_environment(td: str) -> dict | None:
    try:
        from src.market.market_environment import build_market_environment
        env = build_market_environment(td)
        return env.as_dict()
    except Exception:
        return None


def _safe_get_sentiment_cycle(td: str) -> dict | None:
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle(td)
        return cycle.as_dict()
    except Exception:
        return None


def _safe_get_sector_strength(td: str, sector_code: str) -> dict | None:
    try:
        from src.sector.sector_strength import calculate_sector_strength
        r = calculate_sector_strength(td, sector_code=sector_code)
        if r.strength_level == "unknown":
            return None
        return r.as_dict()
    except Exception:
        return None


def _safe_get_sector_mainline(td: str, sector_code: str) -> dict | None:
    try:
        from src.sector.sector_mainline import identify_sector_mainline
        r = identify_sector_mainline(td, sector_code=sector_code)
        if r.mainline_status == "unknown":
            return None
        return r.as_dict()
    except Exception:
        return None


def _get_sector_info(sector_code=None, sector_name=None) -> dict | None:
    try:
        from src.sector.sector_repository import get_sector_basic
        df = get_sector_basic(sector_code=sector_code, sector_name=sector_name)
        if df is None or df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="V1.5.6 板块问诊")
    parser.add_argument("--date", default=None, help="交易日期")
    parser.add_argument("--sector", default=None, help="板块名称或代码")
    parser.add_argument("--sectors", default=None, help="多个板块，逗号分隔")
    args = parser.parse_args()

    td = args.date or date.today().isoformat()

    if args.sector:
        result = diagnose_sector_by_name(td, sector_name=args.sector)
        _print_diagnosis(result)

    elif args.sectors:
        names = [s.strip() for s in args.sectors.split(",")]
        results = diagnose_sectors(td, sector_names=names)
        for r in results:
            _print_diagnosis(r)

    else:
        parser.print_help()


def _print_diagnosis(d: SectorDiagnosis) -> None:
    """Print diagnosis as JSON."""
    print(json.dumps(d.as_dict(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
