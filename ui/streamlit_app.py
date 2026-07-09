"""V1.5.8 AI Research Cockpit — Premium Dark Tech UI.

5 main pages: Cockpit · Sector Opportunities · Portfolio · Daily Report · System Admin
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

# ── Page Config ──
st.set_page_config(
    page_title="AI 投研驾驶舱",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject Theme ──
from ui.components.tech_theme import inject_theme
inject_theme()

# ── Init DB ──
try:
    from src.storage.duckdb_repo import init_database
    init_database()
except Exception:
    pass

# ── Top spacer ──
st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

# ── 5 Main Tabs ──
t_cockpit, t_sector, t_portfolio, t_report, t_admin = st.tabs([
    "🛰 今日驾驶舱",
    "📊 板块机会",
    "💼 持仓体检",
    "📋 投研日报",
    "⚙ 系统管理",
])

# ===================================================================
# TAB 1: Decision Cockpit
# ===================================================================
with t_cockpit:
    from ui.components.decision_cockpit_view import render_cockpit
    try:
        render_cockpit()
    except Exception as e:
        st.error(f"驾驶舱加载失败: {e}")
        st.info("请确保已完成数据同步。运行 `python sync_all_stocks.py`")

# ===================================================================
# TAB 2: Sector Opportunities
# ===================================================================
with t_sector:
    from ui.components.sector_opportunity_view import render_sector_opportunity
    try:
        render_sector_opportunity()
    except Exception as e:
        st.error(f"板块页面加载失败: {e}")

# ===================================================================
# TAB 3: Portfolio Health (V1.7 placeholder)
# ===================================================================
with t_portfolio:
    from ui.components.ui_cards import placeholder_page
    placeholder_page(
        "持仓体检 · 即将启用",
        "V1.7 将支持：每日自动判断持仓标的是否仍值得持有",
        [
            "原始买入逻辑是否仍成立",
            "所属板块是否仍强",
            "是否触发减仓 / 清仓",
            "当前仓位是否过重",
            "是否允许加仓",
        ],
    )

# ===================================================================
# TAB 4: Daily Report (V1.8 placeholder)
# ===================================================================
with t_report:
    from ui.components.ui_cards import placeholder_page
    placeholder_page(
        "每日投研日报 · 即将启用",
        "V1.8 将支持：自动生成投研日报并推送至微信",
        [
            "今日市场状态与情绪周期",
            "今日主线板块与潜在主线",
            "今日重点观察方向",
            "持仓建议",
            "明日观察条件与风险提示",
            "微信推送 (PushPlus)",
        ],
    )

# ===================================================================
# TAB 5: System Admin
# ===================================================================
with t_admin:
    from ui.components.system_admin_view import render_system_admin
    try:
        render_system_admin()
    except Exception as e:
        st.error(f"系统管理加载失败: {e}")

# ── Footer ──
st.markdown(
    """
    <div style="text-align:center;padding:20px;color:#3a4a6a;font-size:0.7rem;">
    AI 投研驾驶舱 V1.5.8 · 仅用于个人投研辅助 · 不构成投资建议
    </div>
    """,
    unsafe_allow_html=True,
)
