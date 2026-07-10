"""V1.7.1 Streamlit-independent data helpers for portfolio position view.

All functions here are pure data transformations — no streamlit imports.
They can be unit-tested without a browser.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.portfolio.position_report import (
    build_position_detail_markdown,
    build_position_list_markdown,
)
from src.portfolio.position_types import (
    POSITION_MODE_CN,
    POSITION_STATUS_CN,
    PositionSummary,
)


def load_positions(
    portfolio_name: str | None = None,
    status: str | None = None,
    is_simulated: bool | None = None,
    stock_code: str | None = None,
    sector_name: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Load positions from service layer."""
    from src.portfolio.position_service import list_positions

    return list_positions(
        portfolio_name=portfolio_name,
        status=status,
        is_simulated=is_simulated,
        stock_code=stock_code,
        sector_name=sector_name,
        limit=limit,
    )


def load_position(position_id: int) -> dict[str, Any] | None:
    """Load a single position by ID."""
    from src.portfolio.position_service import get_position

    return get_position(position_id)


def create_position_from_form(form_data: dict[str, Any]) -> dict[str, Any]:
    """Create a position from form data. Raises on validation error."""
    from src.portfolio.position_service import create_position

    return create_position(form_data)


def update_position_from_form(
    position_id: int, form_data: dict[str, Any]
) -> dict[str, Any]:
    """Update a position from form data. Raises on validation error."""
    from src.portfolio.position_service import update_position

    return update_position(position_id, form_data)


def close_position_from_ui(position_id: int) -> dict[str, Any]:
    """Close a position (no physical delete)."""
    from src.portfolio.position_service import close_position

    return close_position(position_id)


def positions_to_df(positions: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Convert a list of position dicts to a DataFrame for display."""
    if not positions:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for p in positions:
        rows.append({
            "position_id": p.get("position_id"),
            "portfolio_name": p.get("portfolio_name"),
            "持仓类型": position_mode_to_cn(p.get("is_simulated", True)),
            "stock_code": p.get("stock_code"),
            "stock_name": p.get("stock_name"),
            "exchange": p.get("exchange"),
            "buy_date": p.get("buy_date"),
            "avg_cost": p.get("avg_cost"),
            "quantity": p.get("quantity") if p.get("quantity") is not None else "—",
            "position_pct": p.get("position_pct"),
            "sector_name": p.get("sector_name") or "—",
            "original_strategy": p.get("original_strategy") or "—",
            "status": position_status_to_cn(p.get("status", "active")),
            "has_snapshot": "有快照" if p.get("entry_snapshot_json") else "无快照",
            "updated_at": (p.get("updated_at") or "")[:19],
        })
    return pd.DataFrame(rows)


def position_summary(
    portfolio_name: str | None = None,
    is_simulated: bool | None = None,
) -> dict[str, Any]:
    """Get position summary as a dict."""
    from src.portfolio.position_service import get_position_summary

    s: PositionSummary = get_position_summary(
        portfolio_name=portfolio_name,
        is_simulated=is_simulated,
    )
    return {
        "total_count": s.total_count,
        "active_count": s.active_count,
        "closed_count": s.closed_count,
        "real_count": s.real_count,
        "simulated_count": s.simulated_count,
        "total_position_pct": s.total_position_pct,
        "position_pct_ok": s.position_pct_ok,
    }


def position_mode_to_cn(is_simulated: bool) -> str:
    """Convert boolean mode to Chinese label."""
    return POSITION_MODE_CN.get(
        "simulated" if is_simulated else "real", str(is_simulated)
    )


def position_status_to_cn(status: str) -> str:
    """Convert status string to Chinese label."""
    return POSITION_STATUS_CN.get(status, status)


def position_csv_bytes(
    positions: list[dict[str, Any]] | None, include_snapshot: bool = False
) -> bytes:
    """Generate CSV bytes (utf-8-sig) for a list of positions."""
    df = positions_to_df(positions)
    if df.empty:
        return "\ufeff".encode("utf-8")
    if include_snapshot and positions:
        df["entry_snapshot_json"] = [
            (p.get("entry_snapshot_json") or "") for p in positions
        ]
    return df.to_csv(index=False).encode("utf-8-sig")


def position_markdown_bytes(
    positions: list[dict[str, Any]] | None, summary: dict[str, Any] | None = None
) -> bytes:
    """Generate Markdown bytes for position list."""
    if not positions:
        positions = []
    md = build_position_list_markdown(positions, summary)
    return md.encode("utf-8")


def position_detail_markdown_bytes(position: dict[str, Any] | None) -> bytes:
    """Generate Markdown bytes for single position detail."""
    if not position:
        return "".encode("utf-8")
    md = build_position_detail_markdown(position)
    return md.encode("utf-8")


def position_snapshot_as_markdown(position: dict[str, Any] | None) -> str:
    """Return the snapshot JSON as a pretty-printed Markdown code block, or empty."""
    if not position:
        return ""
    snapshot_json = position.get("entry_snapshot_json", "")
    if not snapshot_json:
        return ""
    try:
        obj = json.loads(snapshot_json)
        pretty = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        return f"```json\n{pretty}\n```"
    except Exception:
        return f"```\n{snapshot_json[:500]}\n```"
