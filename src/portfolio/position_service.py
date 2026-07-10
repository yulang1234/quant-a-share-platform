"""V1.7.1 position service — validation, enrichment, snapshot, and persistence.

Orchestrates the full lifecycle of a position:
- input validation & normalization
- security-master auto-completion
- sector auto-completion
- optional V1.6 entry snapshot
- delegating to PortfolioPositionRepository
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any

from src.portfolio.position_types import (
    PositionCreateInput,
    PositionSummary,
    PositionUpdateInput,
    PositionValidationError,
)
from src.repositories.portfolio_position_repo import PortfolioPositionRepository

logger = logging.getLogger(__name__)

_STOCK_CODE_RE = re.compile(r"^\d{6}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Normalization ─────────────────────────────────────────────────────────────


def normalize_stock_code(raw: str) -> str:
    """Normalize a stock code to 6-digit zero-padded string.

    Raises:
        PositionValidationError: if the code contains non-digit characters.
    """
    code = (raw or "").strip()
    if not code:
        raise PositionValidationError("股票代码不能为空", field="stock_code")
    if not code.isdigit():
        raise PositionValidationError(
            f"股票代码包含非法字符: {code}", field="stock_code"
        )
    if len(code) > 6:
        raise PositionValidationError(
            f"股票代码过长: {code}", field="stock_code"
        )
    return code.zfill(6)


# ── Validation ────────────────────────────────────────────────────────────────


def validate_position_input(data: dict[str, Any]) -> None:
    """Validate position input data. Raises PositionValidationError on failure."""
    # stock_code
    code = data.get("stock_code", "")
    normalized = normalize_stock_code(code)
    data["stock_code"] = normalized

    # buy_date
    buy_date = data.get("buy_date", "")
    if not _DATE_RE.match(str(buy_date)):
        raise PositionValidationError(
            f"买入日期格式错误，需要 YYYY-MM-DD: {buy_date}", field="buy_date"
        )

    # avg_cost
    avg_cost = data.get("avg_cost", 0)
    if not isinstance(avg_cost, (int, float)) or float(avg_cost) <= 0:
        raise PositionValidationError(
            f"平均成本必须大于0: {avg_cost}", field="avg_cost"
        )

    # quantity
    quantity = data.get("quantity")
    if quantity is not None:
        if not isinstance(quantity, (int, float)) or float(quantity) < 0:
            raise PositionValidationError(
                f"持仓数量不能小于0: {quantity}", field="quantity"
            )

    # position_pct
    pct = data.get("position_pct", 0)
    if not isinstance(pct, (int, float)) or float(pct) < 0 or float(pct) > 100:
        raise PositionValidationError(
            f"仓位百分比必须在0~100之间: {pct}", field="position_pct"
        )

    # buy_reason
    reason = str(data.get("buy_reason", "")).strip()
    if not reason:
        raise PositionValidationError("买入理由不能为空", field="buy_reason")
    data["buy_reason"] = reason

    # exchange
    exchange = str(data.get("exchange", "")).strip().upper()
    if exchange not in ("SH", "SZ", "BJ"):
        raise PositionValidationError(
            f"交易所必须为 SH/SZ/BJ: {exchange}", field="exchange"
        )
    data["exchange"] = exchange

    # stock_name
    stock_name = str(data.get("stock_name", "")).strip()
    if not stock_name:
        raise PositionValidationError("股票名称不能为空", field="stock_name")
    data["stock_name"] = stock_name

    # status (if provided)
    status = data.get("status", "active")
    if status not in ("active", "closed"):
        raise PositionValidationError(
            f"持仓状态无效: {status}", field="status"
        )

    # string length checks
    portfolio_name = str(data.get("portfolio_name", "default")).strip()
    if len(portfolio_name) > 64:
        raise PositionValidationError("组合名称过长（最多64字符）", field="portfolio_name")
    data["portfolio_name"] = portfolio_name or "default"

    if len(stock_name) > 64:
        raise PositionValidationError("股票名称过长（最多64字符）", field="stock_name")

    sector_name = data.get("sector_name")
    if sector_name and len(str(sector_name)) > 128:
        raise PositionValidationError("板块名称过长（最多128字符）", field="sector_name")

    strategy = data.get("original_strategy")
    if strategy and len(str(strategy)) > 128:
        raise PositionValidationError("原始策略名称过长（最多128字符）", field="original_strategy")


# ── Auto-completion ───────────────────────────────────────────────────────────


def resolve_security_info(
    stock_code: str,
    exchange: str | None = None,
    stock_name: str | None = None,
) -> dict[str, str | None]:
    """Resolve exchange and stock_name from security_master if missing.

    Returns:
        dict with keys: exchange, stock_name, resolution_issue.
        resolution_issue is None when everything resolved cleanly.
    """
    result: dict[str, str | None] = {
        "exchange": (exchange or "").upper() if exchange else None,
        "stock_name": stock_name or None,
        "resolution_issue": None,
    }
    issues: list[str] = []

    try:
        from src.repositories.security_master_repo import SecurityMasterRepository

        repo = SecurityMasterRepository()
        # Try all three exchanges
        for ex in ("SH", "SZ", "BJ"):
            sec = repo.find_by_symbol(stock_code, ex)
            if sec:
                if not result["exchange"]:
                    result["exchange"] = sec.exchange
                if not result["stock_name"]:
                    result["stock_name"] = sec.security_name or stock_code
                return result

        # Not found in any exchange
        if not result["exchange"]:
            issues.append(f"security_master 未找到 {stock_code}，需手动输入交易所")
        if not result["stock_name"]:
            issues.append(f"security_master 未找到 {stock_code}，需手动输入股票名称")

    except Exception as exc:
        logger.warning("security_master lookup failed for %s: %s", stock_code, exc)
        issues.append(f"security_master 查询异常: {exc}")

    if issues:
        result["resolution_issue"] = "; ".join(issues)
    return result


def resolve_sector_name(
    stock_code: str, sector_name: str | None = None
) -> dict[str, str | None]:
    """Resolve sector name from local stock_sector_map.

    Returns:
        dict with keys: sector_name, sector_issue.
    """
    result: dict[str, str | None] = {
        "sector_name": sector_name or None,
        "sector_issue": None,
    }

    # User input takes priority
    if sector_name:
        return result

    try:
        from src.sector.sector_service import get_sectors_by_stock

        sectors_result = get_sectors_by_stock(stock_code)
        if sectors_result and sectors_result.sectors and not sectors_result.missing:
            # Pick the first sector
            first = sectors_result.sectors[0]
            result["sector_name"] = first.get("sector_name", "")
            return result

        result["sector_issue"] = f"本地板块映射中未找到 {stock_code} 的板块信息"
    except Exception as exc:
        logger.warning("sector resolution failed for %s: %s", stock_code, exc)
        result["sector_issue"] = f"板块查询异常: {exc}"

    return result


# ── Snapshot ──────────────────────────────────────────────────────────────────


def build_entry_snapshot(
    trade_date: str,
    sector_name: str | None,
    stock_code: str,
) -> dict[str, Any]:
    """Build an optional V1.6 entry snapshot from local modules.

    Returns:
        dict with keys:
        - snapshot_json: str | None
        - snapshot_version: str | None
        - snapshot_issue: str | None
    """
    result: dict[str, Any] = {
        "snapshot_json": None,
        "snapshot_version": "v1.6.3",
        "snapshot_issue": None,
    }
    issues: list[str] = []
    snapshot: dict[str, Any] = {
        "trade_date": trade_date,
        "sector_name": sector_name,
        "stock_code": stock_code,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": "v1.6.3",
    }

    # Market environment
    try:
        from src.market.market_environment import build_market_environment

        market = build_market_environment(trade_date)
        snapshot["market_environment"] = market.as_dict()
    except Exception as exc:
        issues.append(f"市场环境快照失败: {exc}")

    # Sentiment cycle
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle

        sentiment = build_sentiment_cycle(trade_date)
        snapshot["sentiment_cycle"] = sentiment.as_dict()
    except Exception as exc:
        issues.append(f"情绪周期快照失败: {exc}")

    # Sector mainline (only if we have sector_name)
    if sector_name:
        try:
            from src.sector.sector_mainline import identify_sector_mainline

            mainline = identify_sector_mainline(trade_date, sector_name=sector_name)
            snapshot["sector_mainline"] = mainline.as_dict()
        except Exception as exc:
            issues.append(f"板块主线快照失败: {exc}")

    # Leader identification
    if sector_name:
        try:
            from src.leader.sector_leader import identify_sector_leaders

            leaders = identify_sector_leaders(trade_date, sector_name)
            snapshot["sector_leaders"] = leaders.as_dict()
        except Exception as exc:
            issues.append(f"龙头识别快照失败: {exc}")

    # Opportunity index
    if sector_name:
        try:
            from src.opportunity.opportunity_index import build_opportunity_index

            opp = build_opportunity_index(trade_date, sector_name, stock_code)
            snapshot["opportunity_index"] = opp.as_dict()
        except Exception as exc:
            issues.append(f"机会指数快照失败: {exc}")

    # Condition engine
    try:
        from src.conditions.condition_engine import build_condition_set

        market_d = snapshot.get("market_environment") or {}
        sentiment_d = snapshot.get("sentiment_cycle") or {}
        sector_d = snapshot.get("sector_mainline") or {}
        leader_d = (snapshot.get("sector_leaders") or {}).get("leader_1")
        opp_d = snapshot.get("opportunity_index") or {}

        cs = build_condition_set(market_d, sentiment_d, sector_d, leader_d, opp_d)
        snapshot["condition_set"] = cs.as_dict()
    except Exception as exc:
        issues.append(f"条件引擎快照失败: {exc}")

    # Serialize
    try:
        result["snapshot_json"] = json.dumps(snapshot, ensure_ascii=False, default=str)
    except Exception as exc:
        issues.append(f"快照JSON序列化失败: {exc}")

    if issues:
        result["snapshot_issue"] = "; ".join(issues)

    return result


def parse_snapshot_safe(snapshot_json: str | None) -> dict[str, Any]:
    """Safely parse an entry_snapshot_json string.

    Returns an empty dict on any parse error — never raises.
    """
    if not snapshot_json:
        return {}
    try:
        return json.loads(snapshot_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Failed to parse entry_snapshot_json: %s", exc)
        return {"parse_error": str(exc), "raw_preview": str(snapshot_json)[:200]}


# ── Main service functions ────────────────────────────────────────────────────


def create_position(data: dict[str, Any]) -> dict[str, Any]:
    """Validate, enrich and create a position.

    Args:
        data: Raw form data from UI or API.

    Returns:
        dict with keys: position (as dict), issues (list[str]), snapshot_issue (str|None).
    """
    issues: list[str] = []

    # 1. Validate input
    validate_position_input(data)

    stock_code = data["stock_code"]
    exchange = data.get("exchange", "")
    stock_name = data.get("stock_name", "")
    sector_name_input = data.get("sector_name")

    # 2. Resolve security info
    sec_info = resolve_security_info(stock_code, exchange, stock_name)
    if sec_info["resolution_issue"]:
        issues.append(sec_info["resolution_issue"])
    if sec_info["exchange"]:
        data["exchange"] = sec_info["exchange"]
    if sec_info["stock_name"]:
        data["stock_name"] = sec_info["stock_name"]

    # 3. Resolve sector
    sector_info = resolve_sector_name(stock_code, sector_name_input)
    if sector_info["sector_issue"]:
        issues.append(sector_info["sector_issue"])
    if sector_info["sector_name"]:
        data["sector_name"] = sector_info["sector_name"]

    # 4. Optional snapshot
    capture = data.pop("capture_entry_snapshot", False)
    snapshot_issue: str | None = None
    entry_snapshot_json: str | None = None
    snapshot_version: str | None = None

    if capture:
        snap = build_entry_snapshot(
            trade_date=data.get("buy_date", ""),
            sector_name=data.get("sector_name"),
            stock_code=stock_code,
        )
        entry_snapshot_json = snap["snapshot_json"]
        snapshot_version = snap["snapshot_version"]
        snapshot_issue = snap["snapshot_issue"]
        if snapshot_issue:
            issues.append(f"建仓快照部分失败: {snapshot_issue}")

    data["entry_snapshot_json"] = entry_snapshot_json
    data["snapshot_version"] = snapshot_version

    # 5. Persist
    repo = PortfolioPositionRepository()
    try:
        position = repo.create_position(**data)
    except Exception as exc:
        raise PositionValidationError(
            f"保存持仓失败: {exc}", field="__db__"
        ) from exc

    return {
        "position": _position_to_dict(position),
        "issues": issues,
        "snapshot_issue": snapshot_issue,
    }


def update_position(position_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Validate update input and apply changes.

    Returns:
        dict with keys: position (as dict), issues (list[str]).
    """
    # Build clean update dict
    changes: dict[str, Any] = {}
    for key in ("portfolio_name", "stock_name", "avg_cost", "quantity",
                 "position_pct", "buy_reason", "sector_name",
                 "original_strategy", "user_note"):
        if key in data and data[key] is not None:
            changes[key] = data[key]

    # Validate relevant fields
    if "avg_cost" in changes and float(changes["avg_cost"]) <= 0:
        raise PositionValidationError("平均成本必须大于0", field="avg_cost")
    if "quantity" in changes:
        q = changes["quantity"]
        if q is not None and (not isinstance(q, (int, float)) or float(q) < 0):
            raise PositionValidationError("持仓数量不能小于0", field="quantity")
    if "position_pct" in changes:
        pct = float(changes["position_pct"])
        if pct < 0 or pct > 100:
            raise PositionValidationError("仓位百分比必须在0~100之间", field="position_pct")
    if "buy_reason" in changes and not str(changes["buy_reason"]).strip():
        raise PositionValidationError("买入理由不能为空", field="buy_reason")

    repo = PortfolioPositionRepository()
    position = repo.update_position(position_id, **changes)
    return {
        "position": _position_to_dict(position),
        "issues": [],
    }


def close_position(position_id: int) -> dict[str, Any]:
    """Close a position (status=closed, preserve data)."""
    repo = PortfolioPositionRepository()
    position = repo.close_position(position_id)
    return {"position": _position_to_dict(position)}


def get_position(position_id: int) -> dict[str, Any] | None:
    """Get a single position by ID."""
    repo = PortfolioPositionRepository()
    pos = repo.get_by_id(position_id)
    return _position_to_dict(pos) if pos else None


def list_positions(
    portfolio_name: str | None = None,
    status: str | None = None,
    is_simulated: bool | None = None,
    stock_code: str | None = None,
    sector_name: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """List positions with filters."""
    repo = PortfolioPositionRepository()
    positions = repo.list_positions(
        portfolio_name=portfolio_name,
        status=status,
        is_simulated=is_simulated,
        stock_code=stock_code,
        sector_name=sector_name,
        limit=limit,
    )
    return [_position_to_dict(p) for p in positions]


def get_position_summary(
    portfolio_name: str | None = None,
    is_simulated: bool | None = None,
) -> PositionSummary:
    """Get aggregated summary."""
    repo = PortfolioPositionRepository()
    return repo.build_summary(
        portfolio_name=portfolio_name,
        is_simulated=is_simulated,
    )


def get_entry_snapshot(position_id: int) -> dict[str, Any]:
    """Get the parsed entry snapshot for a position."""
    repo = PortfolioPositionRepository()
    pos = repo.get_by_id(position_id)
    if pos is None:
        return {}
    return parse_snapshot_safe(pos.entry_snapshot_json)


# ── Helper ────────────────────────────────────────────────────────────────────


def _position_to_dict(pos: Any) -> dict[str, Any]:
    """Convert a PortfolioPosition ORM object to a plain dict."""
    if pos is None:
        return {}
    return {
        "position_id": pos.position_id,
        "portfolio_name": pos.portfolio_name,
        "stock_code": pos.stock_code,
        "exchange": pos.exchange,
        "stock_name": pos.stock_name,
        "buy_date": (
            pos.buy_date.strftime("%Y-%m-%d")
            if isinstance(pos.buy_date, date)
            else str(pos.buy_date)[:10]
        ),
        "avg_cost": pos.avg_cost,
        "quantity": pos.quantity,
        "position_pct": pos.position_pct,
        "buy_reason": pos.buy_reason,
        "sector_name": pos.sector_name,
        "original_strategy": pos.original_strategy,
        "entry_snapshot_json": pos.entry_snapshot_json,
        "snapshot_version": pos.snapshot_version,
        "user_note": pos.user_note,
        "is_simulated": pos.is_simulated,
        "source": pos.source,
        "status": pos.status,
        "closed_at": (
            pos.closed_at.isoformat() if pos.closed_at else None
        ),
        "created_at": (
            pos.created_at.isoformat() if pos.created_at else None
        ),
        "updated_at": (
            pos.updated_at.isoformat() if pos.updated_at else None
        ),
    }
