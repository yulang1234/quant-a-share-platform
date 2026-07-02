"""
Streamlit UI for the V0.1 project skeleton.

Run with::

    streamlit run ui/streamlit_app.py
"""

import streamlit as st

st.set_page_config(
    page_title="A股量化研究平台",
    page_icon="📈",
    layout="centered",
)

st.title("📈 A股量化研究平台")
st.markdown("**A股 500 支核心股票池量化研究平台**")
st.divider()

col1, col2 = st.columns(2)
with col1:
    st.metric("当前版本", "V0.1")
    st.caption("项目骨架")
with col2:
    st.metric("当前阶段", "项目骨架搭建")
    st.caption("仅包含工程结构与占位模块")

st.divider()

st.subheader("项目定位")
st.write("这是一个面向 A 股 500 支核心股票池的个人量化研究平台。")

st.subheader("后续模块入口占位")
modules = [
    "股票池管理",
    "历史数据初始化",
    "每日增量更新",
    "数据质量检查",
    "因子分析",
    "TopK 回测",
    "Qlib 研究",
    "AI 分析报告",
]
for module in modules:
    st.info(module)

st.subheader("风险提示")
st.warning("本项目仅用于个人量化研究和学习。")
st.warning("不构成任何投资建议。")
st.warning("不进行自动下单。")
st.warning("不接入实盘交易。")
