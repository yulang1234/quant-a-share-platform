"""V1.7.2 position diagnosis service — evaluate active positions daily.

Assembles current market/sentiment/sector/leader/trend/condition context,
compares against entry snapshot, and produces a PositionDiagnosisResult.
No trading execution. No live pricing. No network calls.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import numpy as np

from src.portfolio.position_diagnosis_rules import (
    classify_health,
    classify_position_action,
    compute_position_health_score,
    evaluate_condition_support,
    evaluate_leader_support,
    evaluate_market_support,
    evaluate_position_size,
    evaluate_sector_support,
    evaluate_sentiment_support,
    evaluate_thesis_status,
    evaluate_trend_health,
)
from src.portfolio.position_diagnosis_types import (
    DiagnosisComponent,
    PositionDiagnosisResult,
    safe_float,
)
from src.portfolio.position_service import parse_snapshot_safe

logger = logging.getLogger(__name__)


# ── Context builder ──────────────────────────────────────────────────────────


def build_current_position_context(
    position: dict[str, Any],
    trade_date: str,
) -> dict[str, Any]:
    """Build all current context needed for diagnosis.

    Each module is wrapped individually; failure in one does not block others.
    """
    td = str(trade_date)[:10]
    stock_code = position.get("stock_code", "")
    sector_name = position.get("sector_name", "")
    issues: list[str] = []

    ctx: dict[str, Any] = {
        "trade_date": td,
        "stock_code": stock_code,
        "sector_name": sector_name,
    }

    # Market
    try:
        from src.market.market_environment import build_market_environment
        ctx["market"] = build_market_environment(td).as_dict()
    except Exception as exc:
        logger.warning("market context failed: %s", exc)
        issues.append(f"市场环境: {exc}")

    # Sentiment
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        ctx["sentiment"] = build_sentiment_cycle(td).as_dict()
    except Exception as exc:
        logger.warning("sentiment context failed: %s", exc)
        issues.append(f"情绪周期: {exc}")

    # Sector mainline
    if sector_name:
        try:
            from src.sector.sector_mainline import identify_sector_mainline
            ctx["sector_mainline"] = identify_sector_mainline(
                td, sector_name=sector_name
            ).as_dict()
        except Exception as exc:
            logger.warning("sector mainline failed for %s: %s", sector_name, exc)
            issues.append(f"板块主线: {exc}")

    # Leader
    if sector_name:
        try:
            from src.leader.sector_leader import identify_sector_leaders
            leaders = identify_sector_leaders(td, sector_name)
            if leaders.leader_1:
                ctx["leader"] = leaders.leader_1.as_dict()
        except Exception as exc:
            logger.warning("leader context failed for %s: %s", sector_name, exc)
            issues.append(f"龙头识别: {exc}")

    # Condition engine
    try:
        from src.conditions.condition_engine import build_condition_set

        market_d = ctx.get("market") or {}
        sentiment_d = ctx.get("sentiment") or {}
        sector_d = ctx.get("sector_mainline") or {}
        leader_d = ctx.get("leader") or {}
        opportunity_d = ctx.get("opportunity_index") or {}

        cs = build_condition_set(market_d, sentiment_d, sector_d, leader_d, opportunity_d)
        ctx["condition_set"] = cs.as_dict()
    except Exception as exc:
        logger.warning("condition engine failed: %s", exc)
        issues.append(f"条件引擎: {exc}")

    # Price context
    try:
        ctx["price"] = _fetch_price_context(stock_code, td)
    except Exception as exc:
        logger.warning("price context failed for %s: %s", stock_code, exc)
        issues.append(f"行情数据: {exc}")

    # Entry snapshot
    ctx["entry_snapshot"] = parse_snapshot_safe(
        position.get("entry_snapshot_json")
    )

    ctx["issues"] = issues
    ctx["data_quality_status"] = "ok" if len(issues) <= 2 else "degraded"

    return ctx


def _fetch_price_context(stock_code: str, trade_date: str) -> dict[str, Any] | None:
    """Fetch price context from local DuckDB.

    Uses stock_daily_raw for pricing; stock_daily_qfq for trend analysis
    if available, gracefully falling back to raw.
    """
    try:
        from src.storage.duckdb_repo import query_df

        # Latest close and recent data from raw
        df = query_df(
            "SELECT trade_date, close, pct_change, amount "
            "FROM stock_daily_raw WHERE stock_code = ? AND trade_date <= ? "
            "ORDER BY trade_date DESC LIMIT 30",
            [stock_code, trade_date],
        )
        if df is None or df.empty:
            return None

        df = df.sort_values("trade_date", ascending=True)
        closes = df["close"].astype(float).values
        pcts = df["pct_change"].dropna().astype(float)

        # Try qfq for trend
        try:
            df_qfq = query_df(
                "SELECT trade_date, close FROM stock_daily_qfq "
                "WHERE stock_code = ? AND trade_date <= ? "
                "ORDER BY trade_date DESC LIMIT 30",
                [stock_code, trade_date],
            )
            if df_qfq is not None and not df_qfq.empty:
                df_qfq = df_qfq.sort_values("trade_date", ascending=True)
                closes = df_qfq["close"].astype(float).values
        except Exception:
            pass  # graceful fallback to raw closes

        result: dict[str, Any] = {}
        if len(closes) > 0:
            result["close"] = float(closes[-1])

        # MA
        if len(closes) >= 5:
            result["ma5"] = round(float(np.mean(closes[-5:])), 2)
        if len(closes) >= 10:
            result["ma10"] = round(float(np.mean(closes[-10:])), 2)
        if len(closes) >= 20:
            result["ma20"] = round(float(np.mean(closes[-20:])), 2)

        # Returns
        if len(closes) >= 6:
            result["pct_chg_5d"] = round(
                (closes[-1] / closes[-6] - 1) * 100, 2
            )
        if len(closes) >= 21:
            result["pct_chg_20d"] = round(
                (closes[-1] / closes[-21] - 1) * 100, 2
            )

        # Drawdown
        if len(closes) >= 20:
            peak_20d = float(np.max(closes[-20:]))
            if peak_20d > 0:
                result["drawdown_20d"] = round(
                    (peak_20d - closes[-1]) / peak_20d * 100, 2
                )
            else:
                result["drawdown_20d"] = 0.0

        return result
    except Exception as exc:
        logger.warning("fetch_price_context error: %s", exc)
        return None


# ── Main diagnosis ───────────────────────────────────────────────────────────


def diagnose_position(
    position_id: int,
    trade_date: str,
    persist: bool = False,
) -> PositionDiagnosisResult:
    """Run a full diagnosis on a single active position.

    Args:
        position_id: The position to diagnose.
        trade_date: Trade date string YYYY-MM-DD.
        persist: If True, save result to SQLite.

    Returns:
        PositionDiagnosisResult with all scores and statuses.
    """
    td = str(trade_date)[:10]

    # 1. Load position
    from src.repositories.portfolio_position_repo import PortfolioPositionRepository

    pos_repo = PortfolioPositionRepository()
    pos_obj = pos_repo.get_by_id(position_id)
    if pos_obj is None:
        result = PositionDiagnosisResult(
            position_id=position_id, trade_date=td,
            diagnosis_status="unknown", suggested_action="unknown",
            thesis_status="unknown",
            issue_summary=[f"持仓 {position_id} 不存在"],
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )
        return result

    if pos_obj.status == "closed":
        result = PositionDiagnosisResult(
            position_id=position_id, trade_date=td,
            portfolio_name=pos_obj.portfolio_name,
            stock_code=pos_obj.stock_code,
            stock_name=pos_obj.stock_name,
            sector_name=pos_obj.sector_name,
            diagnosis_status="unknown", suggested_action="unknown",
            thesis_status="unknown",
            issue_summary=[f"持仓 {position_id} 已关闭，不进行正常体检"],
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )
        return result

    # 2. Convert ORM to dict
    from src.portfolio.position_service import _position_to_dict
    position = _position_to_dict(pos_obj)

    # 3. Build context
    ctx = build_current_position_context(position, td)

    # 4. Evaluate each component
    market_comp = evaluate_market_support(ctx.get("market"))
    sentiment_comp = evaluate_sentiment_support(ctx.get("sentiment"))
    sector_comp = evaluate_sector_support(
        ctx.get("sector_mainline"), ctx.get("entry_snapshot")
    )
    leader_comp = evaluate_leader_support(
        ctx.get("leader"), ctx.get("entry_snapshot")
    )
    trend_comp = evaluate_trend_health(ctx.get("price"))
    condition_comp = evaluate_condition_support(ctx.get("condition_set"))
    thesis_comp = evaluate_thesis_status(
        position, ctx.get("entry_snapshot"), ctx
    )

    components = [
        market_comp, sentiment_comp, sector_comp, leader_comp,
        trend_comp, condition_comp, thesis_comp,
    ]

    # 5. Compute health score
    health_score, coverage = compute_position_health_score(components)

    # 6. Position size
    pct = safe_float(position.get("position_pct"))
    size_status, size_reason = evaluate_position_size(pct)

    # 7. Floating return
    price_ctx = ctx.get("price") or {}
    latest_close = safe_float(price_ctx.get("close")) if price_ctx else None
    avg_cost = safe_float(position.get("avg_cost"))
    unrealized: float | None = None
    if latest_close and avg_cost > 0:
        unrealized = round((latest_close / avg_cost - 1) * 100, 2)

    # 8. Drawdown
    dd_20 = safe_float(price_ctx.get("drawdown_20d")) if price_ctx else None

    # 9. Build result
    result = PositionDiagnosisResult(
        position_id=position_id,
        trade_date=td,
        portfolio_name=position.get("portfolio_name", ""),
        stock_code=position.get("stock_code", ""),
        stock_name=position.get("stock_name", ""),
        sector_name=position.get("sector_name") or "",
        diagnosis_status=classify_health(health_score, coverage),
        thesis_status=thesis_comp.status,
        health_score=health_score,
        data_coverage_ratio=coverage,
        market_support_score=market_comp.score,
        sentiment_support_score=sentiment_comp.score,
        sector_support_score=sector_comp.score,
        leader_support_score=leader_comp.score,
        trend_health_score=trend_comp.score,
        condition_support_score=condition_comp.score,
        thesis_score=thesis_comp.score,
        market_component=market_comp,
        sentiment_component=sentiment_comp,
        sector_component=sector_comp,
        leader_component=leader_comp,
        trend_component=trend_comp,
        condition_component=condition_comp,
        thesis_component=thesis_comp,
        latest_close=latest_close,
        unrealized_return_pct=unrealized,
        drawdown_20d=dd_20,
        position_pct=pct if pct != 0 else None,
        position_size_status=size_status,
        risk_warnings=_collect_warnings(components),
        observation_conditions=_collect_observations(ctx.get("condition_set")),
        invalidation_conditions=_collect_invalidations(ctx.get("condition_set")),
        evidence=_collect_evidence(components),
        data_quality_status=ctx.get("data_quality_status", "unknown"),
        issue_summary=ctx.get("issues", []),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )

    # 10. Classify action
    result.suggested_action = classify_position_action(result)

    # 11. Persist if requested
    if persist:
        try:
            save_position_diagnosis(result)
        except Exception as exc:
            result.issue_summary.append(f"保存失败: {exc}")

    return result


def diagnose_all_active_positions(
    trade_date: str,
    portfolio_name: str | None = None,
    is_simulated: bool | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Run diagnosis on all active positions.

    Returns:
        dict with keys: results (list), success_count, failed_count, issues.
    """
    from src.repositories.portfolio_position_repo import PortfolioPositionRepository

    repo = PortfolioPositionRepository()
    positions = repo.list_positions(
        portfolio_name=portfolio_name,
        status="active",
        is_simulated=is_simulated,
        limit=10000,
    )

    results: list[PositionDiagnosisResult] = []
    success_count = 0
    failed_count = 0
    issues: list[str] = []

    for pos in positions:
        try:
            result = diagnose_position(
                pos.position_id, trade_date, persist=persist
            )
            results.append(result)
            if result.diagnosis_status != "unknown" or "不存在" not in " ".join(
                result.issue_summary
            ):
                success_count += 1
        except Exception as exc:
            failed_count += 1
            issues.append(f"position_id={pos.position_id}: {exc}")

    return {
        "results": [r.as_dict() for r in results],
        "success_count": success_count,
        "failed_count": failed_count,
        "issues": issues,
    }


# ── Persistence ──────────────────────────────────────────────────────────────


def save_position_diagnosis(result: PositionDiagnosisResult) -> dict[str, Any]:
    """Save a diagnosis result to SQLite (upsert)."""
    from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

    repo = PositionDiagnosisRepository()
    kwargs = _result_to_kwargs(result)
    diag = repo.upsert_diagnosis(**kwargs)
    return {"diagnosis_id": diag.diagnosis_id, "position_id": diag.position_id}


def get_latest_diagnosis(position_id: int) -> dict[str, Any] | None:
    """Get the latest diagnosis for a position."""
    from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

    repo = PositionDiagnosisRepository()
    diag = repo.get_latest_by_position(position_id)
    if diag is None:
        return None
    return _diag_to_dict(diag)


def list_diagnoses(
    trade_date: str | None = None,
    portfolio_name: str | None = None,
    stock_code: str | None = None,
    diagnosis_status: str | None = None,
    suggested_action: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """List diagnoses with filters."""
    from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

    repo = PositionDiagnosisRepository()
    diags = repo.list_diagnoses(
        trade_date=trade_date,
        portfolio_name=portfolio_name,
        stock_code=stock_code,
        diagnosis_status=diagnosis_status,
        suggested_action=suggested_action,
        limit=limit,
    )
    return [_diag_to_dict(d) for d in diags]


def get_diagnosis_history(position_id: int, limit: int = 100) -> list[dict[str, Any]]:
    """List diagnosis history for a position."""
    from src.repositories.position_diagnosis_repo import PositionDiagnosisRepository

    repo = PositionDiagnosisRepository()
    diags = repo.list_history(position_id, limit=limit)
    return [_diag_to_dict(d) for d in diags]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _result_to_kwargs(result: PositionDiagnosisResult) -> dict[str, Any]:
    """Convert PositionDiagnosisResult to kwargs for ORM upsert."""
    import json

    return {
        "position_id": result.position_id,
        "trade_date": result.trade_date,
        "portfolio_name": result.portfolio_name,
        "stock_code": result.stock_code,
        "stock_name": result.stock_name,
        "sector_name": result.sector_name,
        "diagnosis_status": result.diagnosis_status,
        "suggested_action": result.suggested_action,
        "thesis_status": result.thesis_status,
        "market_support_score": result.market_support_score,
        "sentiment_support_score": result.sentiment_support_score,
        "sector_support_score": result.sector_support_score,
        "leader_support_score": result.leader_support_score,
        "trend_health_score": result.trend_health_score,
        "condition_support_score": result.condition_support_score,
        "thesis_score": result.thesis_score,
        "health_score": result.health_score,
        "data_coverage_ratio": result.data_coverage_ratio,
        "latest_close": result.latest_close,
        "unrealized_return_pct": result.unrealized_return_pct,
        "drawdown_20d": result.drawdown_20d,
        "position_pct": result.position_pct,
        "position_size_status": result.position_size_status,
        "reason_summary": "; ".join(result.risk_warnings[:3]) if result.risk_warnings else "",
        "risk_warnings_json": json.dumps(result.risk_warnings, ensure_ascii=False),
        "observation_conditions_json": json.dumps(
            result.observation_conditions, ensure_ascii=False
        ),
        "invalidation_conditions_json": json.dumps(
            result.invalidation_conditions, ensure_ascii=False
        ),
        "evidence_json": json.dumps(result.evidence, ensure_ascii=False),
        "current_context_json": "{}",
        "data_quality_status": result.data_quality_status,
        "issue_summary": "; ".join(result.issue_summary) if result.issue_summary else "",
        "rule_version": result.rule_version,
    }


def _diag_to_dict(diag: Any) -> dict[str, Any]:
    """Convert ORM object to dict."""
    if diag is None:
        return {}
    import json

    return {
        "diagnosis_id": diag.diagnosis_id,
        "position_id": diag.position_id,
        "trade_date": (
            diag.trade_date.isoformat()
            if isinstance(diag.trade_date, date)
            else str(diag.trade_date)[:10]
        ),
        "portfolio_name": diag.portfolio_name,
        "stock_code": diag.stock_code,
        "stock_name": diag.stock_name,
        "sector_name": diag.sector_name,
        "diagnosis_status": diag.diagnosis_status,
        "suggested_action": diag.suggested_action,
        "thesis_status": diag.thesis_status,
        "market_support_score": diag.market_support_score,
        "sentiment_support_score": diag.sentiment_support_score,
        "sector_support_score": diag.sector_support_score,
        "leader_support_score": diag.leader_support_score,
        "trend_health_score": diag.trend_health_score,
        "condition_support_score": diag.condition_support_score,
        "thesis_score": diag.thesis_score,
        "health_score": diag.health_score,
        "data_coverage_ratio": diag.data_coverage_ratio,
        "latest_close": diag.latest_close,
        "unrealized_return_pct": diag.unrealized_return_pct,
        "drawdown_20d": diag.drawdown_20d,
        "position_pct": diag.position_pct,
        "position_size_status": diag.position_size_status,
        "reason_summary": diag.reason_summary,
        "risk_warnings_json": diag.risk_warnings_json,
        "observation_conditions_json": diag.observation_conditions_json,
        "invalidation_conditions_json": diag.invalidation_conditions_json,
        "evidence_json": diag.evidence_json,
        "data_quality_status": diag.data_quality_status,
        "issue_summary": diag.issue_summary,
        "rule_version": diag.rule_version,
        "created_at": diag.created_at.isoformat() if diag.created_at else None,
        "updated_at": diag.updated_at.isoformat() if diag.updated_at else None,
    }


def _collect_warnings(components: list[DiagnosisComponent]) -> list[str]:
    warnings: list[str] = []
    for comp in components:
        if comp.issues:
            warnings.extend(comp.issues)
        if comp.reason and comp.score < 40:
            warnings.append(f"[{comp.name}] {comp.reason}")
    return warnings or ["暂无严重风险提示"]


def _collect_observations(condition_set: dict[str, Any] | None) -> list[str]:
    if not condition_set:
        return []
    obs = condition_set.get("observation_conditions") or []
    return [c.get("name", "") for c in obs if c.get("status") == "not_satisfied"]


def _collect_invalidations(condition_set: dict[str, Any] | None) -> list[str]:
    if not condition_set:
        return []
    inv = condition_set.get("invalidation_conditions") or []
    return [c.get("name", "") for c in inv if c.get("status") == "satisfied"]


def _collect_evidence(components: list[DiagnosisComponent]) -> list[str]:
    evidence: list[str] = []
    for comp in components:
        for e in comp.evidence:
            if e not in evidence:
                evidence.append(e)
    return evidence
