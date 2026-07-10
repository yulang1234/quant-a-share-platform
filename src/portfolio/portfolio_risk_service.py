"""V1.7.3 portfolio risk service — analyze position concentration, correlation,
drawdown, and market exposure at the portfolio level.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.portfolio.portfolio_risk_rules import (
    apply_hard_risk_overrides,
    build_portfolio_return_series,
    calculate_top_n_concentration,
    calculate_total_position_pct,
    classify_portfolio_permission,
    classify_risk_level,
    compute_portfolio_risk_score,
    evaluate_consecutive_loss_risk,
    evaluate_correlation_risk,
    evaluate_market_exposure_risk,
    evaluate_portfolio_drawdown_risk,
    evaluate_position_diagnosis_risk,
    evaluate_sector_concentration_risk,
    evaluate_single_position_risk,
    generate_risk_recommendations,
)
from src.portfolio.portfolio_risk_types import PortfolioRiskResult

logger = logging.getLogger(__name__)


def _load_active_positions(portfolio_name: str, is_simulated: bool) -> list[dict[str, Any]]:
    from src.repositories.portfolio_position_repo import PortfolioPositionRepository
    repo = PortfolioPositionRepository()
    pos_objs = repo.list_positions(portfolio_name=portfolio_name, status="active", is_simulated=is_simulated, limit=10000)
    from src.portfolio.position_service import _position_to_dict
    return [_position_to_dict(p) for p in pos_objs]


def build_portfolio_risk_context(
    trade_date: str,
    portfolio_name: str = "default",
    is_simulated: bool = False,
) -> dict[str, Any]:
    td = str(trade_date)[:10]
    issues: list[str] = []
    ctx: dict[str, Any] = {"trade_date": td, "portfolio_name": portfolio_name, "is_simulated": is_simulated}

    ctx["positions"] = _load_active_positions(portfolio_name, is_simulated)

    # Market & sentiment
    try:
        from src.market.market_environment import build_market_environment
        ctx["market"] = build_market_environment(td).as_dict()
    except Exception as exc:
        issues.append(f"市场环境: {exc}")
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        ctx["sentiment"] = build_sentiment_cycle(td).as_dict()
    except Exception as exc:
        issues.append(f"情绪周期: {exc}")

    # Diagnoses
    try:
        from src.portfolio.position_diagnosis_service import list_diagnoses
        ctx["diagnoses"] = list_diagnoses(trade_date=td)
    except Exception as exc:
        issues.append(f"持仓体检: {exc}")

    # Return series
    ctx["return_series"] = build_portfolio_return_series(ctx["positions"], td)

    ctx["issues"] = issues
    ctx["data_quality_status"] = "ok" if len(issues) <= 2 else "degraded"
    return ctx


def analyze_portfolio_risk(
    trade_date: str,
    portfolio_name: str = "default",
    is_simulated: bool = False,
    persist: bool = False,
) -> PortfolioRiskResult:
    td = str(trade_date)[:10]
    ctx = build_portfolio_risk_context(td, portfolio_name, is_simulated)
    positions = ctx["positions"]
    market = ctx.get("market")
    sentiment = ctx.get("sentiment")
    diagnoses = ctx.get("diagnoses", [])
    return_series = ctx.get("return_series", {})

    # Empty portfolio
    if not positions:
        return PortfolioRiskResult(
            trade_date=td, portfolio_name=portfolio_name, is_simulated=is_simulated,
            portfolio_risk_level="unknown", portfolio_permission="unknown",
            issue_summary=["该组合无 active 持仓"],
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )

    # Compute each dimension
    total = calculate_total_position_pct(positions)
    single_dim = evaluate_single_position_risk(positions)
    sector_result = evaluate_sector_concentration_risk(positions)
    sector_dim = sector_result["dimension"]
    market_dim = evaluate_market_exposure_risk(total["total_position_pct"], market, sentiment)
    corr_result = evaluate_correlation_risk(positions, td)
    corr_dim = corr_result["dimension"]
    dd_result = evaluate_portfolio_drawdown_risk(return_series)
    dd_dim = dd_result["dimension"]
    loss_dim = evaluate_consecutive_loss_risk(return_series)
    diag_dim = evaluate_position_diagnosis_risk(positions, td, diagnoses)

    dimensions = [single_dim, sector_dim, market_dim, corr_dim, dd_dim, loss_dim, diag_dim]
    risk_score, coverage = compute_portfolio_risk_score(dimensions)
    risk_level = classify_risk_level(risk_score, coverage)

    # Top3
    top3 = calculate_top_n_concentration(positions, 3)

    # Dangerous counts
    dangerous = sum(1 for d in diagnoses if d.get("diagnosis_status") == "dangerous")
    cautious = sum(1 for d in diagnoses if d.get("diagnosis_status") == "cautious")
    unknown_diag = sum(1 for d in diagnoses if d.get("diagnosis_status") == "unknown")

    result = PortfolioRiskResult(
        trade_date=td, portfolio_name=portfolio_name, is_simulated=is_simulated,
        portfolio_risk_score=risk_score, portfolio_risk_level=risk_level,
        position_count=len(positions),
        sector_count=sector_result["sector_count"],
        total_position_pct=total["total_position_pct"],
        cash_pct=total["cash_pct"],
        max_single_position_pct=single_dim.risk_score and (
            float(max(float(p.get("position_pct", 0) or 0) for p in positions))
        ) or 0,
        max_single_position_code=max(positions, key=lambda p: float(p.get("position_pct", 0) or 0)).get("stock_code", ""),
        max_sector_position_pct=sector_result["max_sector_pct"],
        max_sector_name=sector_result["max_sector_name"],
        top3_position_pct=top3,
        crowded_sector_count=sector_result["crowded_sector_count"],
        high_correlation_pair_count=corr_result["high_count"],
        average_pairwise_correlation=corr_result["average"],
        max_pairwise_correlation=corr_result["max"],
        portfolio_drawdown_20d=dd_result["dd_20d"],
        portfolio_drawdown_60d=dd_result["dd_60d"],
        consecutive_loss_days=int(loss_dim.current_value.replace("天", "")) if loss_dim.current_value else 0,
        dangerous_position_count=dangerous,
        cautious_position_count=cautious,
        unknown_position_count=unknown_diag,
        market_state=market.get("market_state", "unknown") if market else "unknown",
        sentiment_cycle=sentiment.get("sentiment_cycle", "unknown") if sentiment else "unknown",
        risk_dimensions=dimensions,
        sector_exposures=sector_result["sector_exposures"],
        correlation_pairs=corr_result["correlation_pairs"],
        data_coverage_ratio=coverage,
        data_quality_status=ctx.get("data_quality_status", "unknown"),
        issue_summary=ctx.get("issues", []) + total.get("issues", []),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )

    # Hard overrides
    result = apply_hard_risk_overrides(result)

    # Permission & recommendations
    result.portfolio_permission = classify_portfolio_permission(result)
    recs = generate_risk_recommendations(result)
    result.risk_flags = recs["risk_flags"]
    result.recommendations = recs["recommendations"]
    result.observation_conditions = recs["observation_conditions"]
    result.risk_release_conditions = recs["risk_release_conditions"]

    if persist:
        try:
            save_portfolio_risk_snapshot(result)
        except Exception as exc:
            result.issue_summary.append(f"保存失败: {exc}")

    return result


def analyze_all_portfolios(trade_date: str, persist: bool = False) -> dict[str, Any]:
    from src.repositories.portfolio_position_repo import PortfolioPositionRepository
    repo = PortfolioPositionRepository()
    all_positions = repo.list_positions(status="active", limit=10000)
    from src.portfolio.position_service import _position_to_dict
    pos_dicts = [_position_to_dict(p) for p in all_positions]

    # Group by (portfolio_name, is_simulated)
    groups: dict[tuple[str, bool], list[dict]] = {}
    for p in pos_dicts:
        key = (p.get("portfolio_name", "default"), p.get("is_simulated", True))
        groups.setdefault(key, []).append(p)

    results: list[dict] = []
    success = 0
    failed = 0
    for (pf_name, is_sim), _ in groups.items():
        try:
            r = analyze_portfolio_risk(trade_date, pf_name, is_sim, persist=persist)
            results.append(r.as_dict())
            success += 1
        except Exception as exc:
            failed += 1
            results.append({"portfolio_name": pf_name, "is_simulated": is_sim, "error": str(exc)})

    return {"results": results, "success_count": success, "failed_count": failed}


def save_portfolio_risk_snapshot(result: PortfolioRiskResult) -> dict[str, Any]:
    from src.repositories.portfolio_risk_repo import PortfolioRiskRepository
    repo = PortfolioRiskRepository()
    kwargs = _result_to_kwargs(result)
    snap = repo.upsert_snapshot(**kwargs)
    return {"risk_snapshot_id": snap.risk_snapshot_id}


def get_latest_portfolio_risk(portfolio_name: str = "default", is_simulated: bool = False) -> dict[str, Any] | None:
    from src.repositories.portfolio_risk_repo import PortfolioRiskRepository
    repo = PortfolioRiskRepository()
    snap = repo.get_latest(portfolio_name, is_simulated)
    return _snap_to_dict(snap) if snap else None


def list_portfolio_risk_history(portfolio_name: str = "default", is_simulated: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    from src.repositories.portfolio_risk_repo import PortfolioRiskRepository
    repo = PortfolioRiskRepository()
    snaps = repo.list_history(portfolio_name, is_simulated, limit)
    return [_snap_to_dict(s) for s in snaps]


def list_daily_portfolio_risks(trade_date: str, limit: int = 500) -> list[dict[str, Any]]:
    from src.repositories.portfolio_risk_repo import PortfolioRiskRepository
    repo = PortfolioRiskRepository()
    snaps = repo.list_daily_snapshots(trade_date, limit)
    return [_snap_to_dict(s) for s in snaps]


def _result_to_kwargs(r: PortfolioRiskResult) -> dict[str, Any]:
    return {
        "trade_date": r.trade_date, "portfolio_name": r.portfolio_name, "is_simulated": r.is_simulated,
        "portfolio_risk_score": r.portfolio_risk_score, "portfolio_risk_level": r.portfolio_risk_level,
        "portfolio_permission": r.portfolio_permission,
        "position_count": r.position_count, "sector_count": r.sector_count,
        "total_position_pct": r.total_position_pct, "cash_pct": r.cash_pct,
        "max_single_position_pct": r.max_single_position_pct,
        "max_single_position_code": r.max_single_position_code,
        "max_sector_position_pct": r.max_sector_position_pct,
        "max_sector_name": r.max_sector_name,
        "top3_position_pct": r.top3_position_pct,
        "crowded_sector_count": r.crowded_sector_count,
        "high_correlation_pair_count": r.high_correlation_pair_count,
        "average_pairwise_correlation": r.average_pairwise_correlation,
        "max_pairwise_correlation": r.max_pairwise_correlation,
        "portfolio_drawdown_20d": r.portfolio_drawdown_20d,
        "portfolio_drawdown_60d": r.portfolio_drawdown_60d,
        "consecutive_loss_days": r.consecutive_loss_days,
        "dangerous_position_count": r.dangerous_position_count,
        "cautious_position_count": r.cautious_position_count,
        "unknown_position_count": r.unknown_position_count,
        "market_state": r.market_state, "sentiment_cycle": r.sentiment_cycle,
        "market_exposure_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "market_exposure"), 0),
        "single_position_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "single_position"), 0),
        "sector_concentration_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "sector_concentration"), 0),
        "correlation_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "correlation"), 0),
        "drawdown_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "drawdown"), 0),
        "consecutive_loss_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "consecutive_loss"), 0),
        "diagnosis_risk_score": next((d.risk_score for d in r.risk_dimensions if d.name == "position_diagnosis"), 0),
        "data_coverage_ratio": r.data_coverage_ratio,
        "risk_flags_json": json.dumps(r.risk_flags, ensure_ascii=False),
        "recommendations_json": json.dumps(r.recommendations, ensure_ascii=False),
        "observation_conditions_json": json.dumps(r.observation_conditions, ensure_ascii=False),
        "risk_release_conditions_json": json.dumps(r.risk_release_conditions, ensure_ascii=False),
        "evidence_json": json.dumps(r.evidence, ensure_ascii=False),
        "issue_summary": "; ".join(r.issue_summary) if r.issue_summary else "",
        "data_quality_status": r.data_quality_status, "rule_version": r.rule_version,
    }


def _snap_to_dict(s: Any) -> dict[str, Any]:
    if s is None:
        return {}
    return {
        "risk_snapshot_id": s.risk_snapshot_id,
        "trade_date": s.trade_date.isoformat() if isinstance(s.trade_date, datetime.__class__) else str(s.trade_date)[:10],
        "portfolio_name": s.portfolio_name, "is_simulated": s.is_simulated,
        "portfolio_risk_score": s.portfolio_risk_score,
        "portfolio_risk_level": s.portfolio_risk_level,
        "portfolio_permission": s.portfolio_permission,
        "position_count": s.position_count, "total_position_pct": s.total_position_pct,
        "max_single_position_pct": s.max_single_position_pct,
        "max_sector_position_pct": s.max_sector_position_pct,
        "average_pairwise_correlation": s.average_pairwise_correlation,
        "portfolio_drawdown_60d": s.portfolio_drawdown_60d,
        "consecutive_loss_days": s.consecutive_loss_days,
        "dangerous_position_count": s.dangerous_position_count,
        "data_coverage_ratio": s.data_coverage_ratio,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
