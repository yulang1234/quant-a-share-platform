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

    @staticmethod
    def get_stock_sector(stock_code: str | int) -> str:
        """Fetch the industry / sector classification for a single A-stock.

        Thin wrapper around :meth:`get_stock_basic_info` — kept for
        backward compatibility.
        """
        return AkShareClient.get_stock_basic_info(stock_code)["sector"]

    @staticmethod
    def get_stock_basic_info(stock_code: str | int) -> dict[str, str]:
        """Fetch basic information for a single A-stock from East Money.

        Uses ``ak.stock_individual_info_em()`` to retrieve stock name and
        industry classification.

        Parameters
        ----------
        stock_code : str or int
            6-digit A-stock code.

        Returns
        -------
        dict[str, str]
            Keys: ``"stock_code"``, ``"stock_name"``, ``"sector"``.
            Empty strings for any field that cannot be determined.
            Never raises — all errors are caught and logged.
        """
        try:
            code = AkShareClient.normalize_code(stock_code)
        except Exception:
            logger.warning("Invalid stock code for basic info: %s", stock_code)
            return {"stock_code": "", "stock_name": "", "sector": ""}

        result: dict[str, str] = {
            "stock_code": code,
            "stock_name": "",
            "sector": "",
        }

        try:
            ak = AkShareClient._get_akshare_module()
        except Exception as exc:
            logger.warning("AkShare import failed for %s: %s", code, exc)
            return result

        # ── 1. Name via stock_info_a_code_name ──────────────────────────
        try:
            names = ak.stock_info_a_code_name()
            if names is not None and not names.empty:
                code_col = "code" if "code" in names.columns else "代码" if "代码" in names.columns else ""
                name_col = "name" if "name" in names.columns else "名称" if "名称" in names.columns else ""
                if code_col and name_col:
                    matched = names[names[code_col].astype(str).str.zfill(6) == code]
                    if not matched.empty:
                        name = str(matched.iloc[0][name_col]).strip()
                        if name and name != "nan":
                            result["stock_name"] = name
        except Exception:
            logger.warning("AkShare name lookup failed for %s", code)
            logger.debug("AkShare name lookup detail:", exc_info=True)

        # ── 2. Sector via stock_individual_info_em ─────────────────────
        try:
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                if "item" in df.columns and "value" in df.columns:
                    lookup: dict[str, str] = {}
                    for _, row in df.iterrows():
                        key = str(row["item"]).strip()
                        val = str(row["value"]).strip()
                        lookup[key] = val

                    for name_key in ("股票简称", "证券简称", "股票名称"):
                        if (not result["stock_name"]
                                and name_key in lookup and lookup[name_key]
                                and lookup[name_key] != "nan"):
                            result["stock_name"] = lookup[name_key]
                            break

                    for sector_key in ("行业", "所属行业", "板块"):
                        if sector_key in lookup and lookup[sector_key] and lookup[sector_key] != "nan":
                            result["sector"] = lookup[sector_key]
                            break
        except Exception:
            logger.warning("AkShare sector lookup failed for %s", code)
            logger.debug("AkShare sector lookup detail:", exc_info=True)

        return result

    # -- Sector resolution helpers -------------------------------------------

    # Module-level cache: stock_code (6-digit str) → sector name
    _ths_sector_cache: dict[str, str] = {}
    _ths_cache_built: bool = False

    @staticmethod
    def _resolve_sector_em(code: str) -> str:
        """Try ``stock_individual_info_em`` (East Money) for sector.

        Returns empty string on any failure."""
        try:
            ak = AkShareClient._get_akshare_module()
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                return ""
            if "item" not in df.columns or "value" not in df.columns:
                return ""
            for _, row in df.iterrows():
                if str(row["item"]).strip() == "行业":
                    val = str(row["value"]).strip()
                    return val if val and val != "nan" else ""
        except Exception:
            logger.debug("_resolve_sector_em failed for %s", code, exc_info=True)
        return ""

    @staticmethod
    def _resolve_sector_cninfo(code: str) -> str:
        """Try CNINFO ``stock_industry_category_cninfo`` for per-stock sector.

        Returns empty string on any failure."""
        try:
            ak = AkShareClient._get_akshare_module()
            df = ak.stock_industry_category_cninfo(symbol=code)
            if df is not None and not df.empty and "industry" in df.columns:
                val = str(df.iloc[0]["industry"]).strip()
                return val if val and val != "nan" else ""
        except Exception:
            logger.debug("_resolve_sector_cninfo failed for %s", code, exc_info=True)
        return ""

    @staticmethod
    def _resolve_sector_ths(code: str, name: str = "") -> str:
        """Build & cache a THS (同花顺) industry→stocks mapping, then look up.

        On first call this iterates all THS industry boards.  Subsequent calls
        hit an in-memory cache.  Returns empty string on any failure.
        """
        if AkShareClient._ths_cache_built:
            return AkShareClient._ths_sector_cache.get(code, "")

        try:
            ak = AkShareClient._get_akshare_module()

            # Step 1: get all industry board names
            try:
                boards = ak.stock_board_industry_name_ths()
            except (AttributeError, Exception):
                logger.info(
                    "THS industry board list API unavailable — skipping THS sector cache."
                )
                AkShareClient._ths_cache_built = True
                return ""

            if boards is None or boards.empty:
                logger.info("THS industry board list returned empty — skipping.")
                AkShareClient._ths_cache_built = True
                return ""

            # Detect column name for industry name
            for col_candidate in ("name", "名称", "industry_name", "板块名称"):
                if col_candidate in boards.columns:
                    name_col = col_candidate
                    break
            else:
                logger.info(
                    "THS industry board columns unknown: %s — skipping.",
                    list(boards.columns),
                )
                AkShareClient._ths_cache_built = True
                return ""

            industry_names = boards[name_col].dropna().astype(str).tolist()
            if not industry_names:
                logger.info("THS industry board list has no names — skipping.")
                AkShareClient._ths_cache_built = True
                return ""

            logger.info("Building THS sector cache from %d industries…", len(industry_names))

            # Step 2: for each industry, get constituent stocks
            for industry in industry_names:
                try:
                    cons = ak.stock_board_industry_cons_ths(symbol=industry)
                    if cons is not None and not cons.empty:
                        # Detect code column
                        for cc in ("code", "代码", "stock_code", "股票代码"):
                            if cc in cons.columns:
                                code_col = cc
                                break
                        else:
                            continue
                        for _, row in cons.iterrows():
                            c = str(row[code_col]).strip().zfill(6)
                            if len(c) == 6 and c.isdigit():
                                AkShareClient._ths_sector_cache[c] = industry
                except Exception:
                    logger.debug("THS industry '%s' skipped", industry, exc_info=True)

            AkShareClient._ths_cache_built = True
            mapped = len(AkShareClient._ths_sector_cache)
            if mapped > 0:
                logger.info("THS sector cache ready: %d stocks mapped.", mapped)
            else:
                logger.info(
                    "THS sector cache built but 0 stocks mapped — "
                    "API returned no constituent data."
                )
        except Exception:
            logger.warning("Failed to build THS sector cache", exc_info=True)
            AkShareClient._ths_cache_built = True  # don't retry forever

        return AkShareClient._ths_sector_cache.get(code, "")

    @staticmethod
    def _resolve_sector_tushare(code: str) -> str:
        """Try Tushare for Shenwan (申万) industry classification.

        Requires ``TUSHARE_TOKEN`` environment variable.  Returns empty
        string if the token is missing or the API call fails.
        """
        import os
        token = os.getenv("TUSHARE_TOKEN", "")
        if not token:
            return ""

        try:
            import tushare as ts  # type: ignore[import-untyped]
            pro = ts.pro_api(token)
            exchange = "SH" if code.startswith("6") else "SZ"
            ts_code = f"{code}.{exchange}"
            df = pro.stock_basic(ts_code=ts_code, fields="industry")
            if df is not None and not df.empty:
                val = str(df.iloc[0]["industry"]).strip()
                return val if val and val != "nan" else ""
        except Exception:
            logger.debug("Tushare sector lookup failed for %s", code, exc_info=True)

        return ""

    @classmethod
    def resolve_sector_remote(cls, code: str, stock_name: str = "") -> tuple[str, str]:
        """Try all remote (API) sources for sector.  Does NOT check local DB/CSV.

        Returns
        -------
        tuple[str, str]
            ``(sector_value, source_label)``
        """
        # 1. East Money individual info
        sector = cls._resolve_sector_em(code)
        if sector:
            return sector, "akshare_em"

        # 2. CNINFO
        sector = cls._resolve_sector_cninfo(code)
        if sector:
            return sector, "akshare_cninfo"

        # 3. THS (cached)
        sector = cls._resolve_sector_ths(code, stock_name)
        if sector:
            return sector, "akshare_ths"

        # 4. Tushare (optional)
        sector = cls._resolve_sector_tushare(code)
        if sector:
            return sector, "tushare"

        return "", "empty"

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
