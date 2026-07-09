"""V1.5.6 sector diagnosis rules — aggregate market/sentiment/strength/mainline.

Pure functions. All thresholds centralised.
"""
from __future__ import annotations

from typing import Any

from src.sector.sector_diagnosis_types import (
    DIAG_HEALTHY, DIAG_WATCH, DIAG_WAIT, DIAG_CAUTIOUS,
    DIAG_HIGH_RISK, DIAG_COOLING, DIAG_AVOID, DIAG_UNKNOWN,
    FIT_GOOD, FIT_NEUTRAL, FIT_POOR, FIT_UNKNOWN,
    TREND_EMERGING, TREND_STRENGTHENING, TREND_STRONG,
    TREND_OVERHEAT, TREND_COOLING, TREND_WEAKENING, TREND_UNKNOWN,
    LEADER_PENDING,
    ODDS_GOOD, ODDS_NORMAL, ODDS_POOR, ODDS_HIGH_RISK, ODDS_UNKNOWN,
    ACTION_OBSERVE, ACTION_FOCUS_WATCH, ACTION_WAIT_PULLBACK,
    ACTION_CAUTIOUS_WATCH, ACTION_AVOID_CHASE, ACTION_CANCEL_WATCH, ACTION_UNKNOWN,
)
from src.sector.sector_mainline_types import (
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
    RISK_OVERHEAT, RISK_ONE_DAY_SPIKE, RISK_RANK_DROP,
    RISK_TURNOVER_ABNORMAL, RISK_BREADTH_WEAK, RISK_BIG_LOSS_RISING,
)


def diagnose_sector(
    market_env: dict | None,
    sentiment_cycle: dict | None,
    strength: dict | None,
    mainline: dict | None,
) -> dict[str, Any]:
    """Aggregate all signals into a sector diagnosis.

    Args:
        market_env: V1.5.1 market environment dict (market_state, risk_level)
        sentiment_cycle: V1.5.2 sentiment cycle dict (sentiment_cycle)
        strength: V1.5.4 strength dict (strength_score, returns, etc.)
        mainline: V1.5.5 mainline dict (mainline_status, mainline_score, etc.)

    Returns:
        Complete diagnosis dict.
    """
    missing: list[str] = []
    reasons: list[str] = []
    risk_flags: list[str] = []

    # Check data availability
    if strength is None or not strength:
        missing.append("sector_strength")
    if mainline is None or not mainline:
        missing.append("sector_mainline")
    if market_env is None or not market_env:
        missing.append("market_environment")
    if sentiment_cycle is None or not sentiment_cycle:
        missing.append("sentiment_cycle")

    if not strength and not mainline:
        return _unknown_result(missing, ["板块数据不足，无法进行问诊"])

    # Extract key signals
    m_status = (mainline or {}).get("mainline_status", MAINLINE_UNKNOWN)
    m_score = (mainline or {}).get("mainline_score", 0)
    m_confidence = (mainline or {}).get("confidence", "low")
    s_score = (strength or {}).get("strength_score", 0)
    s_level = (strength or {}).get("strength_level", "unknown")
    m_risk_flags = (mainline or {}).get("risk_flags", [])
    risk_flags.extend(m_risk_flags)

    # Market fit
    market_fit = _calc_market_fit(market_env)
    reasons.append(f"市场环境适配度: {_fit_label(market_fit)}")

    # Sentiment fit
    sentiment_fit = _calc_sentiment_fit(sentiment_cycle)
    reasons.append(f"情绪周期适配度: {_fit_label(sentiment_fit)}")

    # Mainline probability
    m_prob = _calc_mainline_probability(m_status, m_score, m_confidence)

    # Trend stage
    trend = _calc_trend_stage(strength, mainline)

    # Buy point odds
    odds = _calc_buy_point_odds(m_status, s_score, market_fit, sentiment_fit, m_risk_flags)

    # Risk level
    risk = _calc_risk_level(m_status, s_score, m_risk_flags, market_fit, sentiment_fit)

    # Diagnosis status
    diag_status = _calc_diagnosis_status(
        m_status, s_score, market_fit, sentiment_fit, m_risk_flags, risk,
    )

    # Suggested action
    action = _calc_suggested_action(diag_status, m_status, market_fit, sentiment_fit, odds)

    # Action hint
    hint = _build_action_hint(
        diag_status, m_status, s_level, market_fit, sentiment_fit, trend, odds,
    )

    # Observation & invalidation conditions
    obs = _build_observation_conditions(m_status, trend, market_fit, sentiment_fit)
    inval = _build_invalidation_conditions(m_status, s_score, m_risk_flags)

    # Build strength_rank dict
    rank_info = {
        "rank_overall": (mainline or {}).get("rank_overall", 0),
        "persistence_days": (mainline or {}).get("persistence_days", 0),
    }

    # Reasons aggregation
    if m_status == MAINLINE_CONFIRMED:
        reasons.append("板块主线状态为确认主线，持续性和强度较好")
    elif m_status == MAINLINE_POTENTIAL:
        reasons.append("板块具有潜在主线特征，但持续性尚需确认")
    elif m_status == MAINLINE_ONE_DAY:
        reasons.append("板块单日异动明显，缺乏持续性，更像一日游题材")
    elif m_status == MAINLINE_COOLING:
        reasons.append("板块正在降温，排名和强度回落")
    elif m_status == MAINLINE_HIGH_RISK:
        reasons.append("板块强度虽高但风险信号明显")
    elif m_status == MAINLINE_NEUTRAL:
        reasons.append("板块表现一般，无明确主线特征")

    if market_fit == FIT_POOR:
        reasons.append("当前市场环境不支持积极进攻")
    if sentiment_fit == FIT_POOR:
        reasons.append("当前情绪周期不支持接力或追高")

    reasons.append("V1.5.6 尚未识别具体龙头结构，需要 V1.6.1 补充")

    return {
        "diagnosis_status": diag_status,
        "mainline_status": m_status,
        "mainline_score": m_score,
        "mainline_probability": m_prob,
        "market_fit": market_fit,
        "sentiment_fit": sentiment_fit,
        "strength_score": s_score,
        "strength_level": s_level,
        "strength_rank": rank_info,
        "trend_stage": trend,
        "leader_structure": LEADER_PENDING,
        "buy_point_odds": odds,
        "risk_level": risk,
        "suggested_action": action,
        "action_hint": hint,
        "observation_conditions": obs,
        "invalidation_conditions": inval,
        "risk_flags": risk_flags,
        "missing_indicator_names": missing,
        "reasons": reasons,
    }


# ── Sub-calculations ────────────────────────────────────────────────────────


def _calc_market_fit(market: dict | None) -> str:
    if not market:
        return FIT_UNKNOWN
    state = market.get("market_state", "unknown")
    if state == "attack":
        return FIT_GOOD
    elif state == "neutral":
        return FIT_NEUTRAL
    elif state in ("defense", "high_risk"):
        return FIT_POOR
    return FIT_UNKNOWN


def _calc_sentiment_fit(sentiment: dict | None) -> str:
    if not sentiment:
        return FIT_UNKNOWN
    cycle = sentiment.get("sentiment_cycle", "unknown")
    if cycle in ("warming", "repair"):
        return FIT_GOOD
    elif cycle == "climax":
        return FIT_NEUTRAL
    elif cycle in ("cooling", "retreat", "ice_point"):
        return FIT_POOR
    elif cycle == "chaotic":
        return FIT_NEUTRAL
    return FIT_UNKNOWN


def _calc_mainline_probability(status: str, score: int, confidence: str) -> int:
    if status == MAINLINE_CONFIRMED:
        base = 70 + score // 3  # 70-100
    elif status == MAINLINE_POTENTIAL:
        base = 40 + score // 3  # 40-70
    elif status == MAINLINE_ONE_DAY:
        base = 15 + score // 4  # 15-40
    elif status in (MAINLINE_COOLING, MAINLINE_HIGH_RISK):
        base = max(5, 30 - score // 3)  # 5-30
    elif status == MAINLINE_NEUTRAL:
        base = 5 + score // 5  # 5-25
    else:
        return 0

    if confidence == "high":
        base = min(100, base + 5)
    elif confidence == "low":
        base = max(0, base - 10)

    return max(0, min(100, int(base)))


def _calc_trend_stage(strength: dict | None, mainline: dict | None) -> str:
    if not strength:
        return TREND_UNKNOWN

    r3 = strength.get("return_3d")
    r5 = strength.get("return_5d")
    rs5 = strength.get("relative_strength_5d")
    up_ratio = strength.get("up_ratio", 0)
    t20 = strength.get("turnover_ratio_20d")
    risk_flags = (mainline or {}).get("risk_flags", [])

    if RISK_OVERHEAT in risk_flags:
        return TREND_OVERHEAT
    if RISK_RANK_DROP in risk_flags:
        return TREND_COOLING
    if r5 is not None and r5 < -3:
        return TREND_WEAKENING

    if r3 is not None and r5 is not None and rs5 is not None:
        if r5 > 5 and rs5 > 3 and up_ratio > 0.6:
            return TREND_STRONG
        if r3 > 2 and r5 > 2 and rs5 > 1:
            return TREND_STRENGTHENING
        if r3 > 1 or r5 > 1:
            return TREND_EMERGING

    return TREND_UNKNOWN


def _calc_buy_point_odds(
    m_status: str, s_score: int, market_fit: str, sentiment_fit: str,
    risk_flags: list[str],
) -> str:
    if RISK_OVERHEAT in risk_flags or m_status == MAINLINE_HIGH_RISK:
        return ODDS_HIGH_RISK
    if m_status in (MAINLINE_COOLING, MAINLINE_ONE_DAY):
        return ODDS_POOR
    if market_fit == FIT_POOR or sentiment_fit == FIT_POOR:
        return ODDS_POOR
    if m_status == MAINLINE_CONFIRMED and s_score >= 80:
        if market_fit == FIT_GOOD:
            return ODDS_GOOD
        return ODDS_NORMAL
    if m_status == MAINLINE_POTENTIAL:
        return ODDS_NORMAL
    if m_status == MAINLINE_NEUTRAL:
        return ODDS_POOR
    return ODDS_UNKNOWN


def _calc_risk_level(
    m_status: str, s_score: int, risk_flags: list[str],
    market_fit: str, sentiment_fit: str,
) -> str:
    if m_status == MAINLINE_HIGH_RISK:
        return "extreme"
    if RISK_OVERHEAT in risk_flags or RISK_TURNOVER_ABNORMAL in risk_flags:
        return "high"
    if m_status == MAINLINE_COOLING:
        return "high"
    if market_fit == FIT_POOR or sentiment_fit == FIT_POOR:
        return "high"
    if m_status == MAINLINE_ONE_DAY:
        return "medium"
    if m_status == MAINLINE_POTENTIAL:
        return "medium"
    if m_status == MAINLINE_CONFIRMED:
        return "low" if s_score >= 85 else "medium"
    return "unknown"


def _calc_diagnosis_status(
    m_status: str, s_score: int, market_fit: str, sentiment_fit: str,
    risk_flags: list[str], risk_level: str,
) -> str:
    if m_status == MAINLINE_UNKNOWN:
        return DIAG_UNKNOWN
    if m_status == MAINLINE_HIGH_RISK:
        return DIAG_HIGH_RISK
    if m_status == MAINLINE_COOLING:
        return DIAG_COOLING
    if m_status == MAINLINE_ONE_DAY:
        return DIAG_CAUTIOUS if market_fit == FIT_POOR else DIAG_WATCH
    if m_status == MAINLINE_POTENTIAL:
        return DIAG_WATCH
    if m_status == MAINLINE_CONFIRMED:
        if risk_level == "low":
            return DIAG_HEALTHY
        if market_fit == FIT_POOR or sentiment_fit == FIT_POOR:
            return DIAG_CAUTIOUS
        return DIAG_WATCH
    return DIAG_WAIT


def _calc_suggested_action(
    diag_status: str, m_status: str, market_fit: str, sentiment_fit: str, odds: str,
) -> str:
    if diag_status == DIAG_HEALTHY:
        return ACTION_FOCUS_WATCH
    if diag_status == DIAG_WATCH:
        return ACTION_OBSERVE if market_fit != FIT_GOOD else ACTION_FOCUS_WATCH
    if diag_status == DIAG_WAIT:
        return ACTION_WAIT_PULLBACK
    if diag_status == DIAG_CAUTIOUS:
        return ACTION_CAUTIOUS_WATCH
    if diag_status in (DIAG_HIGH_RISK, DIAG_AVOID):
        return ACTION_AVOID_CHASE
    if diag_status == DIAG_COOLING:
        return ACTION_CANCEL_WATCH
    return ACTION_UNKNOWN


def _build_action_hint(
    diag_status: str, m_status: str, s_level: str,
    market_fit: str, sentiment_fit: str, trend: str, odds: str,
) -> str:
    hints = {
        (DIAG_HEALTHY, MAINLINE_CONFIRMED): "该板块属于确认主线，强度和持续性较好，适合重点观察，但仍需注意市场环境和追高风险。",
        (DIAG_WATCH, MAINLINE_CONFIRMED): "该板块属于确认主线，强度和持续性较好，但当前市场或情绪环境一般，适合观察等待更好的介入时机。",
        (DIAG_WATCH, MAINLINE_POTENTIAL): "该板块具有潜在主线特征，近期明显走强，建议观察后续排名和成交是否继续确认，暂时不宜追高。",
        (DIAG_CAUTIOUS, MAINLINE_ONE_DAY): "该板块单日异动明显，但缺少持续性，目前更像一日游题材，不建议追高。",
        (DIAG_COOLING, MAINLINE_COOLING): "该板块正在降温，强度和排名回落，建议降低关注度，等待回暖信号。",
        (DIAG_HIGH_RISK, MAINLINE_HIGH_RISK): "该板块短期过热，风险信号明显，建议停止追高和接力，等待风险释放。",
        (DIAG_WAIT, MAINLINE_NEUTRAL): "该板块表现一般，无明确主线特征，建议暂时观望，等待更明确的信号。",
    }
    key = (diag_status, m_status)
    if key in hints:
        hint = hints[key]
    else:
        hint = "数据不足，暂不建议对该板块做明确判断。"

    if market_fit == FIT_POOR:
        hint += " 当前市场环境偏弱，应降低进攻性。"
    if sentiment_fit == FIT_POOR:
        hint += " 当前情绪环境不支持接力追高。"
    return hint


def _build_observation_conditions(
    m_status: str, trend: str, market_fit: str, sentiment_fit: str,
) -> list[str]:
    conditions: list[str] = []
    if m_status in (MAINLINE_POTENTIAL, MAINLINE_ONE_DAY):
        conditions.append("后续 2-3 个交易日继续保持强度排名前 10")
        conditions.append("relative_strength_5d 继续为正")
        conditions.append("成交额温和放大而不是单日爆量")
    if m_status == MAINLINE_CONFIRMED:
        conditions.append("relative_strength_5d 继续为正")
        conditions.append("板块上涨家数占比维持较高水平")
    if market_fit == FIT_POOR:
        conditions.append("市场环境从 defense 修复到 neutral 或 attack")
    if sentiment_fit == FIT_POOR:
        conditions.append("情绪周期从 cooling/retreat 修复到 repair/warming")
    if not conditions:
        conditions.append("观察后续交易日强度变化")
    return conditions


def _build_invalidation_conditions(
    m_status: str, s_score: int, risk_flags: list[str],
) -> list[str]:
    conditions: list[str] = []
    if m_status in (MAINLINE_CONFIRMED, MAINLINE_POTENTIAL):
        conditions.append("强度排名跌出前 20")
        conditions.append("mainline_status 转为 cooling_sector")
        conditions.append("relative_strength_5d 转负")
    if m_status == MAINLINE_ONE_DAY:
        conditions.append("连续 2 日强度排名下降")
    conditions.append("risk_flags 出现 overheat / rank_drop / big_loss_rising")
    if not conditions:
        conditions.append("数据持续不足或板块状态无变化")
    return conditions


def _unknown_result(missing: list[str], reasons: list[str]) -> dict:
    return {
        "diagnosis_status": DIAG_UNKNOWN,
        "mainline_status": MAINLINE_UNKNOWN,
        "mainline_score": 0,
        "mainline_probability": 0,
        "market_fit": FIT_UNKNOWN,
        "sentiment_fit": FIT_UNKNOWN,
        "strength_score": 0,
        "strength_level": "unknown",
        "strength_rank": {},
        "trend_stage": TREND_UNKNOWN,
        "leader_structure": LEADER_PENDING,
        "buy_point_odds": ODDS_UNKNOWN,
        "risk_level": "unknown",
        "suggested_action": ACTION_UNKNOWN,
        "action_hint": "数据不足，暂不建议对该板块做明确判断。",
        "observation_conditions": [],
        "invalidation_conditions": [],
        "risk_flags": [],
        "missing_indicator_names": missing,
        "reasons": reasons,
    }


def _fit_label(fit: str) -> str:
    return {"good": "好", "neutral": "中性", "poor": "差", "unknown": "未知"}.get(fit, fit)
