"""V1.5.8 Reusable UI card renderers."""
from __future__ import annotations

import streamlit as st
from ui.components.tech_theme import C

# ── Simple HTML Card ────────────────────────────────────────────────────────

def card(html: str, glow: bool = False, margin_top: int = 8) -> None:
    """Render a glass card with HTML content."""
    cls = "glass-card glass-card-glow" if glow else "glass-card"
    st.markdown(
        f'<div class="{cls}" style="margin-top:{margin_top}px;">{html}</div>',
        unsafe_allow_html=True,
    )


# ── Hero Banner ─────────────────────────────────────────────────────────────

def hero(title: str, subtitle: str, badges: list[str] | None = None) -> None:
    """Render the top hero banner."""
    badge_html = ""
    if badges:
        items = "".join(
            f'<span class="badge badge-cyan" style="margin-right:8px;">{b}</span>'
            for b in badges
        )
        badge_html = f'<div style="margin-top:10px;">{items}</div>'
    st.markdown(
        f"""
        <div class="hero-card">
            <div style="font-size:1.6rem;font-weight:800;color:#eef4ff;letter-spacing:0.5px;">{title}</div>
            <div style="font-size:0.82rem;color:#7f8da8;margin-top:4px;">{subtitle}</div>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Decision Card (Hero centerpiece) ────────────────────────────────────────

def decision_card(
    strategy: str,
    position: str,
    action: str,
    summary: str,
    tone: str = "neutral",
) -> None:
    """Big decision card — the visual center of the cockpit."""
    tone_colors = {
        "attack": (C["green"], "rgba(53,240,160,0.10)"),
        "neutral": (C["blue"], "rgba(74,141,255,0.10)"),
        "defense": (C["yellow"], "rgba(247,201,72,0.10)"),
        "high_risk": (C["red"], "rgba(255,93,115,0.10)"),
    }
    color, bg = tone_colors.get(tone, (C["cyan"], "rgba(53,216,255,0.08)"))

    st.markdown(
        f"""
        <div class="hero-card" style="border-left:4px solid {color};background:{bg};">
            <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
                <div style="min-width:100px;">
                    <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">今日策略</div>
                    <div style="font-size:1.5rem;font-weight:800;color:{color};">{strategy}</div>
                </div>
                <div style="min-width:100px;">
                    <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">建议仓位</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#eef4ff;">{position}</div>
                </div>
                <div style="min-width:140px;">
                    <div style="font-size:0.7rem;color:#7f8da8;text-transform:uppercase;">今日动作</div>
                    <div style="font-size:1.1rem;font-weight:700;color:#eef4ff;">{action}</div>
                </div>
            </div>
            <div style="margin-top:14px;font-size:0.85rem;color:#a0b4d0;line-height:1.5;">{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Status KPI Card ─────────────────────────────────────────────────────────

def status_card(title: str, status: str, description: str, tone: str = "neutral") -> None:
    """A compact status indicator card."""
    colors = {
        "good": (C["green"], "badge-green"),
        "neutral": (C["blue"], "badge-blue"),
        "warning": (C["yellow"], "badge-yellow"),
        "bad": (C["red"], "badge-red"),
        "unknown": (C["text_muted"], "badge-muted"),
    }
    color, badge_cls = colors.get(tone, (C["cyan"], "badge-cyan"))

    st.markdown(
        f"""
        <div class="glass-card" style="border-left:3px solid {color};">
            <div style="font-size:0.68rem;color:#7f8da8;text-transform:uppercase;letter-spacing:0.5px;">{title}</div>
            <div style="margin:6px 0;">
                <span class="badge {badge_cls}">{status}</span>
            </div>
            <div style="font-size:0.78rem;color:#a0b4d0;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Sector Opportunity Card ─────────────────────────────────────────────────

def sector_card(
    name: str, status_label: str, status_tone: str,
    action: str, risk: str,
    conditions: list[str] | None = None,
    invalidation: list[str] | None = None,
) -> None:
    """Render a sector opportunity card."""
    tone_colors = {
        "good": C["green"], "neutral": C["blue"],
        "warning": C["yellow"], "bad": C["red"],
    }
    color = tone_colors.get(status_tone, C["cyan"])

    cond_html = ""
    if conditions:
        cond_html = "<div style='font-size:0.72rem;color:#7f8da8;margin-top:6px;'>观察: " + " · ".join(conditions[:3]) + "</div>"
    inv_html = ""
    if invalidation:
        inv_html = "<div style='font-size:0.72rem;color:#ff5d73;margin-top:3px;'>失效: " + " · ".join(invalidation[:2]) + "</div>"

    st.markdown(
        f"""
        <div class="glass-card" style="border-left:3px solid {color};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:700;color:#eef4ff;">{name}</span>
                <span class="badge badge-{'green' if status_tone=='good' else 'blue' if status_tone=='neutral' else 'yellow' if status_tone=='warning' else 'red'}">{status_label}</span>
            </div>
            <div style="font-size:0.78rem;color:#a0b4d0;margin-top:4px;">动作: {action} &nbsp;|&nbsp; 风险: {risk}</div>
            {cond_html}{inv_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Risk List ────────────────────────────────────────────────────────────────

def risk_list(items: list[str]) -> None:
    """Render a list of risk warnings."""
    if not items:
        st.markdown('<div class="glass-card"><span style="color:#7f8da8;">暂无风险提示</span></div>', unsafe_allow_html=True)
        return
    lines = "".join(
        f'<div style="color:#ff8c88;font-size:0.82rem;padding:4px 0;">⚠ {item}</div>'
        for item in items
    )
    st.markdown(f'<div class="glass-card">{lines}</div>', unsafe_allow_html=True)


# ── Empty Future Page ───────────────────────────────────────────────────────

def placeholder_page(title: str, description: str, items: list[str]) -> None:
    """Render a premium placeholder for future features."""
    items_html = "".join(f"<li style='color:#a0b4d0;margin:4px 0;'>{item}</li>" for item in items)
    st.markdown(
        f"""
        <div class="hero-card" style="text-align:center;padding:48px;">
            <div style="font-size:3rem;margin-bottom:12px;">🛰</div>
            <div style="font-size:1.3rem;font-weight:700;color:#eef4ff;">{title}</div>
            <div style="font-size:0.85rem;color:#7f8da8;margin:8px 0 20px;">{description}</div>
            <div style="text-align:left;max-width:500px;margin:0 auto;">
                <ul style="font-size:0.82rem;color:#a0b4d0;">{items_html}</ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Section Title ───────────────────────────────────────────────────────────

def section(title: str, subtitle: str = "") -> None:
    """Render a section header."""
    sub = f'<div class="section-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="section-title">{title}</div>{sub}', unsafe_allow_html=True)


# ── Data Scope Badge ────────────────────────────────────────────────────────

def scope_badge(scope: str = "universe_all_a") -> str:
    """Return HTML for a data scope badge."""
    labels = {"universe_all_a": "全A股", "core_500": "core500", "unknown": "未知"}
    return f'<span class="badge badge-muted">{labels.get(scope, scope)}</span>'
