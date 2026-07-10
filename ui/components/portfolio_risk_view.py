"""V1.7.3 Streamlit-independent data helpers for portfolio risk view."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.portfolio.portfolio_risk_report import (
    build_all_portfolios_risk_markdown,
    build_portfolio_risk_markdown,
)
from src.portfolio.portfolio_risk_types import PERMISSION_CN, RISK_LEVEL_CN


def load_portfolio_options() -> list[dict[str, Any]]:
    from src.repositories.portfolio_position_repo import PortfolioPositionRepository
    from src.portfolio.position_service import _position_to_dict
    repo = PortfolioPositionRepository()
    positions = repo.list_positions(status="active", limit=10000)
    pos_dicts = [_position_to_dict(p) for p in positions]
    groups: set[tuple[str, bool]] = set()
    for p in pos_dicts:
        groups.add((p.get("portfolio_name", "default"), p.get("is_simulated", True)))
    return [{"portfolio_name": g[0], "is_simulated": g[1]} for g in sorted(groups)]


def run_portfolio_risk_analysis(trade_date: str, portfolio_name: str = "default", is_simulated: bool = False, persist: bool = False) -> dict[str, Any]:
    from src.portfolio.portfolio_risk_service import analyze_portfolio_risk
    result = analyze_portfolio_risk(trade_date, portfolio_name, is_simulated, persist=persist)
    return result.as_dict()


def run_all_portfolio_risk_analysis(trade_date: str, persist: bool = False) -> dict[str, Any]:
    from src.portfolio.portfolio_risk_service import analyze_all_portfolios
    return analyze_all_portfolios(trade_date, persist=persist)


def save_portfolio_risk_from_ui(result: dict[str, Any]) -> dict[str, Any]:
    from src.portfolio.portfolio_risk_service import save_portfolio_risk_snapshot
    from src.portfolio.portfolio_risk_types import PortfolioRiskResult
    r = PortfolioRiskResult(
        trade_date=result.get("trade_date", ""), portfolio_name=result.get("portfolio_name", "default"),
        is_simulated=result.get("is_simulated", True),
        portfolio_risk_score=result.get("portfolio_risk_score", 0),
        portfolio_risk_level=result.get("portfolio_risk_level", "unknown"),
        portfolio_permission=result.get("portfolio_permission", "unknown"),
        position_count=result.get("position_count", 0),
        total_position_pct=result.get("total_position_pct", 0),
        cash_pct=result.get("cash_pct"),
        max_single_position_pct=result.get("max_single_position_pct", 0),
        max_single_position_code=result.get("max_single_position_code", ""),
        max_sector_position_pct=result.get("max_sector_position_pct", 0),
        max_sector_name=result.get("max_sector_name", ""),
        top3_position_pct=result.get("top3_position_pct", 0),
        high_correlation_pair_count=result.get("high_correlation_pair_count", 0),
        average_pairwise_correlation=result.get("average_pairwise_correlation"),
        max_pairwise_correlation=result.get("max_pairwise_correlation"),
        portfolio_drawdown_20d=result.get("portfolio_drawdown_20d"),
        portfolio_drawdown_60d=result.get("portfolio_drawdown_60d"),
        consecutive_loss_days=result.get("consecutive_loss_days", 0),
        dangerous_position_count=result.get("dangerous_position_count", 0),
        cautious_position_count=result.get("cautious_position_count", 0),
        unknown_position_count=result.get("unknown_position_count", 0),
        market_state=result.get("market_state", ""), sentiment_cycle=result.get("sentiment_cycle", ""),
        data_coverage_ratio=result.get("data_coverage_ratio", 0),
        risk_flags=result.get("risk_flags", []), recommendations=result.get("recommendations", []),
        observation_conditions=result.get("observation_conditions", []),
        risk_release_conditions=result.get("risk_release_conditions", []),
        issue_summary=result.get("issue_summary", []) if isinstance(result.get("issue_summary"), list) else [],
        data_quality_status=result.get("data_quality_status", "unknown"),
    )
    return save_portfolio_risk_snapshot(r)


def load_portfolio_risk_history(portfolio_name: str = "default", is_simulated: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    from src.portfolio.portfolio_risk_service import list_portfolio_risk_history
    return list_portfolio_risk_history(portfolio_name, is_simulated, limit)


def load_daily_portfolio_risks(trade_date: str, limit: int = 500) -> list[dict[str, Any]]:
    from src.portfolio.portfolio_risk_service import list_daily_portfolio_risks
    return list_daily_portfolio_risks(trade_date, limit)


def portfolio_risk_to_df(results: list[dict[str, Any]] | None) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    rows = []
    for r in results:
        rows.append({
            "trade_date": r.get("trade_date"), "portfolio_name": r.get("portfolio_name"),
            "持仓类型": "模拟" if r.get("is_simulated") else "真实",
            "risk_score": r.get("portfolio_risk_score"),
            "risk_level": risk_level_to_cn(r.get("portfolio_risk_level", "")),
            "permission": portfolio_permission_to_cn(r.get("portfolio_permission", "")),
            "position_count": r.get("position_count"),
            "total_pct": r.get("total_position_pct"),
            "max_single_pct": r.get("max_single_position_pct"),
            "max_sector_pct": r.get("max_sector_position_pct"),
            "avg_corr": r.get("average_pairwise_correlation"),
            "dd_60d": r.get("portfolio_drawdown_60d"),
            "loss_days": r.get("consecutive_loss_days"),
            "dangerous": r.get("dangerous_position_count"),
            "coverage": r.get("data_coverage_ratio"),
        })
    return pd.DataFrame(rows)


def risk_dimensions_to_df(result: dict[str, Any] | None) -> pd.DataFrame:
    if not result:
        return pd.DataFrame()
    dims = result.get("risk_dimensions", [])
    rows = []
    for d in dims:
        rows.append({
            "维度": d.get("name"), "风险分": d.get("risk_score"),
            "等级": d.get("risk_level"), "权重": d.get("weight"),
            "当前值": d.get("current_value"), "阈值": d.get("threshold"),
            "说明": d.get("reason"),
        })
    return pd.DataFrame(rows)


def sector_exposure_to_df(result: dict[str, Any] | None) -> pd.DataFrame:
    if not result:
        return pd.DataFrame()
    ses = result.get("sector_exposures", [])
    return pd.DataFrame([{
        "板块": se.get("sector_name"), "持仓数": se.get("position_count"),
        "仓位%": se.get("total_position_pct"), "集中度": se.get("concentration_level"),
    } for se in ses])


def correlation_pairs_to_df(result: dict[str, Any] | None) -> pd.DataFrame:
    if not result:
        return pd.DataFrame()
    cps = result.get("correlation_pairs", [])
    return pd.DataFrame([{
        "股票A": cp.get("stock_a"), "股票B": cp.get("stock_b"),
        "相关性": cp.get("correlation"), "风险": cp.get("risk_level"),
    } for cp in cps])


def risk_level_to_cn(level: str) -> str:
    return RISK_LEVEL_CN.get(level, level)


def portfolio_permission_to_cn(perm: str) -> str:
    return PERMISSION_CN.get(perm, perm)


def portfolio_risk_csv_bytes(results: list[dict[str, Any]] | None) -> bytes:
    df = portfolio_risk_to_df(results)
    if df.empty:
        return "\ufeff".encode("utf-8")
    return df.to_csv(index=False).encode("utf-8-sig")


def portfolio_risk_markdown_bytes(result: dict[str, Any] | None) -> bytes:
    if not result:
        return b""
    return build_portfolio_risk_markdown(result).encode("utf-8")


def all_portfolios_markdown_bytes(results: list[dict[str, Any]] | None, summary: dict[str, Any] | None = None) -> bytes:
    if not results:
        return b""
    return build_all_portfolios_risk_markdown(results, summary).encode("utf-8")
