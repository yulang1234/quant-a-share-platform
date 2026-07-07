"""V1.5.0 minimal decision-rule layer.

Pure functions that combine market_state / sentiment_cycle / sector count
/ data_quality_status into:

* ``overall_bias``  (unknown / defensive / neutral / aggressive)
* ``risk_warnings`` (list[str])
* ``suggested_actions`` (list[str])
* ``observation_conditions`` (list[str])
* ``invalidation_conditions`` (list[str])

Hard constraints (enforced by tests):
* overall_bias may be ``aggressive`` ONLY when market_state, sentiment_cycle
  and sector_count are all non-unknown/non-empty AND data_quality_status is
  healthy/usable. In V1.5.0 (market & sentiment always unknown), aggressive
  is therefore unreachable.
* suggested_actions text must never contain any of the forbidden words:
  买入 / 卖出 / 加仓 / 清仓 / 满仓 / 重仓 / 梭哈 / 目标价 / 必涨 /
  稳赚 / 保证收益 / 推荐股票.
"""
from __future__ import annotations

from typing import Any

# ── Enumerations ──────────────────────────────────────────────────────────────

OVERALL_UNKNOWN = "unknown"
OVERALL_DEFENSIVE = "defensive"
OVERALL_NEUTRAL = "neutral"
OVERALL_AGGRESSIVE = "aggressive"
OVERALL_BIAS_VALUES: tuple[str, ...] = (
    OVERALL_UNKNOWN, OVERALL_DEFENSIVE, OVERALL_NEUTRAL, OVERALL_AGGRESSIVE,
)

# ── Forbidden words (must never appear in suggested_actions text) ──────────────

FORBIDDEN_WORDS: tuple[str, ...] = (
    "买入", "卖出", "加仓", "清仓", "满仓", "重仓", "梭哈",
    "目标价", "今日必涨", "明日必涨", "必涨", "稳赚", "保证收益",
    "推荐股票",
)

# ── Whitelisted output phrases ─────────────────────────────────────────────────

# suggested_actions whitelist — each is an exact phrase.
_SUGGESTED_ACTIONS_POOL: dict[str, tuple[str, ...]] = {
    "insufficient": (
        "数据不足，今日仅做观察",
        "等待后续数据补齐后再生成正式判断",
    ),
    "market_unknown": (
        "市场状态不明，避免追高",
    ),
    "sentiment_unknown": (
        "情绪周期未确认，降低进攻性",
    ),
    "sector_empty": (
        "板块数据不足，暂不输出方向判断",
    ),
    "neutral": (
        "市场中性，等待进一步确认",
    ),
    "aggressive": (
        "市场偏强，但仍需等待后续版本完善判断",
    ),
}

_RISK_WARNINGS_POOL: tuple[str, ...] = (
    "本版本为最小骨架，不输出具体个股买卖建议",
    "数据质量不足或市场/情绪判断缺失时，应以观察为主",
    "请勿据此自动交易；本系统未接入任何实盘交易接口",
)

_OBSERVATION_POOL: tuple[str, ...] = (
    "观察后续交易日数据是否补齐",
    "观察市场指数（待 V1.5.1 引入）的走势确认",
    "观察情绪周期指标（待 V1.5.2 引入）的修复信号",
    "观察板块强度排名（待 V1.5.3 / V1.5.4 完善）的连续性",
)

_INVALIDATION_POOL: tuple[str, ...] = (
    "若数据质量降级为不建议分析，本决策卡失效应以观察为主",
    "若市场/情绪判断口径在后续版本调整，本卡片结论需重新生成",
)


# ── Bias decision ───────────────────────────────────────────────────────────────

# Data-quality verdicts that block any aggressive posture.
_BLOCKING_QUALITY: frozenset[str] = frozenset({
    "risky", "not_recommended", "unavailable",
})

# Market / sentiment tokens considered "decided".
_MARKET_DECIDED: frozenset[str] = frozenset({"weak", "neutral", "strong"})
_SENTIMENT_DECIDED: frozenset[str] = frozenset({
    "ice", "repair", "rising", "climax", "cooling", "declining", "mixed",
})


def decide_overall_bias(
    market_state: str | None,
    sentiment_cycle: str | None,
    sector_count: int,
    data_quality_status: str | None,
) -> str:
    """Return one of the overall_bias enum tokens.

    Rules (conservative precedence):
    1. data_quality_status ∈ {risky, not_recommended, unavailable} → DEFENSIVE.
    2. market_state == "unknown" → DEFENSIVE (or UNKNOWN if data also unknown).
    3. sentiment_cycle == "unknown" → DEFENSIVE.
    4. sector_count == 0 → DEFENSIVE.
    5. only if ALL three are decided AND data quality is healthy/usable →
       ``neutral`` or ``aggressive``. ``aggressive`` requires market strong
       AND sentiment rising/climax AND >0 sectors (not reachable in V1.5.0
       because market & sentiment stay unknown).
    """
    ms = market_state or "unknown"
    sc = sentiment_cycle or "unknown"
    qs = data_quality_status or "unknown"

    if qs in _BLOCKING_QUALITY:
        return OVERALL_DEFENSIVE
    if ms == "unknown" or sc == "unknown":
        return OVERALL_DEFENSIVE
    if sector_count <= 0:
        return OVERALL_DEFENSIVE

    # All decided + healthy/usable quality → may emit neutral/aggressive.
    if ms == "strong" and sc in ("rising", "climax") and sector_count > 0:
        return OVERALL_AGGRESSIVE
    return OVERALL_NEUTRAL


# ── Textual outputs ──────────────────────────────────────────────────────────────

def build_risk_warnings(
    market_state: str | None = None,
    sentiment_cycle: str | None = None,
    sector_count: int = 0,
    data_quality_status: str | None = None,
) -> list[str]:
    """Assemble risk_warnings from the whitelist pool.

    Adds one extra warning when data quality is blocking.
    """
    out = list(_RISK_WARNINGS_POOL)
    if (data_quality_status or "unknown") in _BLOCKING_QUALITY:
        out.append("数据质量风险较高，不建议据此做任何方向性判断")
    if (market_state or "unknown") == "unknown":
        out.append("市场状态未确认，本版本仅作骨架展示")
    return out


def build_suggested_actions(
    market_state: str | None,
    sentiment_cycle: str | None,
    sector_count: int,
    data_quality_status: str | None,
) -> list[str]:
    """Assemble suggested_actions from the whitelist pool (never forbidden words)."""
    ms = market_state or "unknown"
    sc = sentiment_cycle or "unknown"
    qs = data_quality_status or "unknown"

    actions: list[str] = []
    if qs in _BLOCKING_QUALITY:
        actions.extend(_SUGGESTED_ACTIONS_POOL["insufficient"])
    if ms == "unknown":
        actions.extend(_SUGGESTED_ACTIONS_POOL["market_unknown"])
    if sc == "unknown":
        actions.extend(_SUGGESTED_ACTIONS_POOL["sentiment_unknown"])
    if sector_count <= 0:
        actions.extend(_SUGGESTED_ACTIONS_POOL["sector_empty"])

    # De-dup, preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            unique.append(a)

    if not unique:
        # All decided + non-blocking quality → neutral/aggressive hint.
        if ms == "strong":
            unique = list(_SUGGESTED_ACTIONS_POOL["aggressive"])
        else:
            unique = list(_SUGGESTED_ACTIONS_POOL["neutral"])

    # Defensive: verify no forbidden word slipped in.
    assert not _contains_forbidden(unique), "suggested_actions leak forbidden words"
    return unique


def build_observation_conditions(
    market_state: str | None = None,
    sentiment_cycle: str | None = None,
    sector_count: int = 0,
    data_quality_status: str | None = None,
) -> list[str]:
    """Assemble observation_conditions from the whitelist pool."""
    return list(_OBSERVATION_POOL)


def build_invalidation_conditions(
    market_state: str | None = None,
    sentiment_cycle: str | None = None,
    sector_count: int = 0,
    data_quality_status: str | None = None,
) -> list[str]:
    """Assemble invalidation_conditions from the whitelist pool."""
    return list(_INVALIDATION_POOL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _contains_forbidden(texts: list[str]) -> bool:
    """Return True if any forbidden word appears in any text."""
    for t in texts:
        for w in FORBIDDEN_WORDS:
            if w in t:
                return True
    return False


def ensure_no_forbidden(texts: list[str]) -> None:
    """Helper for callers/tests: assert no forbidden words in a list."""
    assert not _contains_forbidden(texts), (
        f"forbidden action words leaked: {_forbidden_found(texts)}"
    )


def _forbidden_found(texts: list[str]) -> list[str]:
    found: list[str] = []
    for t in texts:
        for w in FORBIDDEN_WORDS:
            if w in t and w not in found:
                found.append(w)
    return found
