"""V1.4.1 standardised field mapping for daily bar data.

All providers must map their output to this schema.
"""

import pandas as pd

DAILY_BAR_COLUMNS = [
    "symbol", "exchange", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "adj_type", "provider_name",
]


def validate_daily_bar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a daily bar DataFrame has all required columns.

    Missing columns are filled with NaN.  Returns the DataFrame unchanged
    if all columns already exist.
    """
    for col in DAILY_BAR_COLUMNS:
        if col not in df.columns:
            df[col] = float("nan")
    return df


def apply_provider_name(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Set the provider_name column in *df*."""
    df = df.copy()
    df["provider_name"] = name
    return df


def normalise_symbol_exchange(symbol: str, exchange: str | None = None) -> tuple[str, str]:
    """Normalise a 6-digit code or '000001.SZ' to (symbol, exchange).

    Returns (6-digit string, 'SH'/'SZ'/'BJ').
    """
    s = str(symbol).strip()
    if "." in s:
        parts = s.split(".")
        code = parts[0].zfill(6)
        ex = parts[1].upper()
        return code, ex
    code = s.zfill(6)
    if code.startswith("6"):
        return code, "SH"
    if code.startswith(("0", "3")):
        return code, "SZ"
    if code.startswith(("8", "4")):
        return code, "BJ"
    return code, exchange or "UNKNOWN"
