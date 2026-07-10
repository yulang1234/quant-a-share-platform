"""V1.7.2 Streamlit-independent data helpers for position diagnosis view."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.portfolio.position_diagnosis_report import (
    build_daily_position_diagnosis_markdown,
    build_position_diagnosis_markdown,
)
from src.portfolio.position_diagnosis_types import (
    DIAGNOSIS_STATUS_CN,
    POSITION_SIZE_CN,
    SUGGESTED_ACTION_CN,
    THESIS_STATUS_CN,
)


def load_active_positions(
    portfolio_name: str | None = None,
    is_simulated: bool | None = None,
) -> list[dict[str, Any]]:
    """Load all active positions for diagnosis."""
    from ui.components.portfolio_position_view import load_positions

    return load_positions(
        portfolio_name=portfolio_name,
        status="active",
        is_simulated=is_simulated,
        limit=10000,
    )


def run_single_diagnosis(
    position_id: int, trade_date: str, persist: bool = False
) -> dict[str, Any]:
    """Run diagnosis on a single position."""
    from src.portfolio.position_diagnosis_service import diagnose_position

    result = diagnose_position(position_id, trade_date, persist=persist)
    return result.as_dict()


def run_batch_diagnosis(
    trade_date: str,
    portfolio_name: str | None = None,
    is_simulated: bool | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Run diagnosis on all active positions."""
    from src.portfolio.position_diagnosis_service import diagnose_all_active_positions

    return diagnose_all_active_positions(
        trade_date=trade_date,
        portfolio_name=portfolio_name,
        is_simulated=is_simulated,
        persist=persist,
    )


def save_diagnosis_from_ui(result: dict[str, Any]) -> dict[str, Any]:
    """Save a diagnosis result dict to SQLite."""
    from src.portfolio.position_diagnosis_service import (
        PositionDiagnosisResult,
        save_position_diagnosis,
    )

    # Reconstruct result object from dict
    r = PositionDiagnosisResult(
        position_id=result.get("position_id", 0),
        trade_date=result.get("trade_date", ""),
        portfolio_name=result.get("portfolio_name", ""),
        stock_code=result.get("stock_code", ""),
        stock_name=result.get("stock_name", ""),
        sector_name=result.get("sector_name", ""),
        diagnosis_status=result.get("diagnosis_status", "unknown"),
        suggested_action=result.get("suggested_action", "unknown"),
        thesis_status=result.get("thesis_status", "unknown"),
        health_score=result.get("health_score", 0),
        data_coverage_ratio=result.get("data_coverage_ratio", 0),
        market_support_score=result.get("market_support_score", 0),
        sentiment_support_score=result.get("sentiment_support_score", 0),
        sector_support_score=result.get("sector_support_score", 0),
        leader_support_score=result.get("leader_support_score", 0),
        trend_health_score=result.get("trend_health_score", 0),
        condition_support_score=result.get("condition_support_score", 0),
        thesis_score=result.get("thesis_score", 0),
        latest_close=result.get("latest_close"),
        unrealized_return_pct=result.get("unrealized_return_pct"),
        drawdown_20d=result.get("drawdown_20d"),
        position_pct=result.get("position_pct"),
        position_size_status=result.get("position_size_status", "unknown"),
        risk_warnings=result.get("risk_warnings", []),
        observation_conditions=result.get("observation_conditions", []),
        invalidation_conditions=result.get("invalidation_conditions", []),
        evidence=result.get("evidence", []),
        data_quality_status=result.get("data_quality_status", "unknown"),
        issue_summary=(
            result.get("issue_summary", [])
            if isinstance(result.get("issue_summary"), list)
            else []
        ),
    )
    return save_position_diagnosis(r)


def load_diagnosis_history(
    position_id: int, limit: int = 100
) -> list[dict[str, Any]]:
    """Load diagnosis history for a position."""
    from src.portfolio.position_diagnosis_service import get_diagnosis_history

    return get_diagnosis_history(position_id, limit=limit)


def load_daily_diagnoses(
    trade_date: str | None = None,
    portfolio_name: str | None = None,
    stock_code: str | None = None,
    diagnosis_status: str | None = None,
    suggested_action: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Load diagnoses with filters."""
    from src.portfolio.position_diagnosis_service import list_diagnoses

    return list_diagnoses(
        trade_date=trade_date,
        portfolio_name=portfolio_name,
        stock_code=stock_code,
        diagnosis_status=diagnosis_status,
        suggested_action=suggested_action,
        limit=limit,
    )


def diagnoses_to_df(results: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Convert diagnosis results to a display DataFrame."""
    if not results:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for r in results:
        rows.append({
            "trade_date": r.get("trade_date", ""),
            "position_id": r.get("position_id"),
            "portfolio_name": r.get("portfolio_name"),
            "stock_code": r.get("stock_code"),
            "stock_name": r.get("stock_name"),
            "sector_name": r.get("sector_name") or "—",
            "diagnosis_status": diagnosis_status_to_cn(
                r.get("diagnosis_status", "")
            ),
            "suggested_action": suggested_action_to_cn(
                r.get("suggested_action", "")
            ),
            "thesis_status": thesis_status_to_cn(r.get("thesis_status", "")),
            "health_score": r.get("health_score", 0),
            "market_support_score": r.get("market_support_score", 0),
            "sentiment_support_score": r.get("sentiment_support_score", 0),
            "sector_support_score": r.get("sector_support_score", 0),
            "leader_support_score": r.get("leader_support_score", 0),
            "trend_health_score": r.get("trend_health_score", 0),
            "condition_support_score": r.get("condition_support_score", 0),
            "thesis_score": r.get("thesis_score", 0),
            "latest_close": r.get("latest_close") or "—",
            "unrealized_return_pct": (
                f"{r.get('unrealized_return_pct'):+.2f}%"
                if r.get("unrealized_return_pct") is not None
                else "—"
            ),
            "drawdown_20d": (
                f"{r.get('drawdown_20d'):.1f}%"
                if r.get("drawdown_20d") is not None
                else "—"
            ),
            "position_pct": r.get("position_pct") or "—",
            "position_size_status": position_size_status_to_cn(
                r.get("position_size_status", "")
            ),
            "data_coverage_ratio": r.get("data_coverage_ratio", 0),
            "data_quality_status": r.get("data_quality_status", ""),
        })
    return pd.DataFrame(rows)


def diagnosis_summary(results: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Compute summary stats from a list of diagnosis results."""
    if not results:
        return {"total": 0}
    summary: dict[str, Any] = {"total": len(results)}
    for status in ("healthy", "watch", "cautious", "dangerous", "unknown"):
        summary[status] = sum(
            1 for r in results if r.get("diagnosis_status") == status
        )
    for action in (
        "continue_hold", "light_hold", "forbid_add",
        "reduce_conditionally", "exit_conditionally", "unknown",
    ):
        summary[f"action_{action}"] = sum(
            1 for r in results if r.get("suggested_action") == action
        )
    return summary


def diagnosis_status_to_cn(status: str) -> str:
    return DIAGNOSIS_STATUS_CN.get(status, status)


def suggested_action_to_cn(action: str) -> str:
    return SUGGESTED_ACTION_CN.get(action, action)


def thesis_status_to_cn(status: str) -> str:
    return THESIS_STATUS_CN.get(status, status)


def position_size_status_to_cn(status: str) -> str:
    return POSITION_SIZE_CN.get(status, status)


def diagnosis_csv_bytes(
    results: list[dict[str, Any]] | None,
) -> bytes:
    """Generate CSV bytes (utf-8-sig)."""
    df = diagnoses_to_df(results)
    if df.empty:
        return "\ufeff".encode("utf-8")
    return df.to_csv(index=False).encode("utf-8-sig")


def diagnosis_markdown_bytes(result: dict[str, Any] | None) -> bytes:
    """Single diagnosis Markdown bytes."""
    if not result:
        return b""
    md = build_position_diagnosis_markdown(result)
    return md.encode("utf-8")


def daily_diagnosis_markdown_bytes(
    results: list[dict[str, Any]] | None,
    summary: dict[str, Any] | None = None,
) -> bytes:
    """Daily summary Markdown bytes."""
    if not results:
        results = []
    md = build_daily_position_diagnosis_markdown(results, summary)
    return md.encode("utf-8")
