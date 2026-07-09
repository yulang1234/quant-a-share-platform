"""Streamlit-independent data helpers for V1.6.1 sector leader view."""
from __future__ import annotations

import pandas as pd

from src.leader.leader_report import build_leader_markdown
from src.leader.leader_types import LEADER_CN


def load_sector_options() -> list[str]:
    try:
        from src.sector.sector_repository import list_all_sectors

        df = list_all_sectors()
        if df is not None and not df.empty and "sector_name" in df.columns:
            return sorted(df["sector_name"].dropna().astype(str).tolist())
    except Exception:
        pass
    return []


def load_sector_leader_result(trade_date: str, sector_name: str) -> dict | None:
    try:
        from src.leader.sector_leader import identify_sector_leaders

        return identify_sector_leaders(trade_date, sector_name).as_dict()
    except Exception:
        return None


def leader_type_to_cn(value: str) -> str:
    return LEADER_CN.get(value, value)


def candidates_to_df(result: dict | None) -> pd.DataFrame:
    rows = []
    for candidate in (result or {}).get("all_candidates") or []:
        rows.append(
            {
                "rank_score": candidate.get("leader_score", 0),
                "leader_type": leader_type_to_cn(candidate.get("leader_type", "")),
                "stock_code": candidate.get("stock_code", ""),
                "stock_name": candidate.get("stock_name", ""),
                "relative_strength_score": candidate.get("relative_strength_score", 0),
                "turnover_score": candidate.get("turnover_score", 0),
                "price_rank_score": candidate.get("price_rank_score", 0),
                "pct_chg_5d": candidate.get("pct_chg_5d", 0),
                "risk_flags": ", ".join(candidate.get("risk_flags", [])),
                "reason": candidate.get("reason", ""),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("rank_score", ascending=False)


def leader_csv_bytes(result: dict | None) -> bytes:
    return candidates_to_df(result).to_csv(index=False).encode("utf-8-sig")


def leader_markdown_bytes(result: dict | None) -> bytes:
    if not result:
        return b""
    return build_leader_markdown(result).encode("utf-8")
