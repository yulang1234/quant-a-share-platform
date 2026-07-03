"""
Streamlit UI for the Quant A-Share Research Platform.

Run with::

    streamlit run ui/streamlit_app.py
"""

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
    infer_exchange,
    load_stock_pool_from_csv,
    remove_blacklist,
    save_stock_pool_to_db,
    validate_stock_code,
)
from src.universe.filters import filter_st_stocks

# ── Column display names ─────────────────────────────────────────────
_COLUMN_LABELS: dict[str, str] = {
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "market": "市场",
    "exchange": "交易所",
    "pool_name": "股票池",
    "source": "来源",
    "is_active": "启用状态",
    "is_blacklisted": "黑名单",
    "note": "备注",
    "created_at": "创建时间",
    "updated_at": "更新时间",
}


def _label_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename DataFrame columns to Chinese labels for display."""
    rename = {k: v for k, v in _COLUMN_LABELS.items() if k in df.columns}
    return df.rename(columns=rename)


# ── Page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="A股量化研究平台",
    page_icon="📈",
    layout="wide",
)

st.title("📈 A股量化研究平台")
st.markdown("**A股 500 支核心股票池量化研究平台**")

init_database()

# ── Tab navigation ──────────────────────────────────────────────────────
tab_overview, tab_pool_mgmt, tab_filters, tab_hist_data = st.tabs([
    "📊 项目概览",
    "📂 股票池管理",
    "🔍 过滤测试",
    "📜 历史数据初始化",
])

# =====================================================================
#  TAB 1 — 项目概览
# =====================================================================
with tab_overview:
    col1, col2 = st.columns(2)
    with col1:
        st.metric("当前版本", "V0.3")
        st.caption("20 年历史数据初始化")
    with col2:
        st.metric("当前阶段", "历史数据初始化")
        st.caption("已完成：股票池管理 + 历史数据拉取")

    st.divider()
    st.subheader("后续模块入口")
    modules = [
        "股票池管理 ✅",
        "历史数据初始化 ✅",
        "每日增量更新",
        "数据质量检查",
        "因子分析",
        "TopK 回测",
        "Qlib 研究",
        "AI 分析报告",
    ]
    for m in modules:
        st.info(m)

    st.divider()
    st.subheader("⚠️ 风险提示")
    st.warning("本项目仅用于个人量化研究和学习。不构成任何投资建议。不进行自动下单。不接入实盘交易。")

# =====================================================================
#  TAB 2 — 股票池管理
# =====================================================================
with tab_pool_mgmt:
    st.subheader("📂 股票池管理")

    # ── Side actions ─────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("**导入股票池**")
        if st.button("📥 导入 core_500.csv", use_container_width=True):
            try:
                df = load_stock_pool_from_csv()
                result = save_stock_pool_to_db(df)
                st.success(
                    f"导入完成: {result['inserted_count']} 新增, "
                    f"{result['updated_count']} 更新, "
                    f"共 {result['total_count']} 条"
                )
            except Exception as e:
                st.error(f"导入失败: {e}")

        st.divider()

        st.markdown("**添加单只股票**")
        with st.form("add_stock_form", clear_on_submit=True):
            code_input = st.text_input("股票代码", placeholder="000001")
            name_input = st.text_input("股票名称", placeholder="平安银行")
            exchange_input = st.text_input(
                "交易所 (留空自动推断)", placeholder="SZ / SH / BJ"
            )
            note_input = st.text_input("备注", placeholder="可选")
            submitted = st.form_submit_button("➕ 添加", use_container_width=True)

            if submitted:
                try:
                    code = validate_stock_code(code_input)
                    exch = exchange_input.strip() if exchange_input.strip() else None
                    result = add_stock_to_pool(
                        stock_code=code,
                        stock_name=name_input.strip(),
                        exchange=exch,
                        note=note_input.strip(),
                    )
                    st.success(f"{result['action']}: {code} {name_input}")
                except Exception as e:
                    st.error(f"添加失败: {e}")

    # ── Main table area ──────────────────────────────────────────────
    with col_right:
        st.markdown("**筛选条件**")
        filter_cols = st.columns(4)
        with filter_cols[0]:
            pool_filter = st.text_input("股票池名称", value="core_500")
        with filter_cols[1]:
            incl_inactive = st.checkbox("包含未启用", value=True)
        with filter_cols[2]:
            incl_blacklisted = st.checkbox("包含黑名单", value=True)
        with filter_cols[3]:
            search = st.text_input("搜索代码/名称", placeholder="输入关键词")

        try:
            df_pool = get_stock_pool(
                pool_name=pool_filter or "core_500",
                include_inactive=incl_inactive,
                include_blacklisted=incl_blacklisted,
            )

            if search:
                mask = (
                    df_pool["stock_code"].str.contains(search, na=False)
                    | df_pool["stock_name"].str.contains(search, na=False)
                )
                df_pool = df_pool[mask]

            st.markdown(f"**共 {len(df_pool)} 条记录**")

            # Display with custom formatting
            if not df_pool.empty:
                display_cols = [
                    "stock_code", "stock_name", "market", "exchange",
                    "pool_name", "is_active", "is_blacklisted",
                    "note", "updated_at",
                ]
                display_cols = [c for c in display_cols if c in df_pool.columns]

                # Format booleans for display
                df_display = df_pool[display_cols].copy()
                if "is_active" in df_display.columns:
                    df_display["is_active"] = df_display["is_active"].apply(
                        lambda x: "✅ 启用" if x else "❌ 停用"
                    )
                if "is_blacklisted" in df_display.columns:
                    df_display["is_blacklisted"] = df_display["is_blacklisted"].apply(
                        lambda x: "⛔ 是" if x else "✅ 否"
                    )
                # Rename columns to Chinese labels
                df_display = _label_columns(df_display)
                st.dataframe(df_display, use_container_width=True, height=400)

        except Exception as e:
            st.warning(f"查询失败 (可能股票池为空): {e}")

    # ── Stock actions ────────────────────────────────────────────────
    st.divider()
    col_act1, col_act2, col_act3, col_act4, col_act5 = st.columns(5)

    if not df_pool.empty:
        all_codes = df_pool["stock_code"].unique().tolist()
    else:
        all_codes = []

    with col_act1:
        sel_code = st.selectbox("选择股票代码", options=all_codes, key="action_code")

    with col_act2:
        if st.button("✅ 激活", use_container_width=True) and sel_code:
            try:
                ok = activate_stock(sel_code)
                st.success(f"{sel_code} 已激活" if ok else f"{sel_code} 未找到")
            except Exception as e:
                st.error(str(e))

    with col_act3:
        if st.button("⏸️ 停用", use_container_width=True) and sel_code:
            try:
                ok = deactivate_stock(sel_code)
                st.success(f"{sel_code} 已停用" if ok else f"{sel_code} 未找到")
            except Exception as e:
                st.error(str(e))

    with col_act4:
        if st.button("⛔ 加入黑名单", use_container_width=True) and sel_code:
            try:
                ok = blacklist_stock(sel_code)
                st.success(f"{sel_code} 已加入黑名单" if ok else f"{sel_code} 未找到")
            except Exception as e:
                st.error(str(e))

    with col_act5:
        if st.button("✅ 移出黑名单", use_container_width=True) and sel_code:
            try:
                ok = remove_blacklist(sel_code)
                st.success(f"{sel_code} 已移出黑名单" if ok else f"{sel_code} 未找到")
            except Exception as e:
                st.error(str(e))

    # ── Delete (with confirmation) ───────────────────────────────────
    col_del1, col_del2, _ = st.columns([1, 1, 4])
    with col_del1:
        sel_del_code = st.selectbox("选择要删除的股票", options=all_codes, key="del_code")
    with col_del2:
        if st.button("🗑️ 物理删除", use_container_width=True) and sel_del_code:
            if st.checkbox(f"确认删除 {sel_del_code}？", key="confirm_del"):
                try:
                    ok = delete_stock_from_pool(sel_del_code)
                    st.success(f"{sel_del_code} 已删除" if ok else f"{sel_del_code} 未找到")
                except Exception as e:
                    st.error(str(e))


# =====================================================================
#  TAB 3 — 过滤测试
# =====================================================================
with tab_filters:
    st.subheader("🔍 过滤功能测试")

    st.markdown("""
    使用当前股票池数据测试各过滤器的效果。
    注意：部分过滤器依赖额外的数据字段（如 `list_date`、`amount_mean_20`、`status`），
    当前股票池不包含这些字段，这些过滤器会直接返回原始数据。
    """)

    try:
        pool_for_filter = get_stock_pool(include_inactive=True, include_blacklisted=True)
    except Exception:
        pool_for_filter = pd.DataFrame()

    if pool_for_filter.empty:
        st.info("股票池为空，请先导入 core_500.csv")
    else:
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            with st.container(border=True):
                st.markdown("**原始股票池**")
                _df = pool_for_filter[["stock_code", "stock_name", "is_active", "is_blacklisted"]].copy()
                _df["is_active"] = _df["is_active"].apply(lambda x: "✅ 启用" if x else "❌ 停用")
                _df["is_blacklisted"] = _df["is_blacklisted"].apply(lambda x: "⛔ 是" if x else "✅ 否")
                st.dataframe(
                    _label_columns(_df),
                    use_container_width=True,
                )
                st.caption(f"共 {len(pool_for_filter)} 条")

        with col_f2:
            with st.container(border=True):
                st.markdown("**ST 过滤结果**")
                filtered_st = filter_st_stocks(pool_for_filter)
                _df2 = filtered_st[["stock_code", "stock_name"]].copy()
                st.dataframe(
                    _label_columns(_df2),
                    use_container_width=True,
                )
                st.caption(f"剩余 {len(filtered_st)} 条 (过滤掉 {len(pool_for_filter) - len(filtered_st)} 条)")

        st.divider()

        with st.container(border=True):
            st.markdown("**组合过滤器 (apply_basic_filters)**")
            from src.universe.filters import apply_basic_filters
            filtered_all = apply_basic_filters(pool_for_filter)
            _df3 = filtered_all[["stock_code", "stock_name"]].copy()
            st.dataframe(
                _label_columns(_df3),
                use_container_width=True,
            )
            st.caption(f"原始 {len(pool_for_filter)} → 剩余 {len(filtered_all)}")

        st.info(
            "💡 后续版本 (V0.3+) 会在 stock_basic 表中增加 "
            "`list_date`、`amount_mean_20`、`status` 字段，届时过滤器将全面生效。"
        )


# =====================================================================
#  TAB 4 — 历史数据初始化
# =====================================================================
with tab_hist_data:
    st.subheader("📜 历史数据初始化 (V0.3)")

    st.markdown("""
    本页面展示历史数据初始化的状态。
    **当前版本不提供从页面直接拉取 500 支全量数据的功能**（避免 Streamlit 阻塞）。

    如需拉取数据，请在命令行中运行：
    """)

    st.code(
        "# 小批量测试 (2 支股票, raw + qfq)\n"
        "python -m src.data_update.historical_loader --pool core_500 --limit 2 --adj all\n\n"
        "# 拉取不复权数据\n"
        "python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj raw\n\n"
        "# 拉取前复权数据\n"
        "python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj qfq\n\n"
        "# 重试失败任务\n"
        "python -m src.data_update.retry_failed --limit 5\n",
        language="bash",
    )

    st.divider()

    # ── Data table row counts ─────────────────────────────────────────
    st.subheader("📊 数据表行数")

    try:
        raw_count = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_raw").iloc[0]["cnt"]
        qfq_count = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_qfq").iloc[0]["cnt"]
        log_count = query_df("SELECT COUNT(*) AS cnt FROM data_update_log").iloc[0]["cnt"]

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("stock_daily_raw 行数", f"{raw_count:,}")
        col_r2.metric("stock_daily_qfq 行数", f"{qfq_count:,}")
        col_r3.metric("data_update_log 行数", f"{log_count:,}")
    except Exception as e:
        st.warning(f"查询数据表行数失败: {e}")

    # ── Update summary ────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 更新日志汇总")

    try:
        from src.data_update.update_log import get_update_summary
        summary = get_update_summary(task_type="historical_load")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("✅ Success", summary["success"])
        col_s2.metric("❌ Failed", summary["failed"])
        col_s3.metric("○ Empty", summary["empty"])
        col_s4.metric("⏭️ Skipped", summary["skipped"])
    except Exception as e:
        st.warning(f"查询更新日志汇总失败: {e}")

    # ── Recent logs ───────────────────────────────────────────────────
    st.divider()
    st.subheader("🕐 最近更新日志 (最近 100 条)")

    try:
        from src.data_update.update_log import get_recent_update_logs
        logs = get_recent_update_logs(limit=100)
        if logs.empty:
            st.info("暂无更新日志。请先运行历史数据拉取命令。")
        else:
            # Format for display
            display_logs = logs.copy()
            if "started_at" in display_logs.columns:
                display_logs["started_at"] = pd.to_datetime(display_logs["started_at"]).dt.strftime("%Y-%m-%d %H:%M")
            if "finished_at" in display_logs.columns:
                display_logs["finished_at"] = pd.to_datetime(display_logs["finished_at"]).dt.strftime("%Y-%m-%d %H:%M")

            st.dataframe(display_logs, use_container_width=True, height=400)
    except Exception as e:
        st.warning(f"查询更新日志失败: {e}")
