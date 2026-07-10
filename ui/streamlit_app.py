# -*- coding: utf-8 -*-
"""Local Streamlit cockpit for the A-share research system."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


st.set_page_config(
    page_title="A股AI投研驾驶舱",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from ui.components.tech_theme import inject_theme

    inject_theme()
except Exception:
    pass

tabs = st.tabs(
    [
        "今日驾驶舱",
        "板块机会",
        "板块龙头",
        "机会指数",
        "条件引擎",
        "持仓管理",
        "持仓体检",
        "组合风控",
        "投研日报",
        "系统管理",
    ]
)


with tabs[0]:
    try:
        from ui.components.decision_cockpit_view import render_cockpit

        render_cockpit()
    except Exception as exc:
        st.warning(f"今日驾驶舱暂不可用: {exc}")


with tabs[1]:
    try:
        from ui.components.sector_opportunity_view import render_sector_opportunity

        render_sector_opportunity()
    except Exception as exc:
        st.warning(f"板块机会暂不可用: {exc}")


with tabs[2]:
    st.markdown("## 板块龙头识别")
    st.caption("仅用于本地投研辅助，不构成投资建议，不执行交易。")
    from ui.components.sector_leader_view import (
        candidates_to_df,
        leader_csv_bytes,
        leader_markdown_bytes,
        load_sector_leader_result,
        load_sector_options,
    )

    sectors = load_sector_options()
    sector = st.selectbox("选择板块", sectors or [""])
    trade_date = st.text_input("交易日期", "2026-07-09", key="leader_trade_date")
    if st.button("识别龙头", key="leader_run"):
        result = load_sector_leader_result(trade_date, sector)
        if result:
            df = candidates_to_df(result)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("导出CSV", leader_csv_bytes(result), "sector_leaders.csv", "text/csv")
            st.download_button(
                "导出Markdown",
                leader_markdown_bytes(result),
                "sector_leaders.md",
                "text/markdown",
            )
            for warning in result.get("risk_warnings", []):
                st.warning(warning)
        else:
            st.info("暂无可用的本地板块龙头数据。")


with tabs[3]:
    st.markdown("## 目标收益机会指数")
    st.caption("输出观察状态和条件，不输出无条件交易指令。")
    from ui.components.opportunity_view import (
        action_cn,
        level_cn,
        load_opportunity,
        opportunity_csv_bytes,
        opportunity_markdown_bytes,
        opportunity_score_df,
    )

    c1, c2, c3 = st.columns([2, 2, 1])
    sector = c1.text_input("板块名称", "", key="opportunity_sector")
    stock_code = c2.text_input("股票代码", "", key="opportunity_stock")
    trade_date = c3.text_input("交易日期", "2026-07-09", key="opportunity_trade_date")
    if st.button("计算机会指数", key="opportunity_run"):
        result = load_opportunity(trade_date, sector, stock_code.strip())
        if result:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("机会指数", f"{result.get('opportunity_score', 0):.0f}/100")
            m2.metric("机会等级", level_cn(result.get("opportunity_level", "unknown")))
            m3.metric("观察状态", action_cn(result.get("action_signal", "unknown")))
            m4.metric("风险折扣", f"{result.get('risk_discount', 1):.0%}")
            st.dataframe(opportunity_score_df(result), use_container_width=True, hide_index=True)
            st.download_button("导出CSV", opportunity_csv_bytes(result), "opportunity.csv", "text/csv")
            st.download_button(
                "导出Markdown",
                opportunity_markdown_bytes(result),
                "opportunity.md",
                "text/markdown",
            )
            for warning in result.get("risk_warnings", []):
                st.warning(warning)
        else:
            st.info("暂无可用的本地机会指数数据。")


with tabs[4]:
    st.markdown("## 买卖条件引擎")
    st.caption("只生成条件与权限摘要，不自动补数、不联网、不执行交易。")
    from ui.components.condition_view import (
        condition_csv_bytes,
        condition_markdown_bytes,
        conditions_to_df,
        load_conditions,
        perm_cn,
    )

    c1, c2, c3 = st.columns([2, 2, 1])
    sector = c1.text_input("板块名称", "", key="condition_sector")
    stock_code = c2.text_input("股票代码", "", key="condition_stock")
    trade_date = c3.text_input("交易日期", "2026-07-09", key="condition_trade_date")
    if st.button("生成条件", key="condition_run"):
        result = load_conditions(trade_date, sector, stock_code.strip())
        if result:
            st.metric("permission_summary", perm_cn(result.get("permission", "unknown")))
            st.caption(result.get("permission_reason", ""))
            st.dataframe(conditions_to_df(result), use_container_width=True, hide_index=True)
            st.download_button("导出CSV", condition_csv_bytes(result), "conditions.csv", "text/csv")
            st.download_button(
                "导出Markdown",
                condition_markdown_bytes(result),
                "conditions.md",
                "text/markdown",
            )
            for warning in result.get("risk_warnings", []):
                st.warning(warning)
        else:
            st.info("暂无可用的本地条件数据。")


# ── Tab 5: 持仓管理 (V1.7.1) ──────────────────────────────────────────────────

with tabs[5]:
    st.markdown("## 持仓管理")
    st.caption(
        "用于记录真实或模拟持仓、成本、仓位、买入理由和原始策略。"
        "当前版本只管理持仓记录，不进行自动持仓诊断，也不会执行任何交易。"
    )

    from ui.components.portfolio_position_view import (
        close_position_from_ui,
        create_position_from_form,
        load_position,
        load_positions,
        position_csv_bytes,
        position_detail_markdown_bytes,
        position_markdown_bytes,
        position_mode_to_cn,
        position_snapshot_as_markdown,
        position_status_to_cn,
        position_summary,
        positions_to_df,
        update_position_from_form,
    )

    # ── B. 持仓总览 ────────────────────────────────────────────────
    summary = position_summary()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("活跃持仓", summary["active_count"])
    c2.metric("已关闭持仓", summary["closed_count"])
    c3.metric("真实持仓", summary["real_count"])
    c4.metric("模拟持仓", summary["simulated_count"])
    c5.metric("仓位合计", f"{summary['total_position_pct']:.1f}%")
    if not summary["position_pct_ok"]:
        st.warning("录入数据仓位合计超过 100%，请检查。")

    st.divider()

    # ── C. 新增持仓表单 ────────────────────────────────────────────
    with st.expander("➕ 新增持仓", expanded=False):
        with st.form("new_position_form"):
            col_a, col_b = st.columns(2)
            portfolio_name = col_a.text_input("组合名称", value="default", key="form_portfolio")
            is_simulated = col_b.radio("持仓类型", ["模拟", "真实"], index=0, key="form_mode")
            stock_code = col_a.text_input("股票代码", key="form_code")
            exchange = col_b.selectbox("交易所", ["SH", "SZ", "BJ"], key="form_exchange")
            stock_name = col_a.text_input("股票名称", key="form_name")
            buy_date = col_b.date_input("买入日期", key="form_buy_date")
            col_c, col_d = st.columns(2)
            avg_cost = col_c.number_input("平均成本", min_value=0.01, value=10.0, step=0.01, key="form_cost")
            quantity = col_d.number_input("持仓数量（可选）", min_value=0, value=None, step=100, key="form_qty")
            position_pct = col_c.number_input("仓位百分比", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="form_pct")
            sector_name = col_d.text_input("所属板块（可选）", key="form_sector")
            buy_reason = st.text_area("买入理由", key="form_reason", height=80)
            col_e, col_f = st.columns(2)
            original_strategy = col_e.selectbox(
                "原始策略",
                ["manual", "sector_leader", "opportunity_index", "condition_engine", "user_defined"],
                key="form_strategy",
            )
            user_note = col_f.text_input("用户备注（可选）", key="form_note")
            capture_snapshot = st.checkbox("保存当前 V1.6 判断快照", value=False, key="form_snapshot")

            submitted = st.form_submit_button("保存持仓")
            if submitted:
                try:
                    form_data = {
                        "portfolio_name": portfolio_name.strip() or "default",
                        "stock_code": stock_code.strip(),
                        "exchange": exchange,
                        "stock_name": stock_name.strip(),
                        "buy_date": str(buy_date),
                        "avg_cost": float(avg_cost),
                        "quantity": float(quantity) if quantity is not None and quantity > 0 else None,
                        "position_pct": float(position_pct),
                        "buy_reason": buy_reason.strip(),
                        "sector_name": sector_name.strip() or None,
                        "original_strategy": original_strategy,
                        "user_note": user_note.strip() or None,
                        "is_simulated": is_simulated == "模拟",
                        "capture_entry_snapshot": capture_snapshot,
                    }
                    result = create_position_from_form(form_data)
                    st.success(f"持仓已保存！position_id={result['position']['position_id']}")
                    if result.get("issues"):
                        for issue in result["issues"]:
                            st.info(issue)
                    if result.get("snapshot_issue"):
                        st.warning(f"快照部分失败: {result['snapshot_issue']}")
                except Exception as exc:
                    st.error(f"保存失败: {exc}")

    st.divider()

    # ── D. 持仓筛选 ────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
    filter_status = col_f1.selectbox("状态筛选", ["active", "closed", "all"], key="filter_status")
    filter_mode = col_f2.selectbox("类型筛选", ["all", "真实", "模拟"], key="filter_mode")
    filter_portfolio = col_f3.text_input("组合筛选", key="filter_portfolio")
    filter_code = col_f4.text_input("代码筛选", key="filter_code")
    filter_sector = col_f5.text_input("板块筛选", key="filter_sector")

    st.divider()

    # ── E. 持仓列表 ────────────────────────────────────────────────
    status_arg = None if filter_status == "all" else filter_status
    mode_arg = None if filter_mode == "all" else (filter_mode == "模拟")
    portfolio_arg = filter_portfolio.strip() or None
    code_arg = filter_code.strip() or None
    sector_arg = filter_sector.strip() or None

    positions = load_positions(
        portfolio_name=portfolio_arg,
        status=status_arg,
        is_simulated=mode_arg,
        stock_code=code_arg,
        sector_name=sector_arg,
    )

    df = positions_to_df(positions)
    if not df.empty:
        col_names = [
            "position_id", "portfolio_name", "持仓类型", "stock_code",
            "stock_name", "exchange", "buy_date", "avg_cost", "quantity",
            "position_pct", "sector_name", "original_strategy", "status",
            "has_snapshot", "updated_at",
        ]
        st.dataframe(df[col_names], use_container_width=True, hide_index=True)
    else:
        st.info("暂无符合条件的持仓记录。")

    # ── F. 持仓详情 ────────────────────────────────────────────────
    st.divider()
    selected_id = st.number_input(
        "选择持仓ID查看详情", min_value=1, value=1, step=1, key="detail_id"
    )
    if st.button("查看详情", key="view_detail"):
        detail = load_position(int(selected_id))
        if detail:
            st.markdown("### 持仓详情")
            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.metric("股票代码", detail.get("stock_code", ""))
            col_d2.metric("股票名称", detail.get("stock_name", ""))
            col_d3.metric("交易所", detail.get("exchange", ""))
            col_d4, col_d5, col_d6 = st.columns(3)
            col_d4.metric("平均成本", f"{detail.get('avg_cost', 0):.2f}")
            qty = detail.get("quantity")
            col_d5.metric("持仓数量", f"{int(qty)}" if qty is not None else "未填写")
            col_d6.metric("仓位百分比", f"{detail.get('position_pct', 0):.1f}%")
            st.markdown(f"**买入理由:** {detail.get('buy_reason', '')}")
            st.markdown(f"**所属板块:** {detail.get('sector_name', '暂无数据')}")
            st.markdown(f"**原始策略:** {detail.get('original_strategy', '暂无数据')}")
            st.markdown(f"**用户备注:** {detail.get('user_note', '暂无数据')}")
            st.markdown(f"**持仓类型:** {position_mode_to_cn(detail.get('is_simulated', True))}")
            st.markdown(f"**状态:** {position_status_to_cn(detail.get('status', 'active'))}")
            if detail.get("closed_at"):
                st.markdown(f"**关闭时间:** {detail['closed_at']}")
            st.markdown(f"**创建时间:** {detail.get('created_at', '')}")
            st.markdown(f"**更新时间:** {detail.get('updated_at', '')}")

            # Snapshot
            snapshot_md = position_snapshot_as_markdown(detail)
            if snapshot_md:
                with st.expander("建仓快照 (V1.6)", expanded=False):
                    st.markdown(snapshot_md)

            # Export detail
            st.download_button(
                "导出持仓详情 (Markdown)",
                position_detail_markdown_bytes(detail),
                f"position_{selected_id}_detail.md",
                "text/markdown",
            )
        else:
            st.info(f"未找到持仓记录: position_id={selected_id}")

    # ── G. 编辑持仓 ────────────────────────────────────────────────
    st.divider()
    with st.expander("✏️ 编辑持仓", expanded=False):
        edit_id = st.number_input(
            "持仓ID", min_value=1, value=1, step=1, key="edit_id"
        )
        edit_pos = load_position(int(edit_id))
        if edit_pos:
            with st.form("edit_position_form"):
                new_name = st.text_input("股票名称", value=edit_pos.get("stock_name", ""), key="edit_name")
                new_cost = st.number_input("平均成本", min_value=0.01, value=float(edit_pos.get("avg_cost", 0)), key="edit_cost")
                qty_val = edit_pos.get("quantity")
                new_qty = st.number_input(
                    "持仓数量", min_value=0, value=int(qty_val) if qty_val is not None else None, step=100, key="edit_qty"
                )
                new_pct = st.number_input(
                    "仓位百分比", min_value=0.0, max_value=100.0, value=float(edit_pos.get("position_pct", 0)), key="edit_pct"
                )
                new_reason = st.text_area("买入理由", value=edit_pos.get("buy_reason", ""), key="edit_reason")
                new_sector = st.text_input("所属板块", value=edit_pos.get("sector_name", "") or "", key="edit_sector")
                new_strategy = st.selectbox(
                    "原始策略",
                    ["manual", "sector_leader", "opportunity_index", "condition_engine", "user_defined"],
                    index=["manual", "sector_leader", "opportunity_index", "condition_engine", "user_defined"].index(
                        edit_pos.get("original_strategy") or "manual"
                    ),
                    key="edit_strategy",
                )
                new_note = st.text_input("用户备注", value=edit_pos.get("user_note", "") or "", key="edit_note")

                if st.form_submit_button("更新持仓"):
                    try:
                        qty_input = float(new_qty) if new_qty is not None and new_qty > 0 else None
                        changes = {
                            "stock_name": new_name.strip(),
                            "avg_cost": float(new_cost),
                            "quantity": qty_input,
                            "position_pct": float(new_pct),
                            "buy_reason": new_reason.strip(),
                            "sector_name": new_sector.strip() or None,
                            "original_strategy": new_strategy,
                            "user_note": new_note.strip() or None,
                        }
                        result = update_position_from_form(int(edit_id), changes)
                        st.success(f"持仓 {edit_id} 已更新")
                    except Exception as exc:
                        st.error(f"更新失败: {exc}")

    # ── H. 关闭持仓 ────────────────────────────────────────────────
    st.divider()
    with st.expander("🔒 关闭持仓记录", expanded=False):
        close_id = st.number_input(
            "持仓ID", min_value=1, value=1, step=1, key="close_id"
        )
        close_pos = load_position(int(close_id))
        if close_pos and close_pos.get("status") == "active":
            st.warning(
                "关闭记录仅表示本地持仓状态更新，不会执行任何卖出操作。"
            )
            confirmed = st.checkbox("我确认要关闭此持仓记录", key="close_confirm")
            if st.button("关闭持仓记录", disabled=not confirmed):
                try:
                    result = close_position_from_ui(int(close_id))
                    st.success(f"持仓 {close_id} 已关闭")
                except Exception as exc:
                    st.error(f"关闭失败: {exc}")
        elif close_pos:
            st.info("此持仓已经处于关闭状态。")

    # ── I. 导出 ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 导出")
    col_exp1, col_exp2 = st.columns(2)
    col_exp1.download_button(
        "导出持仓列表 (CSV)",
        position_csv_bytes(positions, include_snapshot=True),
        "portfolio_positions.csv",
        "text/csv",
        key="export_csv",
    )
    col_exp2.download_button(
        "导出持仓列表 (Markdown)",
        position_markdown_bytes(positions, summary),
        "portfolio_positions.md",
        "text/markdown",
        key="export_md",
    )


# ── Tab 6: 持仓体检 (V1.7.2) ──────────────────────────────────────────────────

with tabs[6]:
    st.markdown("## 每日持仓体检")
    st.caption(
        "基于当前市场、情绪、板块、龙头、趋势和条件引擎，对本地 active 持仓生成体检结果。"
        "所有结果仅供个人投研辅助，不会自动执行任何交易。"
    )

    from ui.components.position_diagnosis_view import (
        daily_diagnosis_markdown_bytes,
        diagnoses_to_df,
        diagnosis_csv_bytes,
        diagnosis_markdown_bytes,
        diagnosis_status_to_cn,
        diagnosis_summary,
        load_active_positions,
        load_daily_diagnoses,
        load_diagnosis_history,
        run_batch_diagnosis,
        run_single_diagnosis,
        save_diagnosis_from_ui,
        suggested_action_to_cn,
        thesis_status_to_cn,
    )

    trade_date = st.date_input("交易日期", key="diag_trade_date")

    # ── B. 筛选区 ─────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    diag_portfolio = col_f1.text_input("组合筛选", key="diag_portfolio")
    diag_mode = col_f2.selectbox("持仓类型", ["全部", "真实", "模拟"], key="diag_mode")
    diag_code = col_f3.text_input("代码筛选", key="diag_code")
    diag_status = col_f4.selectbox(
        "体检状态", ["全部", "healthy", "watch", "cautious", "dangerous", "unknown"],
        key="diag_status_filter",
    )

    # ── C. 体检按钮 ───────────────────────────────────────────────
    col_b1, col_b2 = st.columns(2)
    run_btn = col_b1.button("生成体检（不保存）", key="run_diag")
    save_confirm = col_b2.checkbox("确认保存到 SQLite", key="save_confirm")
    save_btn = col_b2.button("保存本次体检", key="save_diag", disabled=not save_confirm)

    if save_btn:
        st.info("保存仅写入 SQLite 体检记录，不修改持仓数据，不执行交易。")

    # ── Load active positions ───────────────────────────────────────
    mode_arg = None if diag_mode == "全部" else (diag_mode == "模拟")
    active_positions = load_active_positions(
        portfolio_name=diag_portfolio.strip() or None,
        is_simulated=mode_arg,
    )

    results: list[dict] = []

    if run_btn:
        with st.spinner("正在运行持仓体检..."):
            td_str = str(trade_date)
            result_data = run_batch_diagnosis(
                trade_date=td_str,
                portfolio_name=diag_portfolio.strip() or None,
                is_simulated=mode_arg,
                persist=False,
            )
            results = result_data.get("results", [])
            st.session_state["diag_results"] = results
            if result_data.get("issues"):
                for issue in result_data["issues"]:
                    st.warning(issue)

    if save_btn:
        td_str = str(trade_date)
        results = st.session_state.get("diag_results", [])
        if not results:
            st.warning("请先生成体检再保存。")
        else:
            with st.spinner("正在保存..."):
                saved = 0
                for r in results:
                    try:
                        save_diagnosis_from_ui(r)
                        saved += 1
                    except Exception as exc:
                        st.warning(f"保存 position_id={r.get('position_id')} 失败: {exc}")
                st.success(f"已保存 {saved}/{len(results)} 条体检记录")

    # ── D. 总览指标 ───────────────────────────────────────────────
    if results:
        summary = diagnosis_summary(results)
        cols = st.columns(8)
        cols[0].metric("active持仓", len(active_positions))
        cols[1].metric("健康", summary.get("healthy", 0))
        cols[2].metric("关注", summary.get("watch", 0))
        cols[3].metric("谨慎", summary.get("cautious", 0))
        cols[4].metric("危险", summary.get("dangerous", 0))
        cols[5].metric("未知", summary.get("unknown", 0))
        cols[6].metric("减仓条件", summary.get("action_reduce_conditionally", 0))
        cols[7].metric("清仓条件", summary.get("action_exit_conditionally", 0))
    else:
        # Load saved diagnoses from DB
        td_str_load = str(trade_date)
        status_filter = None if diag_status == "全部" else diag_status
        saved_diags = load_daily_diagnoses(
            trade_date=td_str_load,
            portfolio_name=diag_portfolio.strip() or None,
            stock_code=diag_code.strip() or None,
            diagnosis_status=status_filter,
        )
        if saved_diags:
            results = saved_diags

    st.divider()

    # ── E. 体检表 ─────────────────────────────────────────────────
    if results:
        df = diagnoses_to_df(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info('暂无体检结果。点击"生成体检"开始。')

    # ── F. 单只持仓详情 ───────────────────────────────────────────
    st.divider()
    detail_id = st.number_input(
        "选择持仓ID查看详情", min_value=1, value=1, step=1, key="diag_detail_id"
    )
    if st.button("查看体检详情", key="view_diag_detail"):
        # Run single diagnosis for detail
        detail_result = run_single_diagnosis(int(detail_id), str(trade_date))
        if detail_result.get("diagnosis_status"):
            st.markdown(f"### 体检详情: {detail_result.get('stock_name', '')}")
            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.metric("体检状态", diagnosis_status_to_cn(detail_result.get("diagnosis_status", "")))
            col_d2.metric("建议动作", suggested_action_to_cn(detail_result.get("suggested_action", "")))
            col_d3.metric("原始逻辑", thesis_status_to_cn(detail_result.get("thesis_status", "")))
            col_d4, col_d5, col_d6 = st.columns(3)
            col_d4.metric("健康分数", f"{detail_result.get('health_score', 0):.1f}")
            unreal = detail_result.get("unrealized_return_pct")
            col_d5.metric("浮动收益", f"{unreal:+.2f}%" if unreal is not None else "N/A")
            col_d6.metric("最新价", f"{detail_result.get('latest_close') or 'N/A'}")

            # Component scores
            with st.expander("分项评分", expanded=False):
                comp_cols = st.columns(4)
                comp_cols[0].metric("市场", f"{detail_result.get('market_support_score', 0):.0f}")
                comp_cols[1].metric("情绪", f"{detail_result.get('sentiment_support_score', 0):.0f}")
                comp_cols[2].metric("板块", f"{detail_result.get('sector_support_score', 0):.0f}")
                comp_cols[3].metric("龙头", f"{detail_result.get('leader_support_score', 0):.0f}")
                comp_cols2 = st.columns(3)
                comp_cols2[0].metric("趋势", f"{detail_result.get('trend_health_score', 0):.0f}")
                comp_cols2[1].metric("条件引擎", f"{detail_result.get('condition_support_score', 0):.0f}")
                comp_cols2[2].metric("原始逻辑", f"{detail_result.get('thesis_score', 0):.0f}")

            with st.expander("风险与条件", expanded=False):
                for w in detail_result.get("risk_warnings", []):
                    st.warning(w)
                st.markdown("**观察条件:**")
                for o in detail_result.get("observation_conditions", []):
                    st.markdown(f"- {o}")
                st.markdown("**失效条件:**")
                for i in detail_result.get("invalidation_conditions", []):
                    st.markdown(f"- {i}")

            st.download_button(
                "导出体检详情 (Markdown)",
                diagnosis_markdown_bytes(detail_result),
                f"position_{detail_id}_diagnosis.md",
                "text/markdown",
                key="export_diag_detail",
            )
        else:
            st.info(f"未能生成体检结果: {detail_result.get('issue_summary', [])}")

    # ── G. 历史记录 ───────────────────────────────────────────────
    st.divider()
    hist_id = st.number_input(
        "选择持仓ID查看历史体检", min_value=1, value=1, step=1, key="hist_id"
    )
    if st.button("查看历史体检", key="view_history"):
        history = load_diagnosis_history(int(hist_id))
        if history:
            hist_df = diagnoses_to_df(history)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无历史体检记录。")

    # ── H. 导出 ───────────────────────────────────────────────────
    st.divider()
    if results:
        col_exp1, col_exp2 = st.columns(2)
        col_exp1.download_button(
            "导出体检表 (CSV)",
            diagnosis_csv_bytes(results),
            "position_diagnosis.csv",
            "text/csv",
            key="diag_export_csv",
        )
        col_exp2.download_button(
            "导出体检日报 (Markdown)",
            daily_diagnosis_markdown_bytes(results, diagnosis_summary(results)),
            "daily_position_diagnosis.md",
            "text/markdown",
        key="diag_export_md",
    )


# ── Tab 7: 组合风控 (V1.7.3) ──────────────────────────────────────────────────

with tabs[7]:
    st.markdown("## 组合风险控制")
    st.caption(
        "基于本地 active 持仓、每日持仓体检、市场环境和历史行情，"
        "检查单股集中、板块集中、持仓相关性、组合回撤和连续亏损等风险。"
        "本页面不会自动修改持仓，也不会执行任何交易。"
    )

    from ui.components.portfolio_risk_view import (
        all_portfolios_markdown_bytes,
        correlation_pairs_to_df,
        load_daily_portfolio_risks,
        load_portfolio_options,
        load_portfolio_risk_history,
        portfolio_permission_to_cn,
        portfolio_risk_csv_bytes,
        portfolio_risk_markdown_bytes,
        portfolio_risk_to_df,
        risk_dimensions_to_df,
        risk_level_to_cn,
        run_all_portfolio_risk_analysis,
        run_portfolio_risk_analysis,
        save_portfolio_risk_from_ui,
        sector_exposure_to_df,
    )

    trade_date = st.date_input("交易日期", key="risk_trade_date")
    options = load_portfolio_options()

    # B. Filter
    col_f1, col_f2 = st.columns(2)
    pf_names = sorted(set(o["portfolio_name"] for o in options))
    pf_name = col_f1.selectbox("组合", pf_names if pf_names else ["default"], key="risk_pf")
    sim_opts = ["真实", "模拟"]
    sim_idx = 0  # default: 真实
    is_sim = col_f2.selectbox("持仓类型", sim_opts, index=sim_idx, key="risk_sim") == "模拟"

    # C. Buttons
    col_b1, col_b2 = st.columns(2)
    run_btn = col_b1.button("生成组合风控报告（不保存）", key="run_risk")
    save_confirm = col_b2.checkbox("确认保存到 SQLite", key="risk_save_confirm")
    save_btn = col_b2.button("保存本次组合风险快照", key="save_risk", disabled=not save_confirm)

    result = None
    if run_btn:
        with st.spinner("正在分析组合风险..."):
            result = run_portfolio_risk_analysis(str(trade_date), pf_name, is_sim, persist=False)
            st.session_state["risk_result"] = result

    if save_btn:
        result = st.session_state.get("risk_result")
        if not result:
            st.warning("请先生成报告再保存")
        else:
            try:
                save_portfolio_risk_from_ui(result)
                st.success("组合风险快照已保存")
            except Exception as exc:
                st.error(f"保存失败: {exc}")

    if result:
        # D. Overview
        st.markdown("### 风险总览")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("风险评分", f"{result.get('portfolio_risk_score', 0):.0f}")
        c2.metric("风险等级", risk_level_to_cn(result.get("portfolio_risk_level", "")))
        c3.metric("权限", portfolio_permission_to_cn(result.get("portfolio_permission", "")))
        c4.metric("持仓数", result.get("position_count", 0))
        c5.metric("总仓位", f"{result.get('total_position_pct', 0):.1f}%")
        c6.metric("覆盖率", f"{result.get('data_coverage_ratio', 0):.0%}")

        st.divider()
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("最大单股", f"{result.get('max_single_position_code', '')} {result.get('max_single_position_pct', 0):.1f}%")
        c2.metric("最大板块", f"{result.get('max_sector_name', '')} {result.get('max_sector_position_pct', 0):.1f}%")
        c3.metric("Top3集中", f"{result.get('top3_position_pct', 0):.1f}%")
        avg_corr = result.get("average_pairwise_correlation")
        c4.metric("平均相关性", f"{avg_corr:.2f}" if avg_corr is not None else "N/A")
        dd60 = result.get("portfolio_drawdown_60d")
        c5.metric("60d回撤", f"{dd60:.1f}%" if dd60 is not None else "N/A")
        c6.metric("连续亏损", f"{result.get('consecutive_loss_days', 0)}天")

        # E. Dimensions
        st.divider()
        st.markdown("### 风险维度")
        dims_df = risk_dimensions_to_df(result)
        if not dims_df.empty:
            st.dataframe(dims_df, use_container_width=True, hide_index=True)

        # F. Sector exposure
        with st.expander("板块暴露", expanded=False):
            sec_df = sector_exposure_to_df(result)
            if not sec_df.empty:
                st.dataframe(sec_df, use_container_width=True, hide_index=True)

        # G. Correlation
        with st.expander("高相关持仓", expanded=False):
            corr_df = correlation_pairs_to_df(result)
            if not corr_df.empty:
                st.dataframe(corr_df, use_container_width=True, hide_index=True)

        # H. Risk flags
        with st.expander("风险提示与建议", expanded=False):
            for f in result.get("risk_flags", []):
                st.warning(f)
            st.markdown("**建议:**")
            for r in result.get("recommendations", []):
                st.markdown(f"- {r}")
            st.markdown("**观察条件:**")
            for o in result.get("observation_conditions", []):
                st.markdown(f"- {o}")
            st.markdown("**解除条件:**")
            for r in result.get("risk_release_conditions", []):
                st.markdown(f"- {r}")

        # I. Export
        st.divider()
        col_e1, col_e2 = st.columns(2)
        col_e1.download_button("导出 CSV", portfolio_risk_csv_bytes([result]), "portfolio_risk.csv", "text/csv", key="risk_csv")
        col_e2.download_button("导出 Markdown", portfolio_risk_markdown_bytes(result), "portfolio_risk_report.md", "text/markdown", key="risk_md")

    # J. History
    st.divider()
    with st.expander("历史风险快照", expanded=False):
        history = load_portfolio_risk_history(pf_name, is_sim)
        if history:
            hist_df = portfolio_risk_to_df(history)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无历史记录")


with tabs[8]:
    try:
        from ui.components.ui_cards import placeholder_page

        placeholder_page("投研日报", "后续版本启用。", ["当前页面不执行联网、补数或交易。"])
    except Exception:
        st.info("投研日报后续版本启用。")


with tabs[9]:
    try:
        from ui.components.system_admin_view import render_system_admin

        render_system_admin()
    except Exception as exc:
        st.warning(f"系统管理暂不可用: {exc}")


st.caption("本系统仅用于本地个人投研辅助，不构成投资建议，不提供收益承诺。")
