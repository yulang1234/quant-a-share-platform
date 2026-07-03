"""
Streamlit UI for the Quant A-Share Research Platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

import pandas as pd
import streamlit as st

from src.storage.duckdb_repo import init_database, query_df
from src.universe.stock_pool import (
    activate_stock,
    add_stock_to_pool,
    blacklist_stock,
    deactivate_stock,
    delete_stock_from_pool,
    get_stock_pool,
    load_stock_pool_from_csv,
    remove_blacklist,
    save_stock_pool_to_db,
    validate_stock_code,
)
from src.universe.filters import apply_basic_filters, filter_st_stocks

# ======================================================================
#  CSS — Dark professional theme
# ======================================================================

_CSS = """
<style>
/* ── Base ── */
.stApp, .stApp > header { background-color: #0b1020 !important; }
.block-container { max-width: 1280px; padding-top: 4.8rem !important; }

/* ── Typography ── */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e8edf5;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] { display: none; }

/* ── Metric / KPI cards ── */
div[data-testid="metric-container"] {
    background: #141d30 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 1.05rem 1.25rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    transition: border-color 0.15s ease;
}
div[data-testid="metric-container"]:hover {
    border-color: rgba(255,255,255,0.14) !important;
}
div[data-testid="metric-container"] > div:first-child {
    font-size: 0.68rem !important;
    color: #7a88a6 !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
div[data-testid="metric-container"] > div:nth-child(2) {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #f0f4ff !important;
}
div[data-testid="metric-container"] > div:nth-child(3) {
    font-size: 0.7rem !important;
    color: #5a6a8a !important;
}

/* ── Bordered containers (card style for st.container(border=True)) ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #141d30 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
}

/* ── DataFrames ── */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    background: #121a2b !important;
}
div[data-testid="stDataFrame"] table {
    background: #121a2b !important;
    color: #d0d8e8 !important;
    font-size: 0.78rem !important;
}
div[data-testid="stDataFrame"] th {
    background: #162033 !important;
    color: #7a88a6 !important;
    font-weight: 500 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.55rem 0.65rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
}
div[data-testid="stDataFrame"] td {
    background: #121a2b !important;
    color: #c8d0e0 !important;
    padding: 0.45rem 0.65rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.03) !important;
}
div[data-testid="stDataFrame"] tr:hover td {
    background: #162033 !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    background: #121a2b !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 8px !important;
}
div[data-testid="stExpander"] summary {
    color: #9aa6bd !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}
div[data-testid="stExpander"] summary:hover {
    color: #e8edf5 !important;
}

/* ── Buttons ── */
.stButton button {
    border-radius: 6px !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    background: #1e2a45 !important;
    color: #c8d0e0 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    transition: all 0.12s;
}
.stButton button:hover {
    background: #2a3a5a !important;
    color: #f0f4ff !important;
    border-color: rgba(255,255,255,0.15) !important;
}
.stButton button[kind="primary"] {
    background: #1a4a7a !important;
    color: #f0f4ff !important;
    border: none !important;
}
.stButton button[kind="primary"]:hover {
    background: #205a90 !important;
}

/* ── Tabs (minimal: font / weight / color / underline only) ── */
div[data-testid="stTabs"] button {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #7a88a6 !important;
    padding: 0.5rem 1.1rem !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f0f4ff !important;
    border-bottom-color: #3e8ec0 !important;
}
div[data-testid="stTabs"] button:hover {
    color: #c8d0e0 !important;
}

/* ── Alert / Info / Error ── */
div[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-size: 0.8rem !important;
}
div[data-testid="stInfo"] {
    background: #121a2b !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    color: #9aa6bd !important;
}
div[data-testid="stSuccess"] { background: #0a1f18 !important; color: #3ecf8e !important; }
div[data-testid="stError"] { background: #1f0a0a !important; color: #e85a5a !important; }
div[data-testid="stWarning"] { background: #1a1508 !important; color: #c8a96b !important; }

/* ── Code block ── */
code {
    background: #162033 !important;
    color: #c8d0e0 !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 4px !important;
}
pre {
    background: #0e1525 !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 6px !important;
}

/* ── Input fields ── */
input, textarea, select, div[data-baseweb="select"] > div {
    background-color: #0e1525 !important;
    color: #e8edf5 !important;
    border-color: rgba(255,255,255,0.1) !important;
    border-radius: 6px !important;
}
input:focus, textarea:focus {
    border-color: #3e8ec0 !important;
}

/* ── Checkbox ── */
label[data-testid="stCheckbox"] span {
    color: #9aa6bd !important;
}

/* ── Dividers ── */
hr {
    border-color: rgba(255,255,255,0.06) !important;
    margin: 0.75rem 0 !important;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"] {
    color: #7a88a6 !important;
}
</style>
"""

# ======================================================================
#  Chinese mappings
# ======================================================================

_COL_CN = {
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "market": "市场",
    "exchange": "交易所",
    "pool_name": "股票池",
    "source": "来源",
    "is_active": "状态",
    "is_blacklisted": "黑名单",
    "note": "备注",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "task_type": "任务类型",
    "adj_type": "复权类型",
    "status": "执行状态",
    "row_count": "行数",
    "started_at": "开始时间",
    "finished_at": "完成时间",
    "error_message": "错误信息",
}

_TASK_CN = {"historical_load": "历史初始化", "daily_incremental": "增量更新"}
_ADJ_CN = {"raw": "不复权", "qfq": "前复权"}
_STAT_CN = {"success": "成功", "failed": "失败", "empty": "空结果", "skipped": "跳过"}


def fmt_cols(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in _COL_CN.items() if k in df.columns})


def fmt_log(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "task_type" in d.columns:
        d["task_type"] = d["task_type"].map(_TASK_CN).fillna(d["task_type"])
    if "adj_type" in d.columns:
        d["adj_type"] = d["adj_type"].map(_ADJ_CN).fillna(d["adj_type"])
    if "status" in d.columns:
        d["status"] = d["status"].map(_STAT_CN).fillna(d["status"])
    for c in ("started_at", "finished_at"):
        if c in d.columns:
            d[c] = pd.to_datetime(d[c], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    return fmt_cols(d)


def fmt_pool(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "is_active" in d.columns:
        d["is_active"] = d["is_active"].apply(lambda x: "启用" if x else "停用")
    if "is_blacklisted" in d.columns:
        d["is_blacklisted"] = d["is_blacklisted"].apply(lambda x: "黑名单" if x else "正常")
    return fmt_cols(d)


# ======================================================================
#  Page setup
# ======================================================================

st.set_page_config(page_title="Quant A-Share", layout="wide", initial_sidebar_state="collapsed")
st.markdown(_CSS, unsafe_allow_html=True)
init_database()

# ======================================================================
#  Top spacer — keeps tabs clear of the Streamlit header bar
# ======================================================================

st.markdown(
    "<div style='height:0.75rem'></div>",
    unsafe_allow_html=True,
)

# ======================================================================
#  Tabs
# ======================================================================

TAB_NAMES = ["总览", "股票池", "数据初始化", "增量更新", "过滤结果"]
t_overview, t_pool, t_hist, t_daily, t_filter = st.tabs(TAB_NAMES)

# ======================================================================
#  TAB: 总览
# ======================================================================

with t_overview:
    # ═══════════════════════════════════════════════════════════════════
    #  Hero — brand area
    # ═══════════════════════════════════════════════════════════════════
    h_left, h_right = st.columns([1.5, 1])
    with h_left:
        st.markdown(
            '<div style="font-size:1.5rem;font-weight:700;color:#f0f4ff;'
            'letter-spacing:-0.02em;line-height:1.2;">Quant A-Share</div>'
            '<div style="font-size:0.8rem;color:#7a88a6;">量化研究控制台</div>',
            unsafe_allow_html=True,
        )
    with h_right:
        st.markdown(
            '<div style="display:flex;gap:0.5rem;justify-content:flex-end;'
            'align-items:center;padding-top:0.55rem;">'
            '<span style="background:#141d30;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:12px;padding:3px 12px;font-size:0.7rem;color:#9aa6bd;">v0.4</span>'
            '<span style="background:#141d30;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:12px;padding:3px 12px;font-size:0.7rem;color:#9aa6bd;">开发环境</span>'
            '<span style="background:#141d30;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:12px;padding:3px 12px;font-size:0.7rem;color:#9aa6bd;">'
            'AkShare + DuckDB + Parquet</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    #  KPI cards (4 equal columns)
    # ═══════════════════════════════════════════════════════════════════
    try:
        pool_total = query_df("SELECT COUNT(*) AS c FROM stock_pool").iloc[0]["c"]
        pool_active = query_df(
            "SELECT COUNT(*) AS c FROM stock_pool WHERE is_active=TRUE AND is_blacklisted=FALSE"
        ).iloc[0]["c"]
        raw_rows = query_df("SELECT COUNT(*) AS c FROM stock_daily_raw").iloc[0]["c"]
        qfq_rows = query_df("SELECT COUNT(*) AS c FROM stock_daily_qfq").iloc[0]["c"]
        log_total = query_df("SELECT COUNT(*) AS c FROM data_update_log").iloc[0]["c"]
    except Exception:
        pool_total = pool_active = raw_rows = qfq_rows = log_total = 0

    # DEBUG: show actual DB path and counts
    import os
    from config.settings import get_duckdb_path
    _dbp = str(get_duckdb_path().resolve())
    _db_exists = os.path.exists(_dbp)
    st.info(f"DEBUG — DB路径: `{_dbp}` | 文件存在: {_db_exists} | stock_pool行数: **{pool_total}** | 活跃: **{pool_active}**")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("股票池总数", f"{pool_total}", "已入库")
    k2.metric("活跃股票", f"{pool_active}", "可交易")
    k3.metric("不复权日线", f"{raw_rows:,}", "Raw")
    k4.metric("前复权日线", f"{qfq_rows:,}", "QFQ")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    #  Mid section — 40 / 60
    # ═══════════════════════════════════════════════════════════════════
    col_left, col_right = st.columns([0.4, 0.6])

    # ── Left: system status + module progress ──
    with col_left:
        # --- System status card (single markdown block, no split HTML) ---
        st.markdown(
            '<div style="background:#141d30;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:10px;padding:1.1rem 1.3rem;'
            'box-shadow:0 2px 8px rgba(0,0,0,0.3);">'
            '<div style="font-size:0.82rem;font-weight:600;color:#b0bdd0;'
            'margin-bottom:0.8rem;">系统状态</div>'
            '<div style="display:grid;grid-template-columns:auto 1fr;'
            'gap:0.45rem 1.5rem;font-size:0.78rem;">'
            '<span style="color:#7a88a6;">环境</span>'
            '<span style="color:#d0d8e8;">开发环境</span>'
            '<span style="color:#7a88a6;">数据源</span>'
            '<span style="color:#d0d8e8;">AkShare</span>'
            '<span style="color:#7a88a6;">存储</span>'
            '<span style="color:#d0d8e8;">DuckDB + Parquet</span>'
            '<span style="color:#7a88a6;">更新日志</span>'
            f'<span style="color:#d0d8e8;">{log_total} 条</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Module progress card (single markdown block) ---
        _badge_done = (
            '<span style="background:#0d3d2a;color:#3ecf8e;padding:2px 10px;'
            'border-radius:10px;font-size:0.7rem;font-weight:500;">已完成</span>'
        )
        _badge_planned = (
            '<span style="background:transparent;color:#7a88a6;padding:2px 10px;'
            'border-radius:10px;font-size:0.7rem;border:1px solid #3a4a6a;">规划中</span>'
        )
        _mod_rows = "\n".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:0.35rem 0;">'
            f'<span style="font-size:0.78rem;color:#c8d0e0;">{name}</span>'
            f'{_badge_done if done else _badge_planned}'
            f'</div>'
            for name, done in [
                ("股票池管理", True),
                ("历史数据初始化", True),
                ("每日增量更新", True),
                ("数据质量检查", False),
                ("因子分析", False),
                ("TopK 回测", False),
            ]
        )
        st.markdown(
            '<div style="background:#141d30;border:1px solid rgba(255,255,255,0.08);'
            'border-radius:10px;padding:1.1rem 1.3rem;'
            'box-shadow:0 2px 8px rgba(0,0,0,0.3);">'
            '<div style="font-size:0.82rem;font-weight:600;color:#b0bdd0;'
            'margin-bottom:0.8rem;">模块进度</div>'
            f'{_mod_rows}'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Right: recent updates ──
    with col_right:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size:0.82rem;font-weight:600;color:#b0bdd0;'
                'margin-bottom:0.1rem;">最近更新</div>',
                unsafe_allow_html=True,
            )
            st.caption("最近 10 条任务记录")
            try:
                from src.data_update.update_log import get_recent_update_logs

                logs = get_recent_update_logs(limit=10)
                if not logs.empty:
                    cols = ["stock_code", "task_type", "adj_type", "status", "row_count", "started_at"]
                    cols = [c for c in cols if c in logs.columns]
                    st.dataframe(
                        fmt_log(logs[cols]),
                        use_container_width=True, height=270,
                        key="df_overview_logs",
                        selection_mode="single-row",
                        on_select="ignore",
                    )
                else:
                    st.markdown(
                        '<div style="font-size:0.78rem;color:#5a6a8a;padding:1rem 0;">'
                        '暂无更新日志</div>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                st.markdown(
                    '<div style="font-size:0.78rem;color:#5a6a8a;padding:1rem 0;">'
                    '无法加载日志</div>',
                    unsafe_allow_html=True,
                )

# ======================================================================
#  TAB: 股票池
# ======================================================================

with t_pool:
    col_l, col_r = st.columns([1, 2.2])

    with col_l:
        st.markdown(
            '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em;'
            'color:#5a6a8a;margin-bottom:0.5rem;">操作</div>',
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            if st.button("导入股票池", use_container_width=True):
                try:
                    r = save_stock_pool_to_db(load_stock_pool_from_csv())
                    st.success(f"导入完成：新增 {r['inserted_count']}")
                except Exception as e:
                    st.error(f"导入失败：{e}")

            with st.expander("新增股票"):
                with st.form("add_form", clear_on_submit=True):
                    c = st.text_input("股票代码", placeholder="000001", key="f_code")
                    n = st.text_input("股票名称", placeholder="平安银行", key="f_name")
                    e = st.text_input("交易所", placeholder="留空自动推断", key="f_exch")
                    nt = st.text_input("备注", placeholder="可选", key="f_note")
                    if st.form_submit_button("确认新增", use_container_width=True):
                        try:
                            code = validate_stock_code(c)
                            exch = e.strip() if e.strip() else None
                            r_ = add_stock_to_pool(
                                stock_code=code, stock_name=n.strip(),
                                exchange=exch, note=nt.strip(),
                            )
                            st.success(f"新增成功：{code}")
                        except Exception as e:
                            st.error(str(e))

        try:
            pool_raw = get_stock_pool(include_inactive=True, include_blacklisted=True)
        except Exception:
            pool_raw = pd.DataFrame()

        if not pool_raw.empty:
            with st.container(border=True):
                st.caption("状态变更")
                sel = st.selectbox(
                    "选择股票", pool_raw["stock_code"].unique(),
                    label_visibility="collapsed", key="pool_sel",
                )
                if sel:
                    ca, cb, cc, cd = st.columns(4)
                    with ca:
                        if st.button("启用", use_container_width=True):
                            try:
                                st.success("已启用" if activate_stock(sel) else "未找到")
                            except Exception as e:
                                st.error(str(e))
                    with cb:
                        if st.button("停用", use_container_width=True):
                            try:
                                st.success("已停用" if deactivate_stock(sel) else "未找到")
                            except Exception as e:
                                st.error(str(e))
                    with cc:
                        if st.button("加黑", use_container_width=True):
                            try:
                                st.success("已加黑" if blacklist_stock(sel) else "未找到")
                            except Exception as e:
                                st.error(str(e))
                    with cd:
                        if st.button("解除", use_container_width=True):
                            try:
                                st.success("已解除" if remove_blacklist(sel) else "未找到")
                            except Exception as e:
                                st.error(str(e))
                    if st.button("删除", use_container_width=True, type="secondary"):
                        try:
                            st.success("已删除" if delete_stock_from_pool(sel) else "未找到")
                        except Exception as e:
                            st.error(str(e))

    with col_r:
        st.markdown(
            '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em;'
            'color:#5a6a8a;margin-bottom:0.5rem;">查询</div>',
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                pname = st.text_input("股票池", value="core_500", label_visibility="collapsed")
            with f2:
                ia = st.checkbox("未启用", value=True)
            with f3:
                ib = st.checkbox("黑名单", value=True)
            with f4:
                q = st.text_input("搜索", placeholder="代码/名称", label_visibility="collapsed")

            try:
                df_pool = get_stock_pool(
                    pool_name=pname or "core_500",
                    include_inactive=ia, include_blacklisted=ib,
                )
                if q:
                    m = df_pool["stock_code"].str.contains(q, na=False) | df_pool["stock_name"].str.contains(q, na=False)
                    df_pool = df_pool[m]

                a_cnt = int(df_pool["is_active"].sum()) if "is_active" in df_pool.columns else 0
                b_cnt = int(df_pool["is_blacklisted"].sum()) if "is_blacklisted" in df_pool.columns else 0
                st.markdown(
                    f'<span style="color:#c8d0e0;font-size:0.85rem;">'
                    f'{len(df_pool)} 只股票</span>'
                    f'<span style="color:#5a6a8a;font-size:0.78rem;margin-left:0.8rem;">'
                    f'{a_cnt} 启用 / {b_cnt} 黑名单</span>',
                    unsafe_allow_html=True,
                )
                if not df_pool.empty:
                    sc = [c for c in [
                        "stock_code", "stock_name", "market", "exchange",
                        "pool_name", "is_active", "is_blacklisted", "note",
                    ] if c in df_pool.columns]
                    st.dataframe(
                        fmt_pool(df_pool[sc]),
                        use_container_width=True, height=520,
                        key="df_pool_query",
                        selection_mode="single-row",
                        on_select="ignore",
                    )
            except Exception as e:
                st.warning(f"查询失败：{e}")

# ======================================================================
#  TAB: 数据初始化
# ======================================================================

with t_hist:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        '页面展示状态，批量任务请在命令行执行。</div>',
        unsafe_allow_html=True,
    )
    for _ in [1]:  # single-pass init
        try:
            rc = query_df("SELECT COUNT(*) AS c FROM stock_daily_raw").iloc[0]["c"]
            qc = query_df("SELECT COUNT(*) AS c FROM stock_daily_qfq").iloc[0]["c"]
            lc = query_df("SELECT COUNT(*) AS c FROM data_update_log WHERE task_type='historical_load'").iloc[0]["c"]
        except Exception:
            rc = qc = lc = 0

    from src.data_update.update_log import get_update_summary

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("不复权日线", f"{rc:,}")
    k2.metric("前复权日线", f"{qc:,}")
    k3.metric("日志", f"{lc:,}")
    try:
        s = get_update_summary("historical_load")
        k4.metric("成功", s["success"], f"失败 {s['failed']}")
    except Exception:
        k4.metric("成功", "—")

    st.markdown("<br>", unsafe_allow_html=True)
    ca, cb = st.columns([1, 1.2])

    with ca:
        with st.container(border=True):
            st.caption("状态")
            try:
                s = get_update_summary("historical_load")
                st.markdown(
                    f'<span style="color:#c8d0e0;font-size:0.8rem;">'
                    f'成功 {s["success"]}　失败 {s["failed"]}　空结果 {s["empty"]}　跳过 {s["skipped"]}</span>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown("暂无数据")
        with st.expander("命令"):
            st.code(
                "python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj all\n"
                "python -m src.data_update.retry_failed --limit 10",
                language="bash",
            )

    with cb:
        with st.container(border=True):
            st.caption("最近日志")
            try:
                logs = get_recent_update_logs(limit=30)
                if not logs.empty:
                    st.dataframe(
                        fmt_log(logs[["stock_code", "adj_type", "status", "row_count", "started_at"]]),
                        use_container_width=True, height=300,
                        key="df_hist_logs",
                        selection_mode="single-row",
                        on_select="ignore",
                    )
                else:
                    st.markdown("暂无日志")
            except Exception as e:
                st.markdown(f"加载失败：{e}")

# ======================================================================
#  TAB: 增量更新
# ======================================================================

with t_daily:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        '页面展示状态，批量任务请在命令行执行。</div>',
        unsafe_allow_html=True,
    )
    try:
        rc2 = query_df("SELECT COUNT(*) AS c FROM stock_daily_raw").iloc[0]["c"]
        qc2 = query_df("SELECT COUNT(*) AS c FROM stock_daily_qfq").iloc[0]["c"]
        lc2 = query_df("SELECT COUNT(*) AS c FROM data_update_log WHERE task_type='daily_incremental'").iloc[0]["c"]
    except Exception:
        rc2 = qc2 = lc2 = 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("不复权日线", f"{rc2:,}")
    k2.metric("前复权日线", f"{qc2:,}")
    k3.metric("增量日志", f"{lc2:,}")
    try:
        s = get_update_summary("daily_incremental")
        k4.metric("成功", s["success"], f"跳过 {s['skipped']}")
    except Exception:
        k4.metric("成功", "—")

    st.markdown("<br>", unsafe_allow_html=True)
    ca2, cb2 = st.columns([1, 1.2])

    with ca2:
        with st.container(border=True):
            st.caption("状态")
            try:
                s = get_update_summary("daily_incremental")
                st.markdown(
                    f'<span style="color:#c8d0e0;font-size:0.8rem;">'
                    f'成功 {s["success"]}　失败 {s["failed"]}　空结果 {s["empty"]}　跳过 {s["skipped"]}</span>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown("暂无数据")
        with st.expander("命令"):
            st.code(
                "python -m src.data_update.daily_incremental --pool core_500 --limit 5 --adj all\n"
                "python -m src.data_update.daily_incremental --pool core_500 --limit 3 --start-date 20260701 --end-date 20260703 --force",
                language="bash",
            )

    with cb2:
        with st.container(border=True):
            st.caption("最近日志")
            try:
                logs = get_recent_update_logs(limit=30)
                if not logs.empty:
                    inc = logs[logs["task_type"] == "daily_incremental"] if "task_type" in logs.columns else logs
                    if not inc.empty:
                        st.dataframe(
                            fmt_log(inc[["stock_code", "adj_type", "status", "row_count", "started_at"]]),
                            use_container_width=True, height=300,
                            key="df_daily_logs",
                            selection_mode="single-row",
                            on_select="ignore",
                        )
                    else:
                        st.markdown("暂无增量日志")
                else:
                    st.markdown("暂无日志")
            except Exception as e:
                st.markdown(f"加载失败：{e}")

# ======================================================================
#  TAB: 过滤结果
# ======================================================================

with t_filter:
    try:
        raw_pool = get_stock_pool(include_inactive=True, include_blacklisted=True)
    except Exception:
        raw_pool = pd.DataFrame()

    if raw_pool.empty:
        st.markdown(
            '<div style="font-size:0.8rem;color:#5a6a8a;">'
            '股票池为空，请先在「股票池」页面导入。</div>',
            unsafe_allow_html=True,
        )
    else:
        n_raw = len(raw_pool)
        n_st = len(filter_st_stocks(raw_pool))
        n_all = len(apply_basic_filters(raw_pool))

        st.markdown(
            f'<div style="font-size:0.82rem;color:#c8d0e0;margin-bottom:0.8rem;">'
            f'原始 {n_raw} 只 → ST 过滤 {n_st} 只 → 组合过滤 {n_all} 只'
            f'<span style="color:#5a6a8a;font-size:0.72rem;margin-left:0.6rem;">'
            f'（过滤 {n_raw - n_all} 只）</span></div>',
            unsafe_allow_html=True,
        )

        co, cr = st.columns(2)

        with co:
            with st.container(border=True):
                st.caption("原始股票池")
                dd = raw_pool[["stock_code", "stock_name", "is_active", "is_blacklisted"]].copy()
                st.dataframe(
                    fmt_pool(dd),
                    use_container_width=True, height=420,
                    key="df_filter_raw",
                    selection_mode="single-row",
                    on_select="ignore",
                )

        with cr:
            with st.container(border=True):
                st.caption("ST 过滤结果")
                dd2 = filter_st_stocks(raw_pool)[["stock_code", "stock_name"]].copy()
                st.dataframe(
                    fmt_pool(dd2),
                    use_container_width=True, height=420,
                    key="df_filter_st",
                    selection_mode="single-row",
                    on_select="ignore",
                )
                st.markdown(
                    f'<span style="color:#5a6a8a;font-size:0.72rem;">剩余 {n_st} 只（过滤 {n_raw - n_st} 只）</span>',
                    unsafe_allow_html=True,
                )
