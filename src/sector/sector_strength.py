"""V1.5.4 sector strength — compute strength scores for sectors.

Calculates sector-level indicators by aggregating constituent stock data
from ``stock_daily_raw``, then applies scoring rules.

Usage (CLI)::

    python -m src.sector.sector_strength --date 2026-07-09 --all --dry-run
    python -m src.sector.sector_strength --date 2026-07-09 --sector 银行
    python -m src.sector.sector_strength --date 2026-07-09 --rank --top-n 20
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.rules.sector_strength_rules import (
    compute_strength_score,
    compute_benchmark_returns,
)
from src.sector.sector_strength_types import (
    SectorStrengthResult,
    SectorStrengthRanking,
    AllSectorStrengthResult,
    STRENGTH_UNKNOWN,
)

logger = logging.getLogger(__name__)

VERSION = "v1.5.4"
_PRIOR_DAYS = 25  # enough for 20-day window


# ── Public API ──────────────────────────────────────────────────────────────


def calculate_sector_strength(
    trade_date: str,
    sector_code: str | None = None,
    sector_name: str | None = None,
) -> SectorStrengthResult:
    """Calculate strength for a single sector.

    Args:
        trade_date: YYYY-MM-DD
        sector_code: sector identifier
        sector_name: sector name (used if sector_code not given)

    Returns:
        SectorStrengthResult — strength_level = unknown if data insufficient.
    """
    td = str(trade_date)[:10]

    # 1. Get sector info
    sector_info = _get_sector_info(sector_code=sector_code, sector_name=sector_name)
    if sector_info is None:
        return _unknown_result(td, sector_code or "", sector_name or "")

    sc = sector_info["sector_code"]
    sn = sector_info["sector_name"]
    st = sector_info.get("sector_type", "unknown")
    src = sector_info.get("source", "unknown")

    # 2. Get constituent stocks
    constituents = _get_constituents(sc)
    if not constituents:
        return SectorStrengthResult(
            trade_date=td, sector_code=sc, sector_name=sn,
            sector_type=st, source=src, stock_count=0,
            strength_level="unknown",
            missing_indicator_names=["constituents"],
            reasons=["板块无成分股数据"],
        )

    stock_codes = list(constituents.keys())
    stock_count = len(stock_codes)

    # 3. Fetch stock data
    try:
        df_hist, prior_dates = _fetch_stock_data(td, stock_codes)
    except Exception as exc:
        logger.warning("Failed to fetch stock data: %s", exc)
        return SectorStrengthResult(
            trade_date=td, sector_code=sc, sector_name=sn,
            sector_type=st, source=src, stock_count=stock_count,
            strength_level="unknown",
            missing_indicator_names=["stock_data"],
            reasons=[f"无法获取行情数据：{exc}"],
        )

    if df_hist is None or df_hist.empty:
        return SectorStrengthResult(
            trade_date=td, sector_code=sc, sector_name=sn,
            sector_type=st, source=src, stock_count=stock_count,
            strength_level="unknown",
            missing_indicator_names=["stock_data"],
            reasons=["板块成分股无行情数据"],
        )

    # 4. Compute indicators
    indicators = _compute_sector_indicators(df_hist, td, prior_dates, stock_count)
    missing = indicators.pop("missing_indicator_names", [])

    # 5. Compute benchmark
    benchmark = _compute_market_benchmark(df_hist, prior_dates)
    benchmark_note = "benchmark 使用全市场有效样本等权平均近似（无指数数据）"

    # 6. Add relative strength
    for period in ["3d", "5d", "10d", "20d"]:
        key = f"return_{period}"
        bench_key = f"return_{period}"
        if indicators.get(key) is not None and benchmark.get(bench_key) is not None:
            indicators[f"relative_strength_{period}"] = round(
                indicators[key] - benchmark[bench_key], 4
            )

    # 7. Score
    score, level, reasons = compute_strength_score(indicators)
    reasons.append(benchmark_note)

    return SectorStrengthResult(
        trade_date=td,
        sector_code=sc,
        sector_name=sn,
        sector_type=st,
        source=src,
        stock_count=stock_count,
        valid_stock_count=indicators.get("valid_stock_count", 0),
        avg_pct_chg=indicators.get("avg_pct_chg", 0.0),
        median_pct_chg=indicators.get("median_pct_chg", 0.0),
        return_3d=indicators.get("return_3d"),
        return_5d=indicators.get("return_5d"),
        return_10d=indicators.get("return_10d"),
        return_20d=indicators.get("return_20d"),
        relative_strength_3d=indicators.get("relative_strength_3d"),
        relative_strength_5d=indicators.get("relative_strength_5d"),
        relative_strength_10d=indicators.get("relative_strength_10d"),
        relative_strength_20d=indicators.get("relative_strength_20d"),
        turnover_ratio_5d=indicators.get("turnover_ratio_5d"),
        turnover_ratio_20d=indicators.get("turnover_ratio_20d"),
        up_count=indicators.get("up_count", 0),
        down_count=indicators.get("down_count", 0),
        flat_count=indicators.get("flat_count", 0),
        up_ratio=indicators.get("up_ratio", 0.0),
        limit_up_count=indicators.get("limit_up_count", 0),
        limit_down_count=indicators.get("limit_down_count", 0),
        big_gain_count=indicators.get("big_gain_count", 0),
        big_loss_count=indicators.get("big_loss_count", 0),
        strength_score=score,
        strength_level=level,
        missing_indicator_names=missing,
        reasons=reasons,
    )


def calculate_all_sector_strength(
    trade_date: str,
    sector_type: str | None = None,
) -> AllSectorStrengthResult:
    """Calculate strength for all sectors.

    Args:
        trade_date: YYYY-MM-DD
        sector_type: filter by sector_type (industry/concept), None = all.

    Returns:
        AllSectorStrengthResult with results and error summary.
    """
    td = str(trade_date)[:10]
    sectors = _list_all_sectors(sector_type)

    if sectors is None or sectors.empty:
        return AllSectorStrengthResult(
            trade_date=td, sector_count=0,
            errors=["无板块数据，请先运行 V1.5.3 同步"],
        )

    results: list[SectorStrengthResult] = []
    errors: list[str] = []

    for _, srow in sectors.iterrows():
        try:
            r = calculate_sector_strength(td, sector_code=srow["sector_code"])
            results.append(r)
        except Exception as exc:
            errors.append(f"{srow.get('sector_name', '?')}: {exc}")

    return AllSectorStrengthResult(
        trade_date=td,
        results=results,
        sector_count=len(sectors),
        calculated_count=len(results),
        error_count=len(errors),
        errors=errors,
    )


def get_sector_rank(
    trade_date: str,
    top_n: int = 20,
    sector_type: str | None = None,
) -> SectorStrengthRanking:
    """Get sector strength ranking for a given date.

    Args:
        trade_date: YYYY-MM-DD
        top_n: number of top sectors to return.
        sector_type: filter by type.

    Returns:
        SectorStrengthRanking with sorted sectors.
    """
    all_result = calculate_all_sector_strength(trade_date, sector_type)

    # Sort by strength_score descending
    sorted_results = sorted(
        all_result.results,
        key=lambda r: r.strength_score,
        reverse=True,
    )[:top_n]

    sectors: list[dict[str, Any]] = []
    for rank, r in enumerate(sorted_results, 1):
        sectors.append({
            "rank_overall": rank,
            "sector_code": r.sector_code,
            "sector_name": r.sector_name,
            "strength_score": r.strength_score,
            "strength_level": r.strength_level,
            "return_5d": r.return_5d,
            "relative_strength_5d": r.relative_strength_5d,
            "up_ratio": r.up_ratio,
            "limit_up_count": r.limit_up_count,
        })

    return SectorStrengthRanking(
        trade_date=trade_date,
        sector_type=sector_type,
        top_n=top_n,
        sectors=sectors,
    )


# ── Internal helpers ────────────────────────────────────────────────────────


def _get_sector_info(sector_code=None, sector_name=None) -> dict | None:
    """Get sector info from repository."""
    try:
        from src.sector.sector_repository import get_sector_basic
        df = get_sector_basic(sector_code=sector_code, sector_name=sector_name)
        if df is None or df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


def _get_constituents(sector_code: str) -> dict[str, str]:
    """Return {stock_code: stock_name} for a sector."""
    try:
        from src.sector.sector_repository import get_stocks_by_sector
        df = get_stocks_by_sector(sector_code=sector_code)
        if df is None or df.empty:
            return {}
        result = {}
        for _, row in df.iterrows():
            code = str(row.get("stock_code", "")).zfill(6)
            name = str(row.get("stock_name", ""))
            if code:
                result[code] = name
        return result
    except Exception:
        return {}


def _list_all_sectors(sector_type=None) -> pd.DataFrame:
    """Return all active sectors, optionally filtered by type."""
    try:
        from src.sector.sector_repository import list_all_sectors
        df = list_all_sectors()
        if df is None or df.empty:
            return pd.DataFrame()
        if sector_type:
            df = df[df["sector_type"] == sector_type]
        return df
    except Exception:
        return pd.DataFrame()


def _fetch_stock_data(
    trade_date: str, stock_codes: list[str],
) -> tuple[pd.DataFrame, list]:
    """Fetch historical stock data for a set of stocks.

    Returns (df_hist, sorted_prior_dates).
    """
    from src.storage.duckdb_repo import query_df

    # Get prior dates
    prior_df = query_df(
        "SELECT DISTINCT trade_date FROM stock_daily_raw "
        "WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
        [trade_date, _PRIOR_DAYS],
    )
    if prior_df is None or prior_df.empty:
        return pd.DataFrame(), []

    all_dates = sorted(pd.to_datetime(prior_df["trade_date"]).dt.date.tolist())
    if not all_dates:
        return pd.DataFrame(), []

    min_date = str(all_dates[0])
    max_date = str(max(all_dates))

    # Fetch window data for these stocks (use IN clause)
    if not stock_codes:
        return pd.DataFrame(), all_dates

    # Batch query — DuckDB handles IN with many values efficiently
    placeholders = ",".join(["?" for _ in stock_codes])
    cols = "stock_code, trade_date, close, amount, pct_change"
    sql = (
        f"SELECT {cols} FROM stock_daily_raw "
        f"WHERE stock_code IN ({placeholders}) "
        "AND trade_date >= ? AND trade_date <= ? "
        "ORDER BY stock_code, trade_date"
    )
    params = stock_codes + [min_date, max_date]
    df = query_df(sql, params)

    if df is not None:
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    return df if df is not None else pd.DataFrame(), all_dates


def _compute_sector_indicators(
    df_hist: pd.DataFrame, trade_date: str, prior_dates: list, stock_count: int,
) -> dict[str, Any]:
    """Aggregate constituent stock data into sector-level indicators."""
    td_dt = pd.to_datetime(trade_date).date()
    missing: list[str] = []

    today = df_hist[df_hist["trade_date"] == td_dt]
    if today.empty:
        return {
            "valid_stock_count": 0, "stock_count": stock_count,
            "missing_indicator_names": ["all"],
        }

    pct = today["pct_change"].dropna()
    n_valid = len(pct)

    indicators: dict[str, Any] = {
        "stock_count": stock_count,
        "valid_stock_count": n_valid,
        "avg_pct_chg": round(float(pct.mean()), 4) if n_valid else 0.0,
        "median_pct_chg": round(float(pct.median()), 4) if n_valid else 0.0,
        "up_count": int((pct > 0).sum()),
        "down_count": int((pct < 0).sum()),
        "flat_count": int((pct == 0).sum()),
        "up_ratio": round(float((pct > 0).sum()) / max(n_valid, 1), 4),
        "limit_up_count": int((pct >= 9.8).sum()),
        "limit_down_count": int((pct <= -9.8).sum()),
        "big_gain_count": int((pct >= 5.0).sum()),
        "big_loss_count": int((pct <= -5.0).sum()),
        "approximate_limit_up": True,
        "approximate_limit_down": True,
    }

    # Multi-period returns
    _add_multi_period_returns(indicators, df_hist, prior_dates, td_dt, missing)

    # Turnover ratios
    _add_turnover_ratios(indicators, df_hist, prior_dates, td_dt, missing)

    indicators["missing_indicator_names"] = missing
    return indicators


def _add_multi_period_returns(
    indicators: dict, df_hist: pd.DataFrame,
    prior_dates: list, td_dt, missing: list,
) -> None:
    """Compute sector equal-weighted 3/5/10/20 day returns."""
    periods = {"3d": 3, "5d": 5, "10d": 10, "20d": 20}
    sorted_dates = sorted(prior_dates + [td_dt])
    today_idx = sorted_dates.index(td_dt) if td_dt in sorted_dates else -1

    for label, n in periods.items():
        if today_idx < n - 1:
            missing.append(f"return_{label}")
            continue

        start_date = sorted_dates[today_idx - n + 1]
        window = df_hist[
            (df_hist["trade_date"] >= start_date)
            & (df_hist["trade_date"] <= td_dt)
        ]

        # Per-stock compound return, then equal-weight average
        returns = []
        for code, group in window.groupby("stock_code"):
            group = group.sort_values("trade_date")
            if len(group) < 2:
                continue
            try:
                first_close = group["close"].iloc[0]
                last_close = group["close"].iloc[-1]
                if first_close and first_close > 0:
                    ret = (last_close / first_close - 1) * 100
                    returns.append(ret)
            except Exception:
                continue

        if returns:
            indicators[f"return_{label}"] = round(float(np.mean(returns)), 4)
        else:
            missing.append(f"return_{label}")


def _add_turnover_ratios(
    indicators: dict, df_hist: pd.DataFrame,
    prior_dates: list, td_dt, missing: list,
) -> None:
    """Compute sector turnover ratios vs 5d / 20d averages."""
    try:
        daily_amount = df_hist.groupby("trade_date")["amount"].sum().reset_index()
        daily_amount = daily_amount.sort_values("trade_date")
        daily_amount.columns = ["trade_date", "daily_amount"]

        daily_amount["ma5"] = daily_amount["daily_amount"].rolling(5, min_periods=5).mean()
        daily_amount["ma20"] = daily_amount["daily_amount"].rolling(20, min_periods=20).mean()

        row = daily_amount[daily_amount["trade_date"] == td_dt]
        if row.empty:
            missing.extend(["turnover_ratio_5d", "turnover_ratio_20d"])
            return

        today_amt = row.iloc[0]["daily_amount"]
        ma5 = row.iloc[0]["ma5"]
        ma20 = row.iloc[0]["ma20"]

        if pd.notna(ma5) and ma5 > 0:
            indicators["turnover_ratio_5d"] = round(float(today_amt / ma5), 4)
        else:
            missing.append("turnover_ratio_5d")

        if pd.notna(ma20) and ma20 > 0:
            indicators["turnover_ratio_20d"] = round(float(today_amt / ma20), 4)
        else:
            missing.append("turnover_ratio_20d")
    except Exception:
        missing.extend(["turnover_ratio_5d", "turnover_ratio_20d"])


def _compute_market_benchmark(
    df_hist: pd.DataFrame, prior_dates: list,
) -> dict[str, float | None]:
    """Compute equal-weighted market benchmark returns."""
    result: dict[str, float | None] = {}
    try:
        daily = df_hist.groupby("trade_date")["pct_change"].apply(list).reset_index()
        all_pct: dict[str, list[float]] = {}
        for _, row in daily.iterrows():
            d = str(row["trade_date"])[:10]
            vals = [v for v in row["pct_change"] if v is not None and not (
                isinstance(v, float) and np.isnan(v)
            )]
            if vals:
                all_pct[d] = vals

        sorted_dates = sorted(prior_dates)
        result = compute_benchmark_returns(all_pct, [str(d) for d in sorted_dates])
    except Exception:
        pass
    return result


def _unknown_result(td: str, code: str, name: str) -> SectorStrengthResult:
    return SectorStrengthResult(
        trade_date=td, sector_code=code, sector_name=name,
        sector_type="unknown", source="unknown",
        strength_level="unknown", stock_count=0,
        missing_indicator_names=["sector_info"],
        reasons=["未找到板块信息"],
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="V1.5.4 板块强度计算")
    parser.add_argument("--date", default=None, help="交易日期 YYYY-MM-DD")
    parser.add_argument("--sector", default=None, help="板块名称或代码")
    parser.add_argument("--all", action="store_true", help="计算所有板块")
    parser.add_argument("--rank", action="store_true", help="输出排名")
    parser.add_argument("--top-n", type=int, default=20, help="排名数量")
    parser.add_argument("--type", default=None, help="板块类型过滤")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    td = args.date or date.today().isoformat()

    if args.sector:
        result = calculate_sector_strength(td, sector_name=args.sector)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=str))

    elif args.rank:
        ranking = get_sector_rank(td, top_n=args.top_n, sector_type=args.type)
        print(json.dumps(ranking.as_dict(), ensure_ascii=False, indent=2, default=str))

    elif args.all:
        all_result = calculate_all_sector_strength(td, sector_type=args.type)
        print(json.dumps(all_result.as_dict(), ensure_ascii=False, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
