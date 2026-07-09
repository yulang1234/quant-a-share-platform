"""V1.5.8 Decision Cockpit View — Today's AI research dashboard."""
from __future__ import annotations

import streamlit as st
from ui.components.ui_cards import (
    hero, decision_card, status_card, risk_list, section, scope_badge,
)
from ui.components.tech_theme import status_tone


def render_cockpit():
    """Main cockpit: market + sentiment + decision + risks."""
    hero(
        "AI 投研驾驶舱",
        "全 A 股市场状态 · 情绪周期 · 主线板块 · 风险提示",
        [f"V1.5.8", "全A股"],
    )

    # ── Load Data ──
    market = _safe_market()
    sentiment = _safe_sentiment()
    mc = market.get("market_state", "unknown")
    sc = sentiment.get("sentiment_cycle", "unknown")

    # ── Decision Card ──
    strategy, position, action, summary, tone = _make_decision(market, sentiment)
    decision_card(strategy, position, action, summary, tone)

    # ── Status Cards ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        t = status_tone(mc)
        status_card("市场环境", _cn(mc), "今天市场是否适合操作", _tone(mc))
    with c2:
        t = status_tone(sc)
        status_card("情绪周期", _cn(sc), "短线情绪所处阶段", _tone(sc))
    with c3:
        mainline = _safe_mainline()
        has = "有" if mainline.get("has_clear_mainline") else "无"
        summary = mainline.get("market_mainline_summary", "")
        status_card("主线板块", f"确认主线: {has}", summary if summary else "暂无主线数据", "good" if mainline.get("has_clear_mainline") else "neutral")
    with c4:
        risk_lv = market.get("risk_level", "unknown")
        status_card("风险等级", _cn_risk(risk_lv), "综合市场+情绪风险", _risk_tone(risk_lv))

    # ── Today's Focus ──
    section("今日重点观察")
    obs = _safe_observations()
    if obs:
        for o in obs[:6]:
            st.markdown(f'<div class="glass-card" style="font-size:0.82rem;color:#a0b4d0;">🔍 {o}</div>', unsafe_allow_html=True)
    else:
        st.info("暂无特别观察项。数据不足时建议仅观察，不做方向性判断。")

    # ── Risk Alerts ──
    section("风险提示")
    risks = _safe_risks()
    risk_list(risks)

    # ── Why? (collapsed) ──
    with st.expander("为什么这样判断"):
        mt = _cn(mc)
        st.markdown(
            f"""
            <div class="glass-card" style="border-left:3px solid {_tone_color(mc)};margin:6px 0;">
                <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">市场环境</div>
                <div style="font-size:0.95rem;font-weight:700;color:#eef4ff;">{mt}</div>
                <div style="font-size:0.8rem;color:#a0b4d0;">{market.get('action_hint','-')}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="glass-card" style="border-left:3px solid {_tone_color(sc)};margin:6px 0;">
                <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">情绪周期</div>
                <div style="font-size:0.95rem;font-weight:700;color:#eef4ff;">{_cn(sc)} <span style="font-size:0.8rem;color:#a0b4d0;">评分 {sentiment.get('sentiment_score','?')}/100</span></div>
                <div style="font-size:0.8rem;color:#a0b4d0;">{sentiment.get('action_hint','-')}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="glass-card" style="border-left:3px solid #35d8ff;margin:6px 0;">
                <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">数据范围</div>
                <div style="font-size:0.9rem;color:#eef4ff;">全A股 · 2,150+ 只标的 · 日线数据</div>
            </div>
            """, unsafe_allow_html=True)


def _tone_color(s: str) -> str:
    if s in ("attack", "warming", "repair", "climax"): return "#35f0a0"
    elif s in ("neutral", "chaotic"): return "#4a8dff"
    elif s in ("defense", "cooling"): return "#f7c948"
    elif s in ("high_risk", "retreat", "ice_point"): return "#ff5d73"
    return "#7f8da8"


# ── Chinese Label Mappings ─────────────────────────────────────────────────

def _cn(s: str) -> str:
    return {
        "attack": "进攻", "neutral": "中性", "defense": "防守", "high_risk": "高风险",
        "ice_point": "冰点", "repair": "修复", "warming": "升温", "climax": "高潮",
        "cooling": "降温", "retreat": "退潮", "chaotic": "混沌", "unknown": "未知",
    }.get(s, s)

def _cn_risk(s: str) -> str:
    return {"low": "低风险", "medium": "中风险", "high": "高风险", "extreme": "极高风险", "unknown": "未知"}.get(s, s)


# ── Data Loaders ───────────────────────────────────────────────────────────

def _safe_market() -> dict:
    try:
        from src.market.market_environment import build_market_environment
        return build_market_environment().as_dict()
    except Exception:
        return {"market_state": "unknown", "risk_level": "unknown", "action_hint": "数据加载失败"}


def _safe_sentiment() -> dict:
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        return build_sentiment_cycle().as_dict()
    except Exception:
        return {"sentiment_cycle": "unknown", "sentiment_score": 0, "action_hint": "数据加载失败"}


def _safe_mainline() -> dict:
    try:
        from src.sector.sector_mainline import build_mainline_snapshot
        snap = build_mainline_snapshot(None)
        return {"has_clear_mainline": snap.has_clear_mainline, "market_mainline_summary": snap.market_mainline_summary}
    except Exception:
        return {"has_clear_mainline": False, "market_mainline_summary": ""}


def _safe_observations() -> list[str]:
    """Generate real observation conditions from V1.5 modules — NOT V1.5.0 placeholders."""
    obs = []
    try:
        from src.market.market_environment import build_market_environment
        env = build_market_environment()
        ms = env.market_state
        if ms == "defense":
            obs.append("等待市场环境从防守修复到中性或进攻")
        elif ms == "high_risk":
            obs.append("市场高风险，等待风险释放后再评估")
        if not env.can_open_position:
            obs.append("当前不建议开新仓，观察市场能否企稳")
    except Exception:
        pass

    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle()
        sc = cycle.sentiment_cycle
        if sc in ("ice_point", "retreat"):
            obs.append("情绪处于冰点/退潮，等待修复信号出现")
        elif sc == "chaotic":
            obs.append("情绪混沌，等待方向明朗")
        elif sc in ("repair", "warming"):
            obs.append("关注涨停家数是否持续回升，连板高度是否拓展")
    except Exception:
        pass

    try:
        from src.sector.sector_mainline import build_mainline_snapshot
        snap = build_mainline_snapshot(None)
        if snap.confirmed_mainlines:
            obs.append(f"持续跟踪确认主线: {', '.join(s['sector_name'] for s in snap.confirmed_mainlines[:3])}")
        if snap.potential_mainlines:
            obs.append(f"观察潜在主线能否确认为主线: {', '.join(s['sector_name'] for s in snap.potential_mainlines[:3])}")
    except Exception:
        pass

    return obs if obs else ["数据加载中，请稍后刷新"]


def _safe_risks() -> list[str]:
    """Generate real risk warnings from V1.5 modules."""
    risks = ["本系统仅用于个人投研辅助，不构成投资建议，不自动交易"]
    try:
        from src.market.market_environment import build_market_environment
        env = build_market_environment()
        if env.risk_level in ("high", "extreme"):
            risks.append(f"市场风险等级: {env.risk_level}，建议控制仓位")
        if env.market_state == "high_risk":
            risks.append("市场处于高风险状态，不建议开新仓和追高")
    except Exception:
        pass

    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle()
        if cycle.relay_risk_level in ("high", "extreme"):
            risks.append(f"短线接力风险: {cycle.relay_risk_level}，追高和打板风险较大")
        if cycle.sentiment_cycle == "retreat":
            risks.append("情绪退潮期，强势股亏钱效应明显，建议停止接力")
        if cycle.sentiment_cycle == "climax":
            risks.append("情绪高潮阶段，谨防次日分化，不建议追高")
    except Exception:
        pass

    return risks


# ── Decision Logic ─────────────────────────────────────────────────────────

def _make_decision(market: dict, sentiment: dict):
    ms = market.get("market_state", "unknown")
    ss = sentiment.get("sentiment_cycle", "unknown")

    if ms == "attack" and ss in ("warming", "repair"):
        return "进攻", "50%+", "可小仓试错", "市场偏强，情绪修复中，可以适度进攻但注意追高风险。", "attack"
    elif ms == "defense" or ss in ("cooling", "retreat", "ice_point"):
        return "防守", "0%-20%", "不追高，只观察", "市场偏弱或情绪退潮，建议暂停开新仓，优先保护利润。", "defense"
    elif ms == "high_risk" or ss == "retreat":
        return "高风险", "0%", "停止操作，只观察", "市场高风险或情绪退潮明显，不建议任何操作。", "high_risk"
    elif ms == "unknown" or ss == "unknown":
        return "观望", "0%", "数据不足，仅观察", "数据不足以做出明确判断，建议等待数据补充。", "neutral"
    else:
        return "中性", "20%-50%", "等待明确信号", "市场中性，可观察主线方向但不要追高。", "neutral"


def _tone(s: str) -> str:
    if s in ("attack", "warming", "repair", "climax"):
        return "good"
    elif s in ("neutral", "chaotic"):
        return "neutral"
    elif s in ("defense", "cooling"):
        return "warning"
    elif s in ("high_risk", "retreat", "ice_point"):
        return "bad"
    return "unknown"


def _risk_tone(s: str) -> str:
    if s == "low": return "good"
    if s == "medium": return "warning"
    if s in ("high", "extreme"): return "bad"
    return "unknown"
