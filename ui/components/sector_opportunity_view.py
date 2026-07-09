"""V1.5.8 Sector Opportunity View — mainlines, potentials, warnings."""
from __future__ import annotations

import streamlit as st
from ui.components.ui_cards import section, sector_card, placeholder_page


def render_sector_opportunity():
    st.markdown("## 板块机会")

    try:
        from src.sector.sector_mainline import build_mainline_snapshot
        snap = build_mainline_snapshot(None)
    except Exception:
        placeholder_page("板块数据暂不可用", "请先同步板块基础数据 (V1.5.3)", ["同步行业板块", "同步股票板块映射"])
        return

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### ✅ 确认主线")
        if snap.confirmed_mainlines:
            for s in snap.confirmed_mainlines[:5]:
                sector_card(
                    s["sector_name"], "确认主线", "good",
                    "重点观察", "中",
                    conditions=["持续排名前10", "相对强度保持正值"],
                )
        else:
            st.caption("暂无确认主线")

    with c2:
        st.markdown("### 🔍 潜在主线")
        if snap.potential_mainlines:
            for s in snap.potential_mainlines[:5]:
                sector_card(
                    s["sector_name"], "潜在主线", "neutral",
                    "观察等待", "中",
                    conditions=["连续2日排名前10", "成交额温和放大"],
                )
        else:
            st.caption("暂无潜在主线")

    with c3:
        st.markdown("### ⚠ 不建议追高")
        risky = snap.high_risk_sectors + snap.one_day_themes + snap.cooling_sectors
        if risky:
            for s in risky[:5]:
                sector_card(
                    s["sector_name"], "高风险/一日游/降温", "warning",
                    "不追高", "高",
                    invalidation=["排名继续下滑", "上涨占比下降"],
                )
        else:
            st.caption("暂无高风险板块")

    # ── Quick Diagnosis ──
    st.markdown("---")
    section("板块问诊")
    name = st.text_input("输入板块名称", "", placeholder="例如: 机器人、AI算力、半导体")
    if name:
        try:
            from src.sector.sector_diagnosis import diagnose_sector_by_name
            d = diagnose_sector_by_name(None, sector_name=name)
            if d.diagnosis_status != "unknown":
                dd = d.as_dict()
                st.info(dd.get("action_hint", ""))
                with st.expander("查看详细指标"):
                    st.json(dd)
            else:
                st.warning(f"板块 '{name}' 数据不足，无法问诊")
        except Exception as e:
            st.warning(f"问诊失败: {e}")
