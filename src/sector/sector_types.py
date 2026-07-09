"""V1.5.3 sector types — dataclasses and enumerations.

Provides structured types for sector basic info and stock-sector mappings.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Sector type tokens ──────────────────────────────────────────────────────

SECTOR_INDUSTRY = "industry"
SECTOR_CONCEPT = "concept"
SECTOR_REGION = "region"
SECTOR_THEME = "theme"
SECTOR_UNKNOWN = "unknown"

SECTOR_TYPES: tuple[str, ...] = (
    SECTOR_INDUSTRY, SECTOR_CONCEPT, SECTOR_REGION, SECTOR_THEME, SECTOR_UNKNOWN,
)

# ── Source tokens ───────────────────────────────────────────────────────────

SOURCE_AKSHARE = "akshare"
SOURCE_TUSHARE = "tushare"
SOURCE_MANUAL = "manual"
SOURCE_UNKNOWN = "unknown"

SOURCES: tuple[str, ...] = (SOURCE_AKSHARE, SOURCE_TUSHARE, SOURCE_MANUAL, SOURCE_UNKNOWN)


@dataclass
class SectorBasic:
    """A single sector/board entry."""

    sector_code: str
    sector_name: str
    sector_type: str = SECTOR_UNKNOWN
    source: str = SOURCE_MANUAL
    source_sector_code: str | None = None
    description: str | None = None
    is_active: bool = True
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StockSectorMapping:
    """A single stock-to-sector mapping row."""

    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    sector_type: str = SECTOR_UNKNOWN
    source: str = SOURCE_MANUAL
    weight: float = 1.0
    is_active: bool = True
    start_date: str | None = None
    end_date: str | None = None
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StockSectorsResult:
    """Result of querying sectors for a stock."""

    stock_code: str
    stock_name: str
    sectors: list[dict[str, Any]] = field(default_factory=list)
    missing: bool = False
    version: str = "v1.5.3"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectorStocksResult:
    """Result of querying stocks for a sector."""

    sector_code: str
    sector_name: str
    sector_type: str = SECTOR_UNKNOWN
    stocks: list[dict[str, Any]] = field(default_factory=list)
    stock_count: int = 0
    missing: bool = False
    version: str = "v1.5.3"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
