"""
AkShare data client -- wrapper around akshare for A-share market data.

Provides methods to fetch daily K-line data (raw / forward-adjusted) for a
single stock via ``ak.stock_zh_a_hist``.

Usage::

    client = AkShareClient()
    df_raw = client.fetch_stock_daily("000001", "20060101", "20260703", adj="raw")
    df_qfq = client.fetch_stock_daily("000001", "20060101", "20260703", adj="qfq")
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

logger = logging.getLogger(__name__)

# Column mapping: Chinese -> English.
# These field names are exactly what akshare's stock_zh_a_hist returns.
_COLUMN_MAP: dict[str, str] = {
    "日期": "trade_date",
    "股票代码": "stock_code",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change_amount",
    "换手率": "turnover_rate",
    "前收盘": "pre_close",
}

# Columns to keep after mapping (in preferred display order)
_FINAL_COLUMNS = [
    "stock_code", "trade_date", "open", "close", "high", "low",
    "pre_close", "volume", "amount", "amplitude",
    "pct_change", "change_amount", "turnover_rate",
]

# Core fields that MUST be present after mapping
_CORE_FIELDS = {"trade_date", "open", "close", "high", "low"}


class AkShareClient:
    """Thin wrapper around akshare functions for A-share market data."""

    def __init__(self) -> None:
        """Initialize the client."""
        pass

    @staticmethod
    def normalize_code(stock_code: str | int) -> str:
        """Normalise *stock_code* to a 6-digit zero-padded string.

        Parameters
        ----------
        stock_code : str or int
            Raw stock identifier, e.g. ``1``, ``"000001"``, ``600519``.

        Returns
        -------
        str
            6-digit string.

        Raises
        ------
        ValueError
            If the code cannot be represented as exactly 6 digits.
        """
        if isinstance(stock_code, int):
            s = str(stock_code).zfill(6)
        else:
            s = stock_code.strip()
            if not s or len(s) > 6:
                raise ValueError(f"Stock code must be 6 digits, got '{stock_code}'")
            s = s.zfill(6)
        if len(s) != 6 or not s.isdigit():
            raise ValueError(f"Stock code must be 6 digits, got '{stock_code}'")
        return s

    # -- Fetch methods -------------------------------------------------------

    def fetch_stock_daily_raw(
        self, stock_code: str | int, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch unadjusted daily K-line for one stock.

        Parameters
        ----------
        stock_code : str or int
            6-digit A-stock code (int or str accepted).
        start_date : str
            ``"YYYYMMDD"`` format.
        end_date : str
            ``"YYYYMMDD"`` format.

        Returns
        -------
        pd.DataFrame
            Columns: stock_code, trade_date, open, high, low, close,
            pre_close, volume, amount, amplitude, pct_change,
            change_amount, turnover_rate.
            Empty DataFrame if no data is returned.
        """
        return self._fetch_and_map(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )

    def fetch_stock_daily_qfq(
        self, stock_code: str | int, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch forward-adjusted (QFQ) daily K-line for one stock.

        Parameters are identical to :meth:`fetch_stock_daily_raw`.
        The returned DataFrame has the same column schema, but note that
        QFQ data from akshare does **not** include ``pre_close``,
        ``amplitude``, or ``change_amount`` -- these columns will be ``NaN``
        in the returned DataFrame.
        """
        return self._fetch_and_map(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )

    def fetch_stock_daily(
        self,
        stock_code: str | int,
        start_date: str,
        end_date: str,
        adj: str = "raw",
    ) -> pd.DataFrame:
        """Fetch daily K-line with the specified adjustment type.

        Parameters
        ----------
        stock_code : str or int
        start_date : str
        end_date : str
        adj : str
            ``"raw"`` for unadjusted, ``"qfq"`` for forward-adjusted.

        Returns
        -------
        pd.DataFrame

        Raises
        ------
        ValueError
            If *adj* is not ``"raw"`` or ``"qfq"``.
        """
        if adj == "raw":
            return self.fetch_stock_daily_raw(stock_code, start_date, end_date)
        if adj == "qfq":
            return self.fetch_stock_daily_qfq(stock_code, start_date, end_date)
        raise ValueError(f"adj must be 'raw' or 'qfq', got '{adj}'")

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _get_akshare_module():
        """Lazy-import and return the akshare module.

        This indirection allows tests to monkey-patch the method and
        avoid importing akshare when it is not installed.
        """
        try:
            import akshare as ak  # noqa: F401
            return ak
        except ImportError:
            raise ImportError(
                "akshare is required for fetching market data. "
                "Please install it with: pip install akshare"
            )

    @staticmethod
    def _format_date(date_val: str | datetime | date) -> str:
        """Convert a date value to the ``YYYYMMDD`` string AkShare expects.

        Accepts:
        - ``"20260703"`` (already correct)
        - ``"2026-07-03"`` (with hyphens)
        - ``datetime`` / ``datetime.date`` objects
        - ``pandas Timestamp`` objects

        Returns
        -------
        str
            ``"YYYYMMDD"``

        Raises
        ------
        ValueError
            If the input cannot be parsed as a valid date.
        """
        if isinstance(date_val, str):
            cleaned = date_val.replace("-", "").strip()
            if not cleaned.isdigit() or len(cleaned) != 8:
                raise ValueError(
                    f"Invalid date string '{date_val}' -- expected YYYYMMDD "
                    f"or YYYY-MM-DD"
                )
            return cleaned
        if isinstance(date_val, datetime):
            return date_val.strftime("%Y%m%d")
        if isinstance(date_val, date):
            return date_val.strftime("%Y%m%d")
        if hasattr(date_val, "strftime"):
            return date_val.strftime("%Y%m%d")
        raise ValueError(
            f"Cannot parse date from {type(date_val).__name__}: {date_val}"
        )

    def _fetch_and_map(
        self,
        stock_code: str | int,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        """Call akshare, map columns, and return a clean DataFrame.

        If the API returns no rows, an empty DataFrame with the correct
        schema is returned instead of raising.
        """
        ak = self._get_akshare_module()

        code = self.normalize_code(stock_code)
        raw_start = self._format_date(start_date)
        raw_end = self._format_date(end_date)

        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=raw_start,
                end_date=raw_end,
                adjust=adjust,
            )
        except Exception as exc:
            logger.warning(
                "AkShare request failed for %s (adj=%s): %s",
                code, adjust, exc,
            )
            raise

        if df is None or df.empty:
            logger.info("No data for %s (adj=%s)", code, adjust)
            return self._empty_result(code)

        # Column mapping: rename Chinese columns to English
        df = df.rename(columns=_COLUMN_MAP)

        # Validate core fields are present after mapping
        mapped_cols = set(df.columns)
        missing = _CORE_FIELDS - mapped_cols
        if missing:
            raise ValueError(
                f"AkShare response for {code} (adj={adjust}) is missing "
                f"core fields: {sorted(missing)}. "
                f"Available columns: {sorted(mapped_cols)}"
            )

        # Ensure stock_code column is 6-char string
        df["stock_code"] = code
        # Parse trade_date to date
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        # Keep only known columns, drop extras
        keep = [c for c in _FINAL_COLUMNS if c in df.columns]
        df = df[keep]

        # Ensure numeric types for price/volume columns
        numeric_cols = [
            "open", "close", "high", "low", "pre_close",
            "volume", "amount", "amplitude",
            "pct_change", "change_amount", "turnover_rate",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.reset_index(drop=True)

    @staticmethod
    def _empty_result(stock_code: str) -> pd.DataFrame:
        """Return an empty DataFrame with the standard column schema."""
        data = {col: pd.Series(dtype="object") for col in _FINAL_COLUMNS}
        df = pd.DataFrame(data)
        df["stock_code"] = stock_code
        return df
