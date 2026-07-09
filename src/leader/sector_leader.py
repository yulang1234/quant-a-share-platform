"""V1.6.1 sector leader identification."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.leader.leader_scoring import compute_leader_score
from src.leader.leader_types import (
    HIGH_RISK,
    LEADER_1,
    LEADER_2,
    MAKE_UP,
    NORMAL,
    PSEUDO,
    LeaderCandidate,
    SectorLeaderResult,
)

VERSION = "v1.6.1"


def identify_sector_leaders(
    trade_date: str, sector_name: str, top_n: int = 10
) -> SectorLeaderResult:
    """Identify sector leaders from local sector membership and local quotes."""
    td = str(trade_date)[:10]
    codes = _get_constituent_codes(sector_name)
    if not codes:
        return _empty_result(td, sector_name, ["no sector constituents"])

    df = _fetch_stocks_data(td, codes)
    if df is None or df.empty:
        return _empty_result(td, sector_name, ["no local quote data"])

    features_list = _build_features(df, td, codes)
    if not features_list:
        return _empty_result(td, sector_name, ["insufficient features"])

    candidates = [_candidate_from_features(feat) for feat in features_list]
    candidates.sort(key=lambda x: x.leader_score, reverse=True)
    if top_n > 0:
        candidates = candidates[:top_n]
    return _classify_leaders(candidates, td, sector_name)


def _candidate_from_features(feat: dict[str, Any]) -> LeaderCandidate:
    scores = compute_leader_score(feat)
    return LeaderCandidate(
        stock_code=feat["stock_code"],
        stock_name=feat.get("stock_name", feat["stock_code"]),
        leader_score=scores["leader_score"],
        relative_strength_score=scores["relative_strength_score"],
        turnover_score=scores["turnover_score"],
        price_rank_score=scores["price_rank_score"],
        resilience_score=scores["resilience_score"],
        startup_score=scores["startup_score"],
        trend_structure_score=scores["trend_structure_score"],
        continuity_score=scores["continuity_score"],
        pct_chg_5d=feat.get("pct_chg_5d") or 0,
        pct_chg_10d=feat.get("pct_chg_10d") or 0,
        turnover_amount=feat.get("turnover_amount") or 0,
        turnover_rank=feat.get("turnover_rank_in_sector", 0),
        trend_structure=_trend_label(feat),
    )


def _get_constituent_codes(sector_name: str) -> list[str]:
    try:
        from src.sector.sector_repository import get_stocks_by_sector

        df = get_stocks_by_sector(sector_name=sector_name)
        if df is None or df.empty or "stock_code" not in df.columns:
            return []
        return df["stock_code"].astype(str).str.zfill(6).tolist()
    except Exception:
        return []


def _fetch_stocks_data(trade_date: str, codes: list[str]) -> pd.DataFrame | None:
    try:
        from src.storage.duckdb_repo import query_df

        placeholders = ",".join(["?"] * len(codes))
        sql = (
            f"SELECT stock_code, trade_date, close, amount, pct_change, turnover_rate "
            f"FROM stock_daily_raw WHERE stock_code IN ({placeholders}) "
            "AND trade_date <= ? ORDER BY stock_code, trade_date"
        )
        df = query_df(sql, codes + [trade_date])
        if df is not None and not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df
    except Exception:
        return None


def _build_features(df: pd.DataFrame, trade_date: str, codes: list[str]) -> list[dict[str, Any]]:
    td = pd.to_datetime(trade_date).date()
    today = df[df["trade_date"] == td]
    if today.empty:
        return []

    sector_avg_5d = _sector_return(df, td, 5)
    sector_avg_10d = _sector_return(df, td, 10)
    all_codes = set(codes)
    amount_rank = _rank_map(today, all_codes, "amount")
    pct_rank = _rank_map(today, all_codes, "pct_change")
    features: list[dict[str, Any]] = []

    for code in all_codes:
        stock_df = df[df["stock_code"] == code].sort_values("trade_date")
        row_today = stock_df[stock_df["trade_date"] == td]
        if stock_df.empty or row_today.empty:
            continue

        closes = stock_df["close"].astype(float).values
        pcts = stock_df["pct_change"].dropna().astype(float).values
        features.append(
            {
                "stock_code": code,
                "stock_name": code,
                "pct_chg_5d": _stock_return(stock_df, td, 5),
                "pct_chg_10d": _stock_return(stock_df, td, 10),
                "sector_avg_5d": sector_avg_5d,
                "sector_avg_10d": sector_avg_10d,
                "turnover_amount": float(row_today["amount"].iloc[0]) if "amount" in row_today else 0,
                "drawdown_20d": _stock_drawdown(stock_df),
                "turnover_rank_in_sector": amount_rank.get(code, len(all_codes)),
                "price_rank_in_sector": pct_rank.get(code, len(all_codes)),
                "sector_stock_count": len(all_codes),
                "above_ma5": bool(len(closes) >= 5 and closes[-1] > np.mean(closes[-5:])),
                "above_ma10": bool(len(closes) >= 10 and closes[-1] > np.mean(closes[-10:])),
                "above_ma20": bool(len(closes) >= 20 and closes[-1] > np.mean(closes[-20:])),
                "up_days_recent": int(sum(1 for p in pcts[-5:] if p > 0)) if len(pcts) else 0,
                "startup_timing": "sync",
            }
        )

    return features


def _rank_map(today: pd.DataFrame, codes: set[str], column: str) -> dict[str, int]:
    values = {}
    for code in codes:
        row = today[today["stock_code"] == code]
        values[code] = float(row[column].iloc[0]) if not row.empty and column in row.columns else 0.0
    return {
        code: i + 1
        for i, (code, _) in enumerate(sorted(values.items(), key=lambda x: x[1], reverse=True))
    }


def _sector_return(df: pd.DataFrame, td, days: int) -> float:
    dates = sorted(df["trade_date"].unique())
    if td not in dates:
        return 0.0
    idx = dates.index(td)
    if idx < days - 1:
        return 0.0
    window = df[(df["trade_date"] >= dates[idx - days + 1]) & (df["trade_date"] <= td)]
    returns = []
    for _, group in window.groupby("stock_code"):
        group = group.sort_values("trade_date")
        if len(group) >= 2 and float(group["close"].iloc[0]) > 0:
            returns.append((float(group["close"].iloc[-1]) / float(group["close"].iloc[0]) - 1) * 100)
    return float(np.mean(returns)) if returns else 0.0


def _stock_return(stock_df: pd.DataFrame, td, days: int) -> float | None:
    dates = sorted(stock_df["trade_date"].unique())
    if td not in dates:
        return None
    idx = dates.index(td)
    if idx < days - 1:
        return None
    start = stock_df[stock_df["trade_date"] == dates[idx - days + 1]]
    end = stock_df[stock_df["trade_date"] == td]
    if start.empty or end.empty or float(start["close"].iloc[0]) <= 0:
        return None
    return round((float(end["close"].iloc[0]) / float(start["close"].iloc[0]) - 1) * 100, 2)


def _stock_drawdown(stock_df: pd.DataFrame) -> float:
    closes = stock_df["close"].astype(float).tail(20).values
    if len(closes) < 2:
        return 0.0
    peak = float(np.max(closes))
    return round((peak - float(closes[-1])) / peak * 100, 2) if peak > 0 else 0.0


def _trend_label(feat: dict[str, Any]) -> str:
    above = sum(1 for k in ("above_ma5", "above_ma10", "above_ma20") if feat.get(k))
    return {3: "bullish", 2: "positive", 1: "mixed", 0: "weak"}[above]


def _classify_leaders(candidates: list[LeaderCandidate], td: str, name: str) -> SectorLeaderResult:
    result = SectorLeaderResult(
        trade_date=td,
        sector_name=name,
        all_candidates=candidates,
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
    if not candidates:
        result.issue_summary.append("no candidates")
        return result

    for i, candidate in enumerate(candidates):
        if candidate.pct_chg_5d > 15 and candidate.leader_score >= 70:
            candidate.leader_type = HIGH_RISK
            candidate.risk_flags.append("short-term overheating")
            candidate.reason = "short-term gain is high"
            result.high_risk_chasing.append(candidate)
        elif candidate.continuity_score < 30 and candidate.pct_chg_5d > 5:
            candidate.leader_type = PSEUDO
            candidate.risk_flags.append("weak continuity")
            candidate.reason = "momentum lacks continuity"
            result.pseudo_leaders.append(candidate)
        elif i == 0 and candidate.leader_score >= 60:
            candidate.leader_type = LEADER_1
            candidate.reason = "top composite score in sector"
            result.leader_1 = candidate
        elif i == 1 and candidate.leader_score >= 50:
            candidate.leader_type = LEADER_2
            candidate.reason = "second composite score in sector"
            result.leader_2 = candidate
        elif candidate.startup_score >= 70 and candidate.leader_score < 60:
            candidate.leader_type = MAKE_UP
            candidate.reason = "early setup with lower composite score"
            result.make_up_candidates.append(candidate)
        else:
            candidate.leader_type = NORMAL

    result.risk_warnings.append("Research aid only. Not investment advice.")
    return result


def _empty_result(td: str, name: str, issues: list[str]) -> SectorLeaderResult:
    return SectorLeaderResult(
        trade_date=td,
        sector_name=name,
        sector_status="unknown",
        issue_summary=issues,
        risk_warnings=["insufficient local data"],
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
