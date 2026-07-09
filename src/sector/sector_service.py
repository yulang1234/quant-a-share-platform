"""V1.5.3 sector service — business logic for stock-sector queries.

Provides the core query APIs required by V1.5.3:
- get_sectors_by_stock(stock_code) → StockSectorsResult
- get_stocks_by_sector(sector_name/code) → SectorStocksResult
- get_sector_basic(sector_name/code) → SectorBasic or None
- validate_sector_mapping() → dict with completeness stats
"""
from __future__ import annotations

import logging
from typing import Any

from src.sector.sector_types import (
    StockSectorsResult,
    SectorStocksResult,
    SECTOR_UNKNOWN,
)

logger = logging.getLogger(__name__)


def get_sectors_by_stock(stock_code: str) -> StockSectorsResult:
    """Return all sectors a stock belongs to.

    Args:
        stock_code: 6-digit stock code (e.g. "000001")

    Returns:
        StockSectorsResult with sectors list and missing flag.
    """
    code = str(stock_code).zfill(6)
    try:
        from src.sector.sector_repository import get_sectors_by_stock as _repo_query
        df = _repo_query(code)
    except Exception as exc:
        logger.warning("Failed to query sectors for %s: %s", code, exc)
        return StockSectorsResult(
            stock_code=code, stock_name="", sectors=[], missing=True,
        )

    if df is None or df.empty:
        return StockSectorsResult(
            stock_code=code, stock_name="", sectors=[], missing=True,
        )

    stock_name = str(df.iloc[0].get("stock_name", ""))
    sectors: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        sectors.append({
            "sector_code": str(row.get("sector_code", "")),
            "sector_name": str(row.get("sector_name", "")),
            "sector_type": str(row.get("sector_type", SECTOR_UNKNOWN)),
            "source": str(row.get("source", "")),
            "updated_at": str(row.get("updated_at", "")),
        })

    return StockSectorsResult(
        stock_code=code,
        stock_name=stock_name,
        sectors=sectors,
        missing=False,
    )


def get_stocks_by_sector(
    sector_name: str | None = None,
    sector_code: str | None = None,
) -> SectorStocksResult:
    """Return all stocks in a sector.

    Args:
        sector_name: e.g. "银行"
        sector_code: e.g. "BK0475"

    Returns:
        SectorStocksResult with stocks list and missing flag.
    """
    if not sector_name and not sector_code:
        return SectorStocksResult(
            sector_code="", sector_name="", stocks=[], missing=True,
        )

    try:
        from src.sector.sector_repository import get_stocks_by_sector as _repo_query
        df = _repo_query(sector_code=sector_code, sector_name=sector_name)
    except Exception as exc:
        logger.warning("Failed to query stocks for sector: %s", exc)
        return SectorStocksResult(
            sector_code=sector_code or "",
            sector_name=sector_name or "",
            stocks=[], missing=True,
        )

    if df is None or df.empty:
        return SectorStocksResult(
            sector_code=sector_code or "",
            sector_name=sector_name or "",
            stocks=[], missing=True,
        )

    first = df.iloc[0]
    resolved_code = sector_code or str(first.get("sector_code", ""))
    resolved_name = sector_name or str(first.get("sector_name", ""))
    resolved_type = str(first.get("sector_type", SECTOR_UNKNOWN))

    stocks: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        stocks.append({
            "stock_code": str(row.get("stock_code", "")),
            "stock_name": str(row.get("stock_name", "")),
            "source": str(row.get("source", "")),
        })

    return SectorStocksResult(
        sector_code=resolved_code,
        sector_name=resolved_name,
        sector_type=resolved_type,
        stocks=stocks,
        stock_count=len(stocks),
        missing=False,
    )


def get_sector_basic_info(
    sector_name: str | None = None,
    sector_code: str | None = None,
) -> dict[str, Any] | None:
    """Return sector basic info as a dict, or None if not found."""
    try:
        from src.sector.sector_repository import get_sector_basic
        df = get_sector_basic(sector_code=sector_code, sector_name=sector_name)
    except Exception as exc:
        logger.warning("Failed to query sector basic: %s", exc)
        return None

    if df is None or df.empty:
        return None

    row = df.iloc[0]
    return {
        "sector_code": str(row.get("sector_code", "")),
        "sector_name": str(row.get("sector_name", "")),
        "sector_type": str(row.get("sector_type", SECTOR_UNKNOWN)),
        "source": str(row.get("source", "")),
        "source_sector_code": str(row.get("source_sector_code", "")),
        "description": str(row.get("description", "")),
        "is_active": bool(row.get("is_active", True)),
        "updated_at": str(row.get("updated_at", "")),
    }


def validate_sector_mapping() -> dict[str, Any]:
    """Check sector mapping completeness.

    Returns:
        dict with summary stats about the current mapping state.
    """
    try:
        from src.sector.sector_repository import (
            count_sector_mappings, list_all_sectors,
        )
        mapping_count = count_sector_mappings()
        sectors_df = list_all_sectors()
        sector_count = len(sectors_df) if sectors_df is not None else 0

        return {
            "total_sectors": sector_count,
            "total_mappings": mapping_count,
            "is_empty": mapping_count == 0,
            "status": "ok" if mapping_count > 0 else "empty",
            "version": "v1.5.3",
        }
    except Exception as exc:
        logger.warning("Failed to validate sector mapping: %s", exc)
        return {
            "total_sectors": 0,
            "total_mappings": 0,
            "is_empty": True,
            "status": f"error: {exc}",
            "version": "v1.5.3",
        }
