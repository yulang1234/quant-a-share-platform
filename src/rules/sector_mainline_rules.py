"""V1.5.5 sector mainline rules — pure classification functions.

All thresholds are centralised for easy adjustment (V2.3 rule-version config).
"""
from __future__ import annotations

from typing import Any

from src.sector.sector_mainline_types import (
    RISK_OVERHEAT, RISK_ONE_DAY_SPIKE, RISK_RANK_DROP,
    RISK_TURNOVER_ABNORMAL, RISK_BREADTH_WEAK,
    RISK_BIG_LOSS_RISING, RISK_DATA_INSUFFICIENT,
    RISK_PERSISTENCE_INSUFFICIENT,
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW,
)

# ── Persistence thresholds ──────────────────────────────────────────────────

PERSISTENCE_LOOKBACK = 5          # number of trading days to look back
PERSISTENCE_TOP_N = 20            # "top N" threshold for persistence counting
PERSISTENCE_CONFIRMED_MIN = 3     # min days in Top N for confirmed mainline
PERSISTENCE_POTENTIAL_MIN = 1     # min days for potential (recent)

# ── Stability scoring ───────────────────────────────────────────────────────

STABILITY_WEIGHT_RECENT = 0.5     # weight for most recent ranks
STABILITY_MAX_RANK_JUMP = 15      # jump > this → flag as one_day_spike

# ── Classification thresholds ───────────────────────────────────────────────

MAINLINE_SCORE_CONFIRMED_MIN = 75
MAINLINE_SCORE_POTENTIAL_MIN = 55
MAINLINE_SCORE_ONE_DAY_MIN = 40

TURNOVER_ABNORMAL_RATIO = 2.0     # turnover > 2x 20d avg → abnormal
TURNOVER_WARM_RATIO = 1.1         # turnover > 1.1x → warming

OVERHEAT_STRENGTH_MIN = 85        # strength > 85 → potential overheat
OVERHEAT_RETURN_1D_MIN = 5.0      # single-day return > 5% → overheat warning

BREADTH_WEAK_RATIO = 0.45         # up_ratio below this → breadth weak
BIG_LOSS_RISING_MIN = 3           # big_loss_count >= this → risk flag


def classify_mainline(
    sector_today: dict[str, Any],
    historical_ranks: list[int],
    historical_strengths: list[dict],
) -> dict[str, Any]:
    """Classify a sector's mainline status.

    Args:
        sector_today: today's strength indicators (SectorStrengthResult as dict)
        historical_ranks: rank_overall for last N days (most recent last)
        historical_strengths: list of strength indicator dicts for last N days

    Returns:
        dict with mainline_status, mainline_score, confidence, risk_flags, reasons.
    """
    missing: list[str] = []
    risk_flags: list[str] = []
    reasons: list[str] = []

    # 1. Calculate persistence
    persistence = _calc_persistence(historical_ranks)
    if persistence is None:
        missing.append("historical_ranks")
        persistence = 0

    # 2. Calculate rank stability
    stability = _calc_stability(historical_ranks, historical_strengths)
    if stability is None:
        missing.append("rank_stability")
        stability = 0

    # 3. Calculate relative strength score
    rel_score = _calc_rel_strength_score(sector_today)
    if rel_score is None:
        missing.append("relative_strength")
        rel_score = 0

    # 4. Confirmations
    turnover_ok = _check_turnover(sector_today)
    breadth_ok = _check_breadth(sector_today)
    limit_up_ok = _check_limit_up(sector_today)

    # 5. Risk flags
    risk_flags.extend(_detect_risk_flags(sector_today, historical_ranks, historical_strengths))

    # 6. Compute mainline score (0-100)
    mainline_score = _compute_mainline_score(
        sector_today, persistence, stability, rel_score,
        turnover_ok, breadth_ok, limit_up_ok,
    )

    # 7. Classify
    status, confidence, class_reasons = _classify(
        sector_today, mainline_score, persistence, stability,
        historical_ranks, risk_flags, turnover_ok, breadth_ok, limit_up_ok,
    )
    reasons.extend(class_reasons)

    return {
        "mainline_status": status,
        "mainline_score": mainline_score,
        "confidence": confidence,
        "persistence_days": persistence,
        "rank_stability_score": stability,
        "relative_strength_score": rel_score,
        "turnover_confirmation": turnover_ok,
        "breadth_confirmation": breadth_ok,
        "limit_up_confirmation": limit_up_ok,
        "risk_flags": risk_flags,
        "missing_indicator_names": missing,
        "reasons": reasons,
    }


# ── Sub-calculations ────────────────────────────────────────────────────────


def _calc_persistence(ranks: list[int]) -> int | None:
    """Count how many days in the last PERSISTENCE_LOOKBACK the sector was in top N."""
    if not ranks:
        return None
    recent = ranks[-PERSISTENCE_LOOKBACK:]
    return sum(1 for r in recent if 0 < r <= PERSISTENCE_TOP_N)


def _calc_stability(ranks: list[int], strengths: list[dict]) -> int | None:
    """Compute rank stability score (0-100).

    High stability = consistently top-ranked, no sudden jumps.
    """
    if not ranks or len(ranks) < 2:
        return None

    score = 50  # base

    # Consistency: how many recent days in top 20?
    recent = ranks[-PERSISTENCE_LOOKBACK:]
    consistent_days = sum(1 for r in recent if 0 < r <= 20)
    score += consistent_days * 8

    # Penalize sudden jumps (today rank >> yesterday rank, but from low position)
    if len(ranks) >= 2:
        prev_avg = sum(ranks[-4:-1]) / max(len(ranks[-4:-1]), 1) if len(ranks) >= 3 else ranks[-2]
        today = ranks[-1]
        if today > 0 and prev_avg > 0 and prev_avg - today > STABILITY_MAX_RANK_JUMP:
            score += 15  # positive jump (improving)
        elif today > 0 and prev_avg > 0 and today - prev_avg > STABILITY_MAX_RANK_JUMP:
            score -= 20  # negative jump (declining)

    return max(0, min(100, score))


def _calc_rel_strength_score(today: dict) -> int | None:
    """Compute relative strength score (0-100)."""
    rel_scores = []
    for period in ["3d", "5d", "10d", "20d"]:
        val = today.get(f"relative_strength_{period}")
        if val is not None:
            rel_scores.append(val)

    if not rel_scores:
        return None

    avg_rel = sum(rel_scores) / len(rel_scores)
    # Map: -5 → 0, 0 → 50, +5 → 100
    score = max(0, min(100, int((avg_rel + 5.0) / 10.0 * 100)))
    return score


def _check_turnover(today: dict) -> bool:
    """Check if turnover confirms strength (not abnormal)."""
    t20 = today.get("turnover_ratio_20d")
    if t20 is None:
        return False
    return TURNOVER_WARM_RATIO <= t20 <= TURNOVER_ABNORMAL_RATIO


def _check_breadth(today: dict) -> bool:
    """Check if breadth (up_ratio) is healthy."""
    up_ratio = today.get("up_ratio", 0)
    return up_ratio is not None and up_ratio >= BREADTH_WEAK_RATIO


def _check_limit_up(today: dict) -> bool:
    """Check if there are limit-ups in the sector."""
    lu = today.get("limit_up_count", 0)
    return lu >= 1


def _detect_risk_flags(
    today: dict, ranks: list[int], strengths: list[dict],
) -> list[str]:
    """Detect risk flags from today's indicators and history."""
    flags: list[str] = []

    strength = today.get("strength_score", 0)
    return_1d = today.get("avg_pct_chg", 0)
    t20 = today.get("turnover_ratio_20d")
    up_ratio = today.get("up_ratio", 0)
    big_loss = today.get("big_loss_count", 0)

    # Overheat
    if strength >= OVERHEAT_STRENGTH_MIN and return_1d >= OVERHEAT_RETURN_1D_MIN:
        flags.append(RISK_OVERHEAT)

    # One-day spike detection: more conservative
    if ranks and len(ranks) >= 3:
        prev_ranks = ranks[-3:-1]
        today_rank = ranks[-1]
        if prev_ranks and today_rank > 0:
            avg_prev = sum(prev_ranks) / len(prev_ranks)
            # Only flag as spike if previous ranks were VERY low and today is VERY high
            if avg_prev > 40 and today_rank <= 10:
                flags.append(RISK_ONE_DAY_SPIKE)

    # Turnover abnormal
    if t20 is not None and t20 > TURNOVER_ABNORMAL_RATIO:
        flags.append(RISK_TURNOVER_ABNORMAL)

    # Breadth weak
    if up_ratio is not None and up_ratio < BREADTH_WEAK_RATIO:
        flags.append(RISK_BREADTH_WEAK)

    # Big loss rising
    if big_loss >= BIG_LOSS_RISING_MIN:
        flags.append(RISK_BIG_LOSS_RISING)

    # Rank drop
    if len(ranks) >= 3:
        recent_ranks = ranks[-3:]
        if len(recent_ranks) == 3 and recent_ranks[0] <= 10 and recent_ranks[-1] > 20:
            flags.append(RISK_RANK_DROP)

    # Persistence insufficient (detected later in classify)
    return flags


def _compute_mainline_score(
    today: dict, persistence: int, stability: int,
    rel_score: int, turnover_ok: bool, breadth_ok: bool, limit_up_ok: bool,
) -> int:
    """Compute 0-100 mainline score."""
    score = 0.0

    # Today's strength (30%)
    strength = today.get("strength_score", 0)
    score += strength * 0.30

    # Persistence (25%)
    persistence_norm = min(persistence / PERSISTENCE_CONFIRMED_MIN, 1.0) * 100
    score += persistence_norm * 0.25

    # Stability (15%)
    score += stability * 0.15

    # Relative strength (15%)
    score += rel_score * 0.15

    # Confirmations (15% total)
    score += (10.0 if turnover_ok else 0.0)
    score += (3.0 if breadth_ok else 0.0)
    score += (2.0 if limit_up_ok else 0.0)

    return max(0, min(100, int(round(score))))


def _classify(
    today: dict, score: int, persistence: int, stability: int,
    ranks: list[int], risk_flags: list[str],
    turnover_ok: bool, breadth_ok: bool, limit_up_ok: bool,
) -> tuple[str, str, list[str]]:
    """Classify sector into mainline status."""
    reasons: list[str] = []
    strength = today.get("strength_score", 0)

    # Unknown
    if not today or today.get("valid_stock_count", 0) == 0:
        return MAINLINE_UNKNOWN, CONFIDENCE_LOW, ["板块数据不足，无法判断主线状态"]

    # High risk
    if RISK_OVERHEAT in risk_flags and RISK_TURNOVER_ABNORMAL in risk_flags:
        reasons.append("板块强度过高且成交异常放大，追高风险明显")
        if RISK_BIG_LOSS_RISING in risk_flags:
            reasons.append("板块内大跌个股增加，分化风险上升")
        return MAINLINE_HIGH_RISK, CONFIDENCE_HIGH, reasons

    if RISK_OVERHEAT in risk_flags and strength >= 85:
        reasons.append("板块短期过热，需警惕回调风险")
        return MAINLINE_HIGH_RISK, CONFIDENCE_MEDIUM, reasons

    # Cooling
    if RISK_RANK_DROP in risk_flags:
        reasons.append("板块排名明显下滑，强度回落")
        if not breadth_ok:
            reasons.append("板块上涨家数占比下降，赚钱效应减弱")
        return MAINLINE_COOLING, CONFIDENCE_MEDIUM, reasons

    if persistence <= 0 and ranks and len(ranks) >= 3:
        prev_ranks = ranks[-3:-1]
        if prev_ranks and min(prev_ranks) <= 15 and (ranks[-1] > 25 if ranks[-1] > 0 else True):
            reasons.append("板块排名从高位回落，可能进入降温阶段")
            return MAINLINE_COOLING, CONFIDENCE_MEDIUM, reasons

    # One-day theme — only when really a spike with no persistence
    if RISK_ONE_DAY_SPIKE in risk_flags and persistence <= 1:
        reasons.append("板块单日突然走强，但此前排名较低，缺乏持续性")
        if not turnover_ok:
            reasons.append("成交额异常放大，疑似短期炒作")
        return MAINLINE_ONE_DAY, CONFIDENCE_MEDIUM, reasons

    if strength >= 60 and persistence <= 1 and len(ranks) >= 3:
        prev_avg = sum(ranks[-3:-1]) / max(len(ranks[-3:-1]), 1) if len(ranks) >= 3 else 999
        if prev_avg > 40:
            reasons.append("单日强度较高但历史排名靠后，可能是一日游题材")
            return MAINLINE_ONE_DAY, CONFIDENCE_MEDIUM, reasons

    # Confirmed mainline
    if score >= MAINLINE_SCORE_CONFIRMED_MIN and persistence >= PERSISTENCE_CONFIRMED_MIN:
        reasons.append("板块连续多日排名靠前，具备主线持续性")
        if stability >= 60:
            reasons.append("排名稳定性较好，不是单日暴冲")
        if turnover_ok:
            reasons.append("成交额温和放大，资金确认度较高")
        if breadth_ok:
            reasons.append("板块上涨家数占比较高，内部扩散较好")
        confidence = CONFIDENCE_HIGH if score >= 85 else CONFIDENCE_MEDIUM
        return MAINLINE_CONFIRMED, confidence, reasons

    # Potential mainline
    if score >= MAINLINE_SCORE_POTENTIAL_MIN and persistence >= PERSISTENCE_POTENTIAL_MIN:
        reasons.append("板块强度开始提升，但持续性尚需观察")
        if persistence < PERSISTENCE_CONFIRMED_MIN:
            risk_flags.append(RISK_PERSISTENCE_INSUFFICIENT)
            reasons.append("连续排名靠前天数不足，暂不能确认为主线")
        return MAINLINE_POTENTIAL, CONFIDENCE_MEDIUM, reasons

    if strength >= 65 and persistence == 1:
        reasons.append("板块近日明显走强，关注能否形成持续性")
        return MAINLINE_POTENTIAL, CONFIDENCE_MEDIUM, reasons

    # Neutral
    reasons.append("板块强度一般，无明确主线特征")
    return MAINLINE_NEUTRAL, CONFIDENCE_LOW, reasons
