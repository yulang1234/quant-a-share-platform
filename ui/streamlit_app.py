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


with tabs[5]:
    try:
        from ui.components.ui_cards import placeholder_page

        placeholder_page("投研日报", "后续版本启用。", ["当前页面不执行联网、补数或交易。"])
    except Exception:
        st.info("投研日报后续版本启用。")


with tabs[6]:
    try:
        from ui.components.system_admin_view import render_system_admin

        render_system_admin()
    except Exception as exc:
        st.warning(f"系统管理暂不可用: {exc}")


st.caption("本系统仅用于本地个人投研辅助，不构成投资建议，不提供收益承诺。")
