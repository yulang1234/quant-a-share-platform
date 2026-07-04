"""
Streamlit UI for the Quant A-Share Research Platform.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

import pandas as pd
import streamlit as st

from config.logging_config import setup_logging
from src.storage.duckdb_repo import init_database, query_df
from src.universe.stock_pool import (
    activate_stock,
    add_stock_to_pool,
    blacklist_stock,
    deactivate_stock,
    delete_stock_from_pool,
    get_stock_pool,
    load_stock_pool_from_csv,
    lookup_stock_info,
    remove_blacklist,
    save_stock_pool_to_db,
    validate_stock_code,
)
from src.universe.filters import apply_basic_filters, filter_st_stocks
from src.data_quality.quality_report import (
    count_quality_issues,
    get_quality_issue_summary,
    get_recent_quality_issues,
)

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
    "sector": "板块/行业",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "task_type": "任务类型",
    "adj_type": "复权类型",
    "status": "执行状态",
    "row_count": "行数",
    "started_at": "开始时间",
    "finished_at": "完成时间",
    "error_message": "错误信息",
    "check_date": "检查日期",
    "issue_type": "问题类型",
    "issue_level": "严重程度",
    "issue_detail": "问题详情",
}

_TASK_CN = {"historical_load": "历史初始化", "daily_incremental": "增量更新"}
_ADJ_CN = {"raw": "不复权", "qfq": "前复权"}
_STAT_CN = {"success": "成功", "failed": "失败", "empty": "空结果", "skipped": "跳过"}
_ISSUE_TYPE_CN = {
    "duplicate_record": "重复记录",
    "missing_trade_date": "缺失交易日",
    "price_anomaly": "价格异常",
}
_ISSUE_LEVEL_CN = {"high": "高", "medium": "中", "low": "低"}


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
    # Replace None with empty string for display
    for col in ("note", "sector"):
        if col in d.columns:
            d[col] = d[col].fillna("").astype(str)
    return fmt_cols(d)


# ======================================================================
#  Page setup
# ======================================================================

setup_logging()
_log = logging.getLogger("streamlit")

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

TAB_NAMES = ["总览", "股票池", "数据初始化", "增量更新", "过滤结果", "数据质量", "数据修复", "基础因子", "因子排名", "因子有效性", "TopK选股", "基础回测", "回测评价体系", "多因子评分", "命令手册", "风险提示"]
t_overview, t_pool, t_hist, t_daily, t_filter, t_quality, t_repair, t_factors, t_ranks, t_analysis, t_topk, t_backtest, t_backtest_eval, t_scoring, t_commands, t_disclaimer = st.tabs(TAB_NAMES)

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
            'border-radius:12px;padding:3px 12px;font-size:0.7rem;color:#9aa6bd;">v1.0.0</span>'
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
    #  V1.4 Pipeline status — key data tables snapshot
    # ═══════════════════════════════════════════════════════════════════
    try:
        from ui.components.ui_helpers import safe_metric, safe_fetch_latest_date
        _pipeline_data = [
            ("stock_pool", "股票池"),
            ("stock_daily_qfq", "qfq 行情"),
            ("stock_daily_factors", "基础因子"),
            ("stock_factor_rank", "因子排名"),
            ("factor_analysis_summary", "因子分析"),
            ("strategy_selection_result", "候选股票"),
            ("backtest_equity_curve", "回测曲线"),
            ("backtest_performance_summary", "回测评价"),
            ("stock_composite_score", "综合评分"),
        ]
        _p1, _p2, _p3 = st.columns(3)
        for i, (tbl, lbl) in enumerate(_pipeline_data):
            col = [_p1, _p2, _p3][i % 3]
            cnt = safe_metric(lbl, tbl)
            col.metric(lbl, cnt)
        _latest_qfq = safe_fetch_latest_date("stock_daily_qfq") or "--"
        _latest_factor = safe_fetch_latest_date("stock_daily_factors") or "--"
        _latest_rank = safe_fetch_latest_date("stock_factor_rank") or "--"
        st.caption(f"最新行情: {_latest_qfq} | 最新因子: {_latest_factor} | 最新排名: {_latest_rank}")
    except Exception:
        pass

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
                    _log.info("导入股票池 | inserted=%d updated=%d", r["inserted_count"], r["updated_count"])
                    st.success(f"导入完成：新增 {r['inserted_count']}")
                except Exception as e:
                    _log.warning("导入股票池失败 | error=%s", e)
                    st.error(f"导入失败：{e}")

            with st.expander("新增股票"):
                # ── Simple form: only code + note + button ─────────
                _F_KEYS = ["f_code", "f_note"]

                if st.session_state.pop("_reset_add_stock_form", False):
                    for k in _F_KEYS:
                        st.session_state[k] = ""

                for k in _F_KEYS:
                    if k not in st.session_state:
                        st.session_state[k] = ""

                c = st.text_input("股票代码", placeholder="000001 / 688007", key="f_code")
                nt = st.text_input("备注", placeholder="可选", key="f_note")

                if st.button("确认新增", use_container_width=True):
                    try:
                        code = validate_stock_code(c)
                        note = nt.strip()
                        info = lookup_stock_info(code)
                        is_fallback_name = (info["stock_name"] == "待补充")
                        _log.info(
                            "新增股票 | code=%s | name=%s | sector=%s | source=%s | fallback=%s",
                            code, info["stock_name"],
                            info["sector"] or "(空)", info["sector_source"],
                            is_fallback_name,
                        )
                        r_ = add_stock_to_pool(
                            stock_code=code,
                            stock_name=info["stock_name"],
                            exchange=info["exchange"],
                            sector=info["sector"],
                            note=note,
                        )
                        _log.info("新增成功 | code=%s | action=%s", code, r_["action"])
                        st.session_state["_reset_add_stock_form"] = True
                        # Build success message
                        name_part = info["stock_name"]
                        if info["sector"]:
                            sector_part = f"板块/行业：{info["sector"]}"
                        else:
                            sector_part = "板块/行业待补充"
                        st.session_state["_add_msg"] = (
                            f"新增成功：{code} {name_part} | {sector_part}"
                        )
                        st.rerun()
                    except Exception as ex:
                        _log.warning("新增失败 | code=%s | error=%s", c.strip() if c else "", ex)
                        st.error(str(ex))

                msg = st.session_state.pop("_add_msg", "")
                if msg:
                    st.success(msg)

            # ── Batch sector repair button ────────────────────────────
            with st.expander("批量补齐板块/行业"):
                if st.button("执行批量补齐", use_container_width=True):
                    try:
                        from src.universe.repair_sector import repair_sectors
                        with st.spinner("正在扫描并补齐板块/行业…"):
                            result = repair_sectors(dry_run=False)
                        total = result["total"]
                        repaired = result["repaired"]
                        skipped = result["skipped"]
                        if total == 0:
                            st.info("所有股票的板块/行业已补齐，无需操作。")
                        else:
                            st.success(
                                f"补齐完成：共 {total} 只待补齐，"
                                f"成功 {repaired} 只，跳过 {skipped} 只"
                            )
                        _log.info(
                            "批量补齐完成 | total=%d repaired=%d skipped=%d",
                            total, repaired, skipped,
                        )
                    except Exception as ex:
                        msg = str(ex).lower()
                        if any(s in msg for s in ("cannot open", "being used", "另一个程序")):
                            st.warning("数据库正被占用，请关闭 Streamlit 后用命令行运行：`python -m src.universe.repair_sector`")
                        else:
                            st.error(f"补齐失败：{ex}")
                        _log.warning("批量补齐失败 | error=%s", ex)

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
                        "pool_name", "is_active", "is_blacklisted", "note", "sector",
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

# ======================================================================
#  TAB: 数据质量
# ======================================================================

with t_quality:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        '页面展示状态，批量检查请在命令行执行。V0.5 只检查不修复。</div>',
        unsafe_allow_html=True,
    )

    try:
        total_open = count_quality_issues(status="open")
        raw_open = count_quality_issues(adj_type="raw", status="open")
        qfq_open = count_quality_issues(adj_type="qfq", status="open")
        dup_open = count_quality_issues(issue_type="duplicate_record", status="open")
        miss_open = count_quality_issues(issue_type="missing_trade_date", status="open")
        price_open = count_quality_issues(issue_type="price_anomaly", status="open")
    except Exception:
        total_open = raw_open = qfq_open = dup_open = miss_open = price_open = 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("待处理问题", f"{total_open}")
    k2.metric("不复权问题", f"{raw_open}")
    k3.metric("前复权问题", f"{qfq_open}")
    k4.metric("价格异常", f"{price_open}")

    st.markdown("<br>", unsafe_allow_html=True)

    ca, cb = st.columns([1, 1.2])

    with ca:
        with st.container(border=True):
            st.caption("分类统计")
            try:
                summary = get_quality_issue_summary()
                if summary["total_open_issues"]:
                    rows = "<br>".join(
                        f'<span style="color:#c8d0e0;font-size:0.78rem;">'
                        f'{_ISSUE_TYPE_CN.get(r["issue_type"], r["issue_type"])} '
                        f'({_ADJ_CN.get(r["adj_type"], r["adj_type"])}) : '
                        f'{r["issue_count"]}</span>'
                        for r in summary["by_type_adj"]
                    )
                    st.markdown(rows, unsafe_allow_html=True)
                else:
                    st.markdown("暂无未处理问题")
            except Exception:
                st.markdown("暂无数据")

        with st.expander("命令"):
            st.code(
                "python -m src.data_quality.quality_report --adj raw --limit 5\n"
                "python -m src.data_quality.quality_report --adj qfq --limit 5\n"
                "python -m src.data_quality.quality_report --adj all --limit 20\n"
                "python -m src.data_quality.quality_report --stock-code 000001 --adj raw\n"
                "python -m src.data_quality.quality_report --adj all --no-write",
                language="bash",
            )

    with cb:
        with st.container(border=True):
            st.caption("最近问题")
            try:
                issues = get_recent_quality_issues(limit=20)
                if not issues.empty:
                    display_cols = [
                        "stock_code", "check_date", "issue_type",
                        "issue_level", "adj_type", "issue_detail",
                    ]
                    display_cols = [c for c in display_cols if c in issues.columns]
                    display_df = issues[display_cols].copy()
                    display_df["issue_type"] = display_df["issue_type"].map(_ISSUE_TYPE_CN).fillna(display_df["issue_type"])
                    display_df["issue_level"] = display_df["issue_level"].map(_ISSUE_LEVEL_CN).fillna(display_df["issue_level"])
                    display_df["adj_type"] = display_df["adj_type"].map(_ADJ_CN).fillna(display_df["adj_type"])
                    display_df = display_df.rename(columns={k: v for k, v in _COL_CN.items() if k in display_df.columns})
                    st.dataframe(
                        display_df,
                        use_container_width=True, height=320,
                        key="df_quality_issues",
                        selection_mode="single-row",
                        on_select="ignore",
                    )
                else:
                    st.markdown("暂无质量问题记录")
            except Exception as e:
                st.markdown(f"加载失败：{e}")

# ======================================================================
#  TAB: 数据修复 (V0.6)
# ======================================================================

with t_repair:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V0.6 数据修复与重跑 -- 基于质量检查结果做安全修复。'
        '所有操作默认 dry-run，需 --confirm 才真实执行。</div>',
        unsafe_allow_html=True,
    )

    try:
        from src.data_repair.repair_log import get_recent_repair_logs, get_repair_summary
        summary = get_repair_summary()
        logs = get_recent_repair_logs(limit=20)
    except Exception:
        summary = {"total_logs": 0, "by_status": [], "by_action": []}
        logs = pd.DataFrame()

    k1, k2, k3 = st.columns(3)
    k1.metric("修复日志总数", summary.get("total_logs", 0))
    success_count = sum(r["cnt"] for r in summary.get("by_status", []) if r["status"] == "success")
    k2.metric("成功修复", success_count)
    dry_count = sum(r["cnt"] for r in summary.get("by_status", []) if r["status"] == "dry_run")
    k3.metric("Dry-run", dry_count)

    st.markdown("<br>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])

    with cl:
        with st.container(border=True):
            st.caption("状态汇总")
            if summary["by_status"]:
                for r in summary["by_status"]:
                    st.markdown(f'<span style="color:#c8d0e0;font-size:0.78rem;">{r["status"]}: {r["cnt"]}</span>', unsafe_allow_html=True)
            else:
                st.markdown("暂无修复记录")
        with st.container(border=True):
            st.caption("操作汇总")
            if summary["by_action"]:
                for r in summary["by_action"]:
                    st.markdown(f'<span style="color:#c8d0e0;font-size:0.78rem;">{r["repair_action"]}: {r["cnt"]}</span>', unsafe_allow_html=True)
            else:
                st.markdown("暂无操作记录")

    with cr:
        with st.container(border=True):
            st.caption("最近修复日志")
            if not logs.empty:
                dc = [c for c in ["stock_code", "repair_action", "adj_type", "status", "affected_rows", "created_at"] if c in logs.columns]
                st.dataframe(logs[dc], use_container_width=True, height=280, key="df_repair_logs", selection_mode="single-row", on_select="ignore")
            else:
                st.markdown("暂无修复日志")

    with st.expander("命令行示例"):
        st.code(
            "# 生成修复计划\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action plan --dry-run\n\n"
            "# dry-run 去重\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action deduplicate --adj all --dry-run\n\n"
            "# 真实去重\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action deduplicate --adj all --no-dry-run --confirm\n\n"
            "# dry-run 重拉区间\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj raw --action refetch --start-date 20260701 --end-date 20260703 --dry-run\n\n"
            "# 真实重拉\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj raw --action refetch --start-date 20260701 --end-date 20260703 --no-dry-run --confirm\n\n"
            "# 真实重建 Parquet\n"
            "python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj all --action rebuild-parquet --no-dry-run --confirm",
            language="bash",
        )

# ======================================================================
#  TAB: 基础因子 (V0.7)
# ======================================================================

with t_factors:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V0.7 基础因子计算 -- 基于 qfq 日线数据计算。不做标准化、排名、有效性分析。</div>',
        unsafe_allow_html=True,
    )

    try:
        from src.storage.duckdb_repo import fetch_daily_factors, query_df
        fac = fetch_daily_factors(limit=5)
        total = query_df("SELECT COUNT(*) AS c FROM stock_daily_factors")
        total_rows = int(total.iloc[0]["c"]) if not total.empty else 0
        stocks = query_df("SELECT COUNT(DISTINCT stock_code) AS c FROM stock_daily_factors")
        stock_count = int(stocks.iloc[0]["c"]) if not stocks.empty else 0
    except Exception:
        fac = pd.DataFrame()
        total_rows = 0
        stock_count = 0

    k1, k2 = st.columns(2)
    k1.metric("因子总行数", total_rows)
    k2.metric("覆盖股票数", stock_count)

    if not fac.empty:
        st.caption("最近因子样例")
        st.dataframe(fac.head(5), use_container_width=True, height=200,
                     key="df_factors_sample", selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无因子数据。请运行 CLI 生成：\n\n"
                "python -m src.factors.run_factor_calculation --pool core_500 --limit 5")

    with st.expander("命令行示例"):
        st.code(
            "# 小批量因子计算\n"
            "python -m src.factors.run_factor_calculation --pool core_500 --limit 5\n\n"
            "# 单只股票因子计算\n"
            "python -m src.factors.run_factor_calculation --stock-code 000001\n\n"
            "# 指定日期范围\n"
            "python -m src.factors.run_factor_calculation --stock-code 000001 --start-date 20200101 --end-date 20231231",
            language="bash",
        )

# ======================================================================
#  TAB: 因子排名 (V0.8)
# ======================================================================

with t_ranks:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V0.8 因子标准化与排名 -- 横截面去极值、z-score、方向处理、排名。</div>',
        unsafe_allow_html=True,
    )

    try:
        from src.storage.duckdb_repo import fetch_factor_rankings, query_df
        ranks = fetch_factor_rankings(limit=10)
        total_r = query_df("SELECT COUNT(*) AS c FROM stock_factor_rank")
        total_rows = int(total_r.iloc[0]["c"]) if not total_r.empty else 0
        stk_r = query_df("SELECT COUNT(DISTINCT stock_code) AS c FROM stock_factor_rank")
        stock_count = int(stk_r.iloc[0]["c"]) if not stk_r.empty else 0
        fac_r = query_df("SELECT COUNT(DISTINCT factor_name) AS c FROM stock_factor_rank")
        factor_count = int(fac_r.iloc[0]["c"]) if not fac_r.empty else 0
    except Exception:
        ranks = pd.DataFrame()
        total_rows = stock_count = factor_count = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("排名总行数", total_rows)
    k2.metric("覆盖股票数", stock_count)
    k3.metric("覆盖因子数", factor_count)

    if not ranks.empty:
        st.caption("最近排名样例")
        dc = [c for c in ["stock_code", "trade_date", "factor_name", "raw_value", "rank_value", "percentile_rank"] if c in ranks.columns]
        st.dataframe(ranks[dc].head(10), use_container_width=True, height=250,
                     key="df_ranks_sample", selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无排名数据。")

    with st.expander("命令行示例"):
        st.code(
            "# 小批量计算因子排名\n"
            "python -m src.factor_rank.run_factor_ranking --pool core_500 --limit 5\n\n"
            "# 指定因子排名\n"
            "python -m src.factor_rank.run_factor_ranking --factor-name return_20d --limit 5\n\n"
            "# 指定交易日排名\n"
            "python -m src.factor_rank.run_factor_ranking --trade-date 20260703\n\n"
            "# 指定日期范围\n"
            "python -m src.factor_rank.run_factor_ranking --start-date 20260101 --end-date 20260703 --limit 5",
            language="bash",
        )

# ======================================================================
#  TAB: 因子有效性 (V0.9)
# ======================================================================

with t_analysis:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V0.9 因子有效性分析 -- IC/RankIC/分组收益/汇总报告。</div>',
        unsafe_allow_html=True,
    )

    try:
        from src.storage.duckdb_repo import fetch_analysis_summary, query_df
        s = fetch_analysis_summary(limit=20)
        total = query_df("SELECT COUNT(*) AS c FROM factor_analysis_summary")
        total_rows = int(total.iloc[0]["c"]) if not total.empty else 0
        facs = query_df("SELECT COUNT(DISTINCT factor_name) AS c FROM factor_analysis_summary")
        factor_count = int(facs.iloc[0]["c"]) if not facs.empty else 0
    except Exception:
        s = pd.DataFrame(); total_rows = factor_count = 0

    k1, k2 = st.columns(2)
    k1.metric("汇总报告数", total_rows)
    k2.metric("已分析因子数", factor_count)

    if not s.empty:
        st.caption("分析汇总（按 avg_rank_ic 排序）")
        dc = [c for c in ["factor_name", "forward_days", "avg_ic", "avg_rank_ic", "ic_ir", "avg_group_spread", "trade_date_count"] if c in s.columns]
        st.dataframe(s[dc].sort_values("avg_rank_ic", ascending=False).head(20) if "avg_rank_ic" in dc else s[dc].head(20),
                     use_container_width=True, height=300, key="df_analysis_summary", selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无分析数据。")

    with st.expander("命令行示例"):
        st.code(
            "# 小批量因子有效性分析\n"
            "python -m src.factor_analysis.run_factor_analysis --pool core_500 --limit 5\n\n"
            "# 指定因子分析\n"
            "python -m src.factor_analysis.run_factor_analysis --factor-name return_20d --forward-days 5 --limit 5\n\n"
            "# 指定日期范围和未来收益周期\n"
            "python -m src.factor_analysis.run_factor_analysis --factor-name return_20d --start-date 20200101 --end-date 20231231 --forward-days 10",
            language="bash",
        )

# ======================================================================
#  TAB: TopK 选股 (V1.0)
# ======================================================================

with t_topk:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V1.0 TopK 选股策略 -- 单因子/多因子加权 TopK 候选股票生成。'
        '结果仅供参考，不构成投资建议。</div>',
        unsafe_allow_html=True,
    )
    try:
        from src.storage.duckdb_repo import fetch_strategy_selection_result, query_df
        sel = fetch_strategy_selection_result(limit=20)
        total = query_df("SELECT COUNT(*) AS c FROM strategy_selection_result")
        total_rows = int(total.iloc[0]["c"]) if not total.empty else 0
        strats = query_df("SELECT COUNT(DISTINCT strategy_name) AS c FROM strategy_selection_result")
        strat_count = int(strats.iloc[0]["c"]) if not strats.empty else 0
    except Exception:
        sel = pd.DataFrame(); total_rows = strat_count = 0

    k1, k2 = st.columns(2)
    k1.metric("候选股结果数", total_rows)
    k2.metric("已运行策略数", strat_count)

    if not sel.empty:
        st.caption("最近候选股 TopK")
        dc = [c for c in ["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score"] if c in sel.columns]
        st.dataframe(sel[dc].head(20), use_container_width=True, height=250, key="df_topk_sample", selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无候选股数据。")

    with st.expander("命令行示例"):
        st.code(
            "# 默认单因子策略\n"
            "python -m src.strategy.run_topk_strategy --strategy single_return_20d_top20 --limit 5\n\n"
            "# 临时单因子\n"
            "python -m src.strategy.run_topk_strategy --factor-name return_20d --top-k 20 --limit 5\n\n"
            "# 临时多因子\n"
            "python -m src.strategy.run_topk_strategy --factor-weights \"{\\\"return_20d\\\":0.5,\\\"momentum_20d\\\":0.5}\" --top-k 20 --limit 5",
            language="bash",
        )

# ======================================================================
#  TAB: 基础回测 (V1.1)
# ======================================================================

with t_backtest:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V1.1 基础回测 -- 持仓/每日收益/资金曲线。V1.2 才做评价指标。不构成投资建议。</div>',
        unsafe_allow_html=True,
    )
    try:
        from src.storage.duckdb_repo import fetch_backtest_config, fetch_backtest_daily_returns, fetch_backtest_equity_curve
        cfgs = fetch_backtest_config()
        rets = fetch_backtest_daily_returns(limit=10)
        eqs = fetch_backtest_equity_curve(limit=10)
    except Exception:
        cfgs = pd.DataFrame(); rets = pd.DataFrame(); eqs = pd.DataFrame()

    k1, k2, k3 = st.columns(3)
    k1.metric("回测配置数", len(cfgs))
    k2.metric("每日收益行", len(rets))
    k3.metric("资金曲线行", len(eqs))

    if not eqs.empty:
        st.caption("最近资金曲线")
        dc = [c for c in ["backtest_name", "trade_date", "equity"] if c in eqs.columns]
        st.dataframe(eqs[dc].head(10), use_container_width=True, height=200, key="df_bt_eq")
    elif not cfgs.empty:
        st.caption("最近回测配置")
        dc = [c for c in ["backtest_name", "strategy_name", "initial_cash", "top_k", "rebalance_frequency"] if c in cfgs.columns]
        st.dataframe(cfgs[dc].head(5), use_container_width=True, height=150, key="df_bt_cfg")
    else:
        st.info("暂无回测数据。")

    with st.expander("命令行示例"):
        st.code(
            "# 默认基础回测\n"
            "python -m src.backtest.run_backtest --strategy single_return_20d_top20 --limit 5\n\n"
            "# 自定义参数\n"
            "python -m src.backtest.run_backtest --strategy single_return_20d_top20 --initial-cash 500000 --top-k 10 --rebalance-frequency weekly --limit 5",
            language="bash",
        )

# ======================================================================
#  TAB: 回测评价体系 (V1.2)
# ======================================================================

with t_backtest_eval:
    st.markdown(
        '<div style="font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;">'
        'V1.2 回测评价体系 -- 绩效指标/回撤序列/月度收益/年度收益。'
        '页面只展示结果，不执行全量任务；回测结果不构成投资建议。</div>',
        unsafe_allow_html=True,
    )
    try:
        from src.storage.duckdb_repo import (
            fetch_backtest_drawdown_series,
            fetch_backtest_monthly_return,
            fetch_backtest_performance_summary,
            fetch_backtest_yearly_return,
            query_df,
        )
        perf_total = int(query_df("SELECT COUNT(*) AS c FROM backtest_performance_summary").iloc[0]["c"])
        dd_total = int(query_df("SELECT COUNT(*) AS c FROM backtest_drawdown_series").iloc[0]["c"])
        monthly_total = int(query_df("SELECT COUNT(*) AS c FROM backtest_monthly_return").iloc[0]["c"])
        yearly_total = int(query_df("SELECT COUNT(*) AS c FROM backtest_yearly_return").iloc[0]["c"])
        perf = fetch_backtest_performance_summary(limit=10)
        dd = fetch_backtest_drawdown_series(limit=10)
        monthly = fetch_backtest_monthly_return(limit=10)
        yearly = fetch_backtest_yearly_return(limit=10)
    except Exception:
        perf_total = dd_total = monthly_total = yearly_total = 0
        perf = pd.DataFrame(); dd = pd.DataFrame(); monthly = pd.DataFrame(); yearly = pd.DataFrame()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("绩效汇总行", perf_total)
    k2.metric("回撤序列行", dd_total)
    k3.metric("月度收益行", monthly_total)
    k4.metric("年度收益行", yearly_total)

    st.caption("最近 performance summary")
    if not perf.empty:
        cols = [c for c in ["backtest_name", "start_date", "end_date", "total_return", "annualized_return", "max_drawdown", "sharpe_ratio", "calmar_ratio"] if c in perf.columns]
        st.dataframe(perf[cols], use_container_width=True, height=180, key="df_bt_eval_perf")
    else:
        st.info("暂无绩效汇总数据。")

    st.caption("最近 drawdown series")
    if not dd.empty:
        cols = [c for c in ["backtest_name", "trade_date", "equity", "running_max_equity", "drawdown"] if c in dd.columns]
        st.dataframe(dd[cols], use_container_width=True, height=180, key="df_bt_eval_dd")
    else:
        st.info("暂无回撤序列数据。")

    st.caption("最近 monthly return")
    if not monthly.empty:
        cols = [c for c in ["backtest_name", "year_month", "monthly_return", "start_equity", "end_equity", "trading_days"] if c in monthly.columns]
        st.dataframe(monthly[cols], use_container_width=True, height=180, key="df_bt_eval_monthly")
    else:
        st.info("暂无月度收益数据。")

    st.caption("最近 yearly return")
    if not yearly.empty:
        cols = [c for c in ["backtest_name", "year", "yearly_return", "start_equity", "end_equity", "trading_days"] if c in yearly.columns]
        st.dataframe(yearly[cols], use_container_width=True, height=180, key="df_bt_eval_yearly")
    else:
        st.info("暂无年度收益数据。")

    with st.expander("命令行示例"):
        st.code(
            "python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt\n\n"
            "python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt --risk-free-rate 0.02\n\n"
            "python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt --start-date 20200101 --end-date 20231231",
            language="bash",
        )


# ======================================================================
#  TAB: 多因子评分 (V1.3)
# ======================================================================

with t_scoring:
    st.markdown(
        "<div style='font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;'>"
        "V1.3 多因子评分系统 -- 综合评分/排名/因子明细。不构成投资建议。</div>",
        unsafe_allow_html=True,
    )
    try:
        from src.storage.duckdb_repo import fetch_stock_composite_score, fetch_stock_score_detail, query_df
        comp = fetch_stock_composite_score(limit=20)
        det = fetch_stock_score_detail(limit=20)
        total = query_df("SELECT COUNT(*) AS c FROM stock_composite_score")
        total_rows = int(total.iloc[0]["c"]) if not total.empty else 0
        models = query_df("SELECT COUNT(DISTINCT model_name) AS c FROM stock_composite_score")
        model_count = int(models.iloc[0]["c"]) if not models.empty else 0
    except Exception:
        comp = pd.DataFrame(); det = pd.DataFrame(); total_rows = model_count = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("综合评分行数", total_rows)
    k2.metric("评分模型数", model_count)
    k3.metric("评分明细行", len(det))

    if not comp.empty:
        st.caption("最近综合评分 TopK")
        dc = [c for c in ["model_name","trade_date","stock_code","composite_score","score_rank","factor_coverage_ratio"] if c in comp.columns]
        st.dataframe(comp[dc].head(20), use_container_width=True, height=250, key="df_scoring_sample", selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无评分数据。")

    with st.expander("命令行示例"):
        st.code(
            "# 动量质量评分模型\n"
            "python -m src.scoring.run_scoring --model momentum_quality_score --limit 5\n\n"
            "# 趋势量能评分模型\n"
            "python -m src.scoring.run_scoring --model trend_volume_score --limit 5\n\n"
            "# 低波稳定评分模型\n"
            "python -m src.scoring.run_scoring --model low_vol_stable_score --trade-date 20260703",
            language="bash",
        )

# ======================================================================
#  TAB: 命令手册 (V1.4)
# ======================================================================

with t_commands:
    st.markdown("<div style='font-size:0.78rem;color:#5a6a8a;margin-bottom:0.8rem;'>常用命令行参考 -- 所有命令默认 dry-run 安全</div>", unsafe_allow_html=True)
    commands = [
        ("数据更新", "python -m src.data_update.historical_loader --pool core_500 --adj qfq --limit 5"),
        ("数据质量", "python -m src.data_quality.quality_report --adj qfq --limit 5"),
        ("数据修复", "python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action plan --dry-run"),
        ("因子计算", "python -m src.factors.run_factor_calculation --pool core_500 --limit 5"),
        ("因子排名", "python -m src.factor_rank.run_factor_ranking --pool core_500 --limit 5"),
        ("因子分析", "python -m src.factor_analysis.run_factor_analysis --pool core_500 --limit 5"),
        ("TopK 选股", "python -m src.strategy.run_topk_strategy --strategy single_return_20d_top20 --limit 5"),
        ("基础回测", "python -m src.backtest.run_backtest --strategy single_return_20d_top20 --limit 5"),
        ("回测评价", "python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt"),
        ("多因子评分", "python -m src.scoring.run_scoring --model momentum_quality_score --limit 5"),
    ]
    for name, cmd in commands:
        with st.expander(name):
            st.code(cmd, language="bash")

# ======================================================================
#  TAB: 风险提示 (V1.4)
# ======================================================================

with t_disclaimer:
    st.markdown("""<div style="background:#141d30;border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:1.5rem;">
<h3 style="color:#f0f4ff;">风险提示</h3>
<ul style="color:#9aa6bd;font-size:0.82rem;line-height:1.8;">
<li>本平台仅用于个人量化研究</li>
<li>所有评分、回测、评价结果不构成投资建议</li>
<li>历史回测不代表未来收益</li>
<li>数据可能存在缺失、延迟、错误</li>
<li>任何交易决策需要用户独立判断</li>
<li>本项目不提供自动交易能力</li>
<li>本项目不接券商 API</li>
<li>本项目不会自动下单</li>
</ul>
</div>""", unsafe_allow_html=True)
