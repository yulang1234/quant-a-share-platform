"""V1.5.8 System Admin View — all back-office functions behind toggle."""
from __future__ import annotations

import streamlit as st
from ui.components.ui_cards import section


def render_system_admin():
    st.markdown("## 系统管理")

    advanced = st.toggle("高级模式 / 开发者模式", value=False, key="sys_advanced")

    # ── Data Sync ──
    section("数据同步")
    with st.expander("全 A 股近 30 天同步"):
        st.code("python -m src.data_update.all_a_recent_sync --recent-days 30 --adj qfq --confirm", language="bash")
    with st.expander("每日增量更新"):
        st.code("python -m src.data_update.daily_incremental --adj qfq", language="bash")
    with st.expander("板块数据同步"):
        st.code("python -m src.sector.sector_sync --sync-basic --source akshare --confirm\npython -m src.sector.sector_sync --sync-map --source akshare --confirm", language="bash")

    # ── Data Health ──
    section("数据健康")
    try:
        from src.storage.duckdb_repo import query_df
        df = query_df("SELECT COUNT(DISTINCT stock_code) as stocks, COUNT(*) as rows, MAX(trade_date) as latest FROM stock_daily_raw")
        r = df.iloc[0]
        st.metric("行情覆盖", f"{r['stocks']} 只股票")
        st.metric("最新日期", str(r["latest"])[:10])
    except Exception:
        st.caption("数据暂不可用")

    # ── Advanced: Research Tools ──
    if advanced:
        section("研究工具")
        st.caption("因子计算、回测、评分等（仅高级模式）")
        with st.expander("基础因子"):
            st.code("python -m src.factors.run_factor_calculation --pool core_500 --limit 5", language="bash")
        with st.expander("TopK 选股"):
            st.code("python -m src.strategy.run_topk_strategy --strategy single_return_20d_top20 --limit 5", language="bash")
        with st.expander("基础回测"):
            st.code("python -m src.backtest.run_backtest --strategy single_return_20d_top20 --limit 5", language="bash")

    # ── Advanced: Debug ──
    if advanced:
        section("开发调试")
        with st.expander("数据库路径"):
            st.code("DuckDB: D:/AIProjects/data/duckdb/quant_a_share.duckdb\nMetaDB: D:/AIProjects/data/meta/quant_meta.db", language="text")
        with st.expander("命令手册"):
            st.markdown("详见 `python -m pytest tests/ -q` 和 `README.md`")
