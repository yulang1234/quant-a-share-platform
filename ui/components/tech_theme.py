"""V1.5.8 Dark Tech AI Research Cockpit — Theme & CSS."""
from __future__ import annotations

# ── Color Tokens ───────────────────────────────────────────────────────────
C = {
    "bg_main": "#070b18",
    "bg_panel": "rgba(16,24,48,0.72)",
    "bg_card": "rgba(22,32,62,0.58)",
    "border": "rgba(120,180,255,0.12)",
    "border_glow": "rgba(53,216,255,0.25)",
    "text": "#eef4ff",
    "text_muted": "#7f8da8",
    "cyan": "#35d8ff",
    "blue": "#4a8dff",
    "purple": "#8b5cf6",
    "green": "#35f0a0",
    "yellow": "#f7c948",
    "red": "#ff5d73",
    "orange": "#ff8c42",
}

# ── Status → Tone Mapping ──────────────────────────────────────────────────

def status_tone(market_state: str) -> dict:
    """Return {color, icon, label} for a market/sentiment state."""
    m = {
        "attack": ("#35f0a0", "🚀", "进攻"),
        "neutral": ("#4a8dff", "⏸", "中性"),
        "defense": ("#f7c948", "🛡", "防守"),
        "high_risk": ("#ff5d73", "⚠", "高风险"),
        "extreme": ("#ff3060", "🔥", "极高风险"),
        "ice_point": ("#7f8da8", "❄", "冰点"),
        "repair": ("#35d8ff", "🔧", "修复"),
        "warming": ("#f7c948", "🌡", "升温"),
        "climax": ("#ff8c42", "🔺", "高潮"),
        "cooling": ("#8b5cf6", "🔻", "降温"),
        "retreat": ("#ff5d73", "📉", "退潮"),
        "chaotic": ("#7f8da8", "🌀", "混沌"),
        "very_strong": ("#35f0a0", "💎", "极强"),
        "strong": ("#35d8ff", "📈", "强势"),
        "weak": ("#f7c948", "📉", "弱势"),
        "very_weak": ("#ff5d73", "💀", "极弱"),
        "confirmed_mainline": ("#35f0a0", "✅", "确认主线"),
        "potential_mainline": ("#35d8ff", "🔍", "潜在主线"),
        "one_day_theme": ("#f7c948", "⚡", "一日游"),
        "cooling_sector": ("#8b5cf6", "❄", "降温"),
        "high_risk_sector": ("#ff5d73", "⚠", "高风险"),
    }
    return {k: v for k, v in m.get(market_state, ("#7f8da8", "❓", "未知")).items() if k in ["color", "icon", "label"]} if isinstance(m.get(market_state), dict) else \
           {"color": "#7f8da8", "icon": "?" , "label": market_state}


# ── CSS ────────────────────────────────────────────────────────────────────

TECH_CSS = """
<style>
/* ========== GLOBAL ========== */
.stApp, .main, [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #070b18 0%, #0a1030 40%, #0d1440 100%) !important;
}
header[data-testid="stHeader"] { background: transparent !important; }
footer { display: none !important; }

/* ========== SIDEBAR ========== */
[data-testid="stSidebar"] {
    background: rgba(10,16,40,0.92) !important;
    border-right: 1px solid rgba(120,180,255,0.08) !important;
}
[data-testid="stSidebar"] * { color: #a0b4d0 !important; }

/* ========== TABS ========== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: transparent !important;
    border-bottom: 1px solid rgba(120,180,255,0.1);
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #7f8da8 !important;
    background: transparent !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 20px !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    border: none !important;
    transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover { color: #35d8ff !important; background: rgba(53,216,255,0.06) !important; }
.stTabs [aria-selected="true"] {
    color: #35d8ff !important;
    border-bottom: 2px solid #35d8ff !important;
    background: rgba(53,216,255,0.08) !important;
}

/* ========== METRICS ========== */
[data-testid="stMetric"] { background: transparent !important; }
[data-testid="stMetricValue"] { color: #eef4ff !important; font-size: 1.4rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #7f8da8 !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.5px; }

/* ========== CARDS ========== */
.glass-card {
    background: rgba(16,24,48,0.65);
    border: 1px solid rgba(120,180,255,0.10);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
    transition: border-color 0.3s;
}
.glass-card:hover { border-color: rgba(53,216,255,0.25); }

.glass-card-glow {
    border-color: rgba(53,216,255,0.30) !important;
    box-shadow: 0 0 32px rgba(53,216,255,0.08), 0 4px 24px rgba(0,0,0,0.4) !important;
}

.hero-card {
    background: linear-gradient(135deg, rgba(16,30,60,0.85) 0%, rgba(10,20,48,0.9) 100%);
    border: 1px solid rgba(120,180,255,0.18);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 20px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.4);
}

/* ========== STATUS BADGES ========== */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-green { background: rgba(53,240,160,0.15); color: #35f0a0; border: 1px solid rgba(53,240,160,0.25); }
.badge-blue { background: rgba(74,141,255,0.15); color: #4a8dff; border: 1px solid rgba(74,141,255,0.25); }
.badge-yellow { background: rgba(247,201,72,0.15); color: #f7c948; border: 1px solid rgba(247,201,72,0.25); }
.badge-red { background: rgba(255,93,115,0.15); color: #ff5d73; border: 1px solid rgba(255,93,115,0.25); }
.badge-purple { background: rgba(139,92,246,0.15); color: #8b5cf6; border: 1px solid rgba(139,92,246,0.25); }
.badge-cyan { background: rgba(53,216,255,0.15); color: #35d8ff; border: 1px solid rgba(53,216,255,0.25); }
.badge-muted { background: rgba(127,141,168,0.12); color: #7f8da8; border: 1px solid rgba(127,141,168,0.18); }

/* ========== SECTION TITLES ========== */
.section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #eef4ff;
    margin-bottom: 4px;
    letter-spacing: 0.3px;
}
.section-subtitle {
    font-size: 0.74rem;
    color: #7f8da8;
    margin-bottom: 14px;
}

/* ========== DATA FRAMES ========== */
[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden !important; }
[data-testid="stDataFrame"] table { font-size: 0.78rem !important; }
[data-testid="stDataFrame"] th { background: rgba(16,24,48,0.6) !important; color: #a0b4d0 !important; font-weight: 600 !important; }

/* ========== INFO / WARNING ========== */
.stAlert { border-radius: 8px !important; }
div[data-testid="stInfo"] { background: rgba(53,216,255,0.08) !important; border: 1px solid rgba(53,216,255,0.18) !important; }
div[data-testid="stWarning"] { background: rgba(247,201,72,0.08) !important; border: 1px solid rgba(247,201,72,0.18) !important; }
div[data-testid="stError"] { background: rgba(255,93,115,0.08) !important; border: 1px solid rgba(255,93,115,0.18) !important; }

/* ========== EXPANDER ========== */
.streamlit-expanderHeader { font-size: 0.82rem !important; color: #a0b4d0 !important; }

/* ========== BUTTONS ========== */
.stButton button {
    background: rgba(53,216,255,0.12) !important;
    border: 1px solid rgba(53,216,255,0.2) !important;
    color: #35d8ff !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}
.stButton button:hover { background: rgba(53,216,255,0.2) !important; border-color: rgba(53,216,255,0.4) !important; }

/* ========== TOGGLE ========== */
[data-testid="stToggle"] label { color: #7f8da8 !important; }
</style>
"""

def inject_theme():
    """Inject CSS into Streamlit. Call once at app start."""
    import streamlit as st
    st.markdown(TECH_CSS, unsafe_allow_html=True)
