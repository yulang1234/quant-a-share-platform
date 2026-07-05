"""
Factor calculator — read qfq data, compute factors, save to DuckDB.

V0.7: full implementation.  No AkShare, no Parquet, no data modification.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from src.factors.base_factor import ensure_factor_columns
from src.factors.momentum_factors import calculate_momentum_factors
from src.factors.price_factors import calculate_all_price_factors
from src.factors.volatility_factors import calculate_volatility_factors
from src.factors.volume_factors import calculate_all_volume_factors
from src.storage.duckdb_repo import (
    fetch_daily_factors,
    query_df,
    upsert_daily_factors,
)
from src.universe.stock_pool import get_active_stock_pool

logger = logging.getLogger(__name__)

_EXPECTED_COLS = [
    "return_1d", "return_5d", "return_10d", "return_20d", "return_60d",
    "momentum_5d", "momentum_10d", "momentum_20d", "momentum_60d",
    "ma5", "ma10", "ma20", "ma60", "ma120",
    "close_ma5_ratio", "close_ma10_ratio", "close_ma20_ratio",
    "close_ma60_ratio", "close_ma120_ratio",
    "volatility_5d", "volatility_10d", "volatility_20d", "volatility_60d",
    "volume_ma5", "volume_ma20", "volume_ma60",
    "volume_ratio_5_20", "volume_ratio_20_60",
    "amount_ma5", "amount_ma20", "amount_ma60",
    "turnover_ma5", "turnover_ma20", "turnover_ma60",
    "turnover_ratio_5_20",
    "high_20d", "low_20d", "price_position_20d",
    "high_60d", "low_60d", "price_position_60d",
]


def get_factor_source_data(
    stock_codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Read qfq daily data for factor calculation.

    Parameters
    ----------
    stock_codes : list[str], optional
        If None, reads from active stock pool.
    start_date : str, optional
        "YYYY-MM-DD".
    end_date : str, optional
    limit : int, optional
        Max number of stocks.

    Returns
    -------
    pd.DataFrame
        Sorted by stock_code, trade_date.  Stock codes are 6-digit strings.
    """
    if limit is not None and limit <= 0:
        return pd.DataFrame()

    if stock_codes is None:
        pool = get_active_stock_pool()
        stock_codes = pool["stock_code"].astype(str).str.zfill(6).tolist()

    if limit is not None and len(stock_codes) > limit:
        stock_codes = stock_codes[:limit]

    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions) if conditions else "1=1"

    dfs: list[pd.DataFrame] = []
    for code in stock_codes:
        try:
            sql = (
                f"SELECT * FROM stock_daily_qfq WHERE stock_code = ? AND {where} "
                "ORDER BY trade_date"
            )
            part = query_df(sql, [code])
            if not part.empty:
                dfs.append(part)
        except Exception:
            logger.debug("No qfq data for %s", code)

    if not dfs:
        return pd.DataFrame()

    result = pd.concat(dfs, ignore_index=True)
    if "stock_code" in result.columns:
        result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    return result.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)


def calculate_daily_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all V0.7 factors from a qfq DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame()

    price = calculate_all_price_factors(df)
    mom = calculate_momentum_factors(df)
    vol = calculate_volatility_factors(df)
    vol_factors = calculate_all_volume_factors(df)

    result = price.merge(mom, on=["stock_code", "trade_date"], how="left")
    result = result.merge(vol, on=["stock_code", "trade_date"], how="left")
    result = result.merge(vol_factors, on=["stock_code", "trade_date"], how="left")

    result["factor_date"] = pd.Timestamp.now().date()
    result["source_adj"] = "qfq"
    result = ensure_factor_columns(result, _EXPECTED_COLS)

    return result


def save_daily_factors(factor_df: pd.DataFrame) -> int:
    """Write factor DataFrame to stock_daily_factors (upsert)."""
    if factor_df is None or factor_df.empty:
        return 0
    return upsert_daily_factors(factor_df)


def run_factor_calculation(
    pool_name: str = "core_500",
    stock_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Full pipeline: read qfq data, compute factors, save to DuckDB.

    Returns
    -------
    dict
        Keys: total_stocks, source_rows, factor_rows, written_rows, status.
    """
    codes = [str(stock_code).zfill(6)] if stock_code else None
    source_df = get_factor_source_data(
        stock_codes=codes, start_date=start_date,
        end_date=end_date, limit=limit,
    )
    source_rows = len(source_df)

    if source_df.empty:
        return {
            "total_stocks": 1 if stock_code else 0,
            "source_rows": 0,
            "factor_rows": 0,
            "written_rows": 0,
            "status": "skipped (no qfq data)",
        }

    factor_df = calculate_daily_factors(source_df)
    factor_rows = len(factor_df)
    written = save_daily_factors(factor_df)

    return {
        "total_stocks": len(source_df["stock_code"].unique()) if "stock_code" in source_df.columns else 0,
        "source_rows": source_rows,
        "factor_rows": factor_rows,
        "written_rows": written,
        "status": "success",
    }
