"""Types for V1.7.1 portfolio position management.

Defines enums, dataclasses, input contracts and business exceptions.
No database or network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


# ── Enums ────────────────────────────────────────────────────────────────────


class PositionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class PositionMode(str, Enum):
    REAL = "real"
    SIMULATED = "simulated"


POSITION_STATUS_CN: dict[str, str] = {
    "active": "活跃",
    "closed": "已关闭",
}

POSITION_MODE_CN: dict[str, str] = {
    "real": "真实",
    "simulated": "模拟",
}


# ── Input dataclasses ─────────────────────────────────────────────────────────


@dataclass
class PositionCreateInput:
    """Validated input for creating a new position."""

    portfolio_name: str = "default"
    stock_code: str = ""
    exchange: str = ""
    stock_name: str = ""
    buy_date: str = ""  # "YYYY-MM-DD"
    avg_cost: float = 0.0
    quantity: float | None = None
    position_pct: float = 0.0
    buy_reason: str = ""
    sector_name: str | None = None
    original_strategy: str | None = None
    user_note: str | None = None
    is_simulated: bool = True
    capture_entry_snapshot: bool = False

    # Filled by service after creation:
    entry_snapshot_json: str | None = field(default=None, compare=False)
    snapshot_version: str | None = field(default=None, compare=False)
    snapshot_issue: str | None = field(default=None, compare=False)


@dataclass
class PositionUpdateInput:
    """Validated input for updating an existing position.

    Only fields that are safe to modify are included.
    stock_code, exchange and is_simulated are NOT updatable.
    """

    portfolio_name: str | None = None
    stock_name: str | None = None
    avg_cost: float | None = None
    quantity: float | None = None
    position_pct: float | None = None
    buy_reason: str | None = None
    sector_name: str | None = None
    original_strategy: str | None = None
    user_note: str | None = None


# ── Output / presentation ─────────────────────────────────────────────────────


@dataclass
class PositionSummary:
    """Aggregated summary of a filtered position list."""

    total_count: int = 0
    active_count: int = 0
    closed_count: int = 0
    real_count: int = 0
    simulated_count: int = 0
    total_position_pct: float = 0.0
    position_pct_ok: bool = True


@dataclass
class PositionRow:
    """Flat row for UI tables / CSV export."""

    position_id: int
    portfolio_name: str
    mode_cn: str
    stock_code: str
    stock_name: str
    exchange: str
    buy_date: str
    avg_cost: float
    quantity: float | None
    position_pct: float
    sector_name: str
    original_strategy: str
    status_cn: str
    has_snapshot: bool
    updated_at: str


# ── Business exceptions ───────────────────────────────────────────────────────


class PositionValidationError(ValueError):
    """Input validation failed for a position operation."""

    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message)
        self.field = field


class DuplicateActivePositionError(Exception):
    """An active position already exists for the same stock in the same portfolio."""

    def __init__(
        self, portfolio_name: str, stock_code: str, is_simulated: bool
    ) -> None:
        mode = "模拟" if is_simulated else "真实"
        super().__init__(
            f"组合 [{portfolio_name}] 中已存在股票 {stock_code} 的活跃{mode}持仓，"
            f"请编辑已有记录或先关闭。"
        )
        self.portfolio_name = portfolio_name
        self.stock_code = stock_code
        self.is_simulated = is_simulated


class PositionNotFoundError(Exception):
    """No position found for the given position_id."""

    def __init__(self, position_id: int) -> None:
        super().__init__(f"持仓记录不存在: position_id={position_id}")
        self.position_id = position_id


class PositionAlreadyClosedError(Exception):
    """The position is already closed and cannot be closed again."""

    def __init__(self, position_id: int) -> None:
        super().__init__(f"持仓记录已关闭: position_id={position_id}")
        self.position_id = position_id
