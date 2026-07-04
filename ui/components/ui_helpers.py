"""V1.4 UI helper functions — safe data display wrappers."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.storage.duckdb_repo import query_df


def safe_fetch_table_count(table_name: str) -> int:
    try:
        r = query_df(f"SELECT COUNT(*) AS c FROM {table_name}")
        return int(r.iloc[0]["c"]) if not r.empty else 0
    except Exception:
        return 0


def safe_fetch_latest_date(table_name: str, date_col: str = "trade_date") -> str | None:
    try:
        r = query_df(f"SELECT MAX({date_col}) AS d FROM {table_name}")
        if r.empty: return None
        val = r.iloc[0]["d"]
        return str(val)[:10] if val else None
    except Exception:
        return None


def safe_fetch_sample(table_name: str, limit: int = 20) -> pd.DataFrame:
    try:
        return query_df(f"SELECT * FROM {table_name} LIMIT {int(limit)}")
    except Exception:
        return pd.DataFrame()


def safe_display_dataframe(df: pd.DataFrame, title: str | None = None) -> None:
    if df is not None and not df.empty:
        if title:
            st.caption(title)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("暂无数据")


def render_command_block(commands: str) -> None:
    st.code(commands, language="bash")


def render_kpi_card(label: str, value, delta: str | None = None) -> None:
    st.metric(label, value, delta=delta)


def safe_metric(label: str, table: str, default: str = "0") -> str:
    try:
        r = query_df(f"SELECT COUNT(*) AS c FROM {table}")
        return str(int(r.iloc[0]["c"])) if not r.empty else default
    except Exception:
        return default
