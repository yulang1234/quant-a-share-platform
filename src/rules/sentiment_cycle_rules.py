"""V1.5.2 sentiment cycle rules — pure judgment functions.

Converts a flat ``indicators`` dict (produced by
:mod:`src.sentiment.sentiment_indicators`) into a structured sentiment-cycle
verdict.

All thresholds are defined as module-level constants so they can be
adjusted without touching logic (and later wired into a config file for
V2.3 rule-version management).

Design principles
-----------------
* **Conservative** — when evidence is missing or ambiguous, default to
  ``unknown`` / ``chaotic``. ``chase_high_allowed`` is almost always False.
* **Readable** — every rule is a named function that returns a partial
  result. The top-level ``judge_sentiment_cycle`` checks phases in order.
* **Explainable** — every rule appends human-readable ``reasons``.
* **No I/O** — pure functions, trivially testable.
"""
from __future__ import annotations

from typing import Any

# ── Configurable thresholds (candidates for V2.3 rule-version config) ─────────

# Ice point
ICE_LIMIT_UP_MAX = 15             # limit_up_count below this → very cold
ICE_LIMIT_DOWN_MIN = 20           # limit_down_count above this → panic
ICE_STRONG_LOSS_EFFECT = True     # strong stock loss effect must be present
ICE_YLU_AVG_PCT_CHG_MAX = -1.0    # yesterday limit-up avg pct_chg below this
ICE_YLU_POSITIVE_RATIO_MAX = 0.35 # low positive ratio among yesterday's limit-ups

# Repair
REPAIR_LIMIT_UP_RISING = True     # limit_up_count > 3d_avg
REPAIR_LIMIT_DOWN_FALLING = True  # limit_down_count < 3d_avg
REPAIR_YLU_AVG_PCT_CHG_MIN = -0.5 # improving from negative
REPAIR_PROMOTION_RATE_MIN = 0.2   # some promotion happening
REPAIR_MAX_HEIGHT_MAX = 4         # still not high enough for attack

# Warming
WARMING_LIMIT_UP_MIN = 20         # significant limit-up activity
WARMING_LIMIT_DOWN_MAX = 10       # low panic
WARMING_MAX_HEIGHT_MIN = 3        # at least 3rd board exists
WARMING_PROMOTION_RATE_MIN = 0.35 # good promotion
WARMING_YLU_AVG_PCT_CHG_MIN = 0.5 # yesterday's limit-ups doing well

# Climax
CLIMAX_LIMIT_UP_MIN = 40          # very high limit-up count
CLIMAX_MAX_HEIGHT_MIN = 5         # high board exists
CLIMAX_PROMOTION_RATE_HIGH = 0.55 # very high promotion (may signal excess)

# Cooling
COOLING_LIMIT_UP_DECLINING = True # limit_up_count < 3d_avg
COOLING_PROMOTION_DECLINING = True # promotion_rate below recent
COOLING_YLU_AVG_PCT_CHG_MAX = 0.0 # yesterday's limit-ups turning flat/neg
COOLING_HIGH_BOARD_NEG_MIN = 1    # at least some high-board stocks negative

# Retreat
RETREAT_LIMIT_DOWN_MIN = 15       # increasing limit-downs
RETREAT_STRONG_LOSS_EFFECT = True # strong stock loss effect
RETREAT_YLU_BIG_LOSS_MIN = 3      # multiple yesterday limit-ups having big losses
RETREAT_YLU_AVG_PCT_CHG_MAX = -1.5 # yesterday limit-ups doing very poorly


# ── Public API ───────────────────────────────────────────────────────────────


def judge_sentiment_cycle(indicators: dict[str, Any]) -> dict[str, Any]:
    """Return a complete sentiment-cycle judgment dict.

    Checks phases in order of precedence:
    1. data insufficient → ``unknown``
    2. retreat → ``retreat``
    3. ice_point → ``ice_point``
    4. chaotic → ``chaotic`` (contradictory signals)
    5. cooling → ``cooling``
    6. repair → ``repair``
    7. warming → ``warming``
    8. climax → ``climax``
    9. fallback → ``chaotic``

    Returns a dict with keys: sentiment_cycle, sentiment_score, risk_level,
    can_try_position, can_attack, relay_risk_level, chase_high_allowed,
    action_hint, reasons.
    """
    if not indicators or not indicators.get("valid_stock_count"):
        return _verdict(
            sentiment_cycle="unknown",
            sentiment_score=0,
            risk_level="unknown",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="unknown",
            chase_high_allowed=False,
            action_hint="数据不足，暂不建议对情绪周期做明确判断。",
            reasons=["缺少当日个股数据，无法进行情绪周期判断"],
        )

    missing = indicators.get("missing_indicator_names") or []
    reasons_all: list[str] = []

    # Note missing indicators
    if missing:
        reasons_all.append(
            f"部分情绪指标因数据不足未参与判断（{', '.join(missing[:5])}"
            + (f" 等共 {len(missing)} 项" if len(missing) > 5 else "")
            + "）"
        )

    # ---- 1. Check retreat first (most dangerous) ----
    retreat_result = _check_retreat(indicators)
    if retreat_result:
        reasons_all.extend(retreat_result["reasons"])
        score = _compute_score(indicators, "retreat")
        return _verdict(
            sentiment_cycle="retreat",
            sentiment_score=score,
            risk_level="extreme",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="extreme",
            chase_high_allowed=False,
            action_hint=_action_hint_for("retreat"),
            reasons=reasons_all,
        )

    # ---- 2. Check ice_point ----
    ice_result = _check_ice_point(indicators)
    if ice_result:
        reasons_all.extend(ice_result["reasons"])
        score = _compute_score(indicators, "ice_point")
        return _verdict(
            sentiment_cycle="ice_point",
            sentiment_score=score,
            risk_level="high",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="high",
            chase_high_allowed=False,
            action_hint=_action_hint_for("ice_point"),
            reasons=reasons_all,
        )

    # ---- 3. Check chaotic (contradictory signals) ----
    chaotic_result = _check_chaotic(indicators)
    if chaotic_result:
        reasons_all.extend(chaotic_result["reasons"])
        score = _compute_score(indicators, "chaotic")
        return _verdict(
            sentiment_cycle="chaotic",
            sentiment_score=score,
            risk_level="high",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="high",
            chase_high_allowed=False,
            action_hint=_action_hint_for("chaotic"),
            reasons=reasons_all,
        )

    # ---- 4. Check cooling ----
    cooling_result = _check_cooling(indicators)
    if cooling_result:
        reasons_all.extend(cooling_result["reasons"])
        score = _compute_score(indicators, "cooling")
        return _verdict(
            sentiment_cycle="cooling",
            sentiment_score=score,
            risk_level="high",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="high",
            chase_high_allowed=False,
            action_hint=_action_hint_for("cooling"),
            reasons=reasons_all,
        )

    # ---- 5. Check climax ----
    climax_result = _check_climax(indicators)
    if climax_result:
        reasons_all.extend(climax_result["reasons"])
        score = _compute_score(indicators, "climax")
        return _verdict(
            sentiment_cycle="climax",
            sentiment_score=score,
            risk_level="medium",
            can_try_position=False,
            can_attack=False,
            relay_risk_level="high",
            chase_high_allowed=False,
            action_hint=_action_hint_for("climax"),
            reasons=reasons_all,
        )

    # ---- 6. Check repair ----
    repair_result = _check_repair(indicators)
    if repair_result:
        reasons_all.extend(repair_result["reasons"])
        score = _compute_score(indicators, "repair")
        return _verdict(
            sentiment_cycle="repair",
            sentiment_score=score,
            risk_level="medium",
            can_try_position=True,
            can_attack=False,
            relay_risk_level="medium",
            chase_high_allowed=False,
            action_hint=_action_hint_for("repair"),
            reasons=reasons_all,
        )

    # ---- 7. Check warming ----
    warming_result = _check_warming(indicators)
    if warming_result:
        reasons_all.extend(warming_result["reasons"])
        score = _compute_score(indicators, "warming")
        # chase_high: only in strong warming with low risk
        chase = _check_chase_high_allowed(indicators)
        return _verdict(
            sentiment_cycle="warming",
            sentiment_score=score,
            risk_level="medium",
            can_try_position=True,
            can_attack=True,
            relay_risk_level="medium",
            chase_high_allowed=chase,
            action_hint=_action_hint_for("warming", chase),
            reasons=reasons_all,
        )

    # ---- 8. Fallback: chaotic when signals are mixed ----
    _add_fallback_reasons(indicators, reasons_all)
    score = _compute_score(indicators, "chaotic")
    return _verdict(
        sentiment_cycle="chaotic",
        sentiment_score=score,
        risk_level="medium",
        can_try_position=False,
        can_attack=False,
        relay_risk_level="high",
        chase_high_allowed=False,
        action_hint=_action_hint_for("chaotic"),
        reasons=reasons_all,
    )


# ── Rule functions ───────────────────────────────────────────────────────────


def _check_retreat(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if retreat conditions are detected.

    Key distinction from ice_point: retreat = actively getting WORSE
    (declining from a higher state), ice_point = already at BOTTOM.

    Retreat requires evidence of TREND deterioration:
    - limit_down increasing vs 3d/5d avg
    - limit_up decreasing vs 3d/5d avg
    """
    reasons: list[str] = []
    hit_count = 0
    required = 3

    # Must have trend evidence: things are getting WORSE
    has_trend = False

    limit_down = ind.get("limit_down_count", 0)
    ld_3d = ind.get("limit_down_count_3d_avg")
    if ld_3d is not None and limit_down > ld_3d * 1.2 and limit_down >= 10:
        reasons.append(f"跌停家数 {limit_down} 较近期均值 {ld_3d:.0f} 明显增加，恐慌扩散")
        hit_count += 1
        has_trend = True
    elif limit_down >= RETREAT_LIMIT_DOWN_MIN:
        reasons.append(f"跌停家数 {limit_down}，恐慌情绪较重")
        hit_count += 1

    limit_up = ind.get("limit_up_count", 0)
    lu_3d = ind.get("limit_up_count_3d_avg")
    if lu_3d is not None and limit_up < lu_3d * 0.6 and lu_3d >= 10:
        reasons.append(f"涨停家数 {limit_up} 较近期均值 {lu_3d:.0f} 大幅下降，赚钱效应退潮")
        hit_count += 1
        has_trend = True

    if ind.get("strong_stock_loss_effect") is True:
        reasons.append("强势股出现明显亏钱效应")
        hit_count += 1

    ylu_big_loss = ind.get("yesterday_limit_up_big_loss_count", 0)
    if ylu_big_loss >= RETREAT_YLU_BIG_LOSS_MIN:
        reasons.append(f"昨日涨停股今日大亏 {ylu_big_loss} 家，短线接力亏钱效应显著")
        hit_count += 1

    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    if ylu_avg is not None and ylu_avg <= RETREAT_YLU_AVG_PCT_CHG_MAX:
        reasons.append(f"昨日涨停股今日平均跌幅 {abs(ylu_avg):.1f}%，亏钱效应显著")
        hit_count += 1

    max_height = ind.get("max_consecutive_limit_up_height", 0)
    if max_height is not None and max_height <= 2:
        reasons.append("连板高度降至2板以下，短线情绪低迷")
        hit_count += 1

    # Retreat requires at least one trend signal (things getting worse)
    if hit_count >= required and has_trend:
        return {"reasons": reasons}
    return None


def _check_ice_point(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if ice point conditions are detected."""
    reasons: list[str] = []
    hit_count = 0
    required = 3

    limit_up = ind.get("limit_up_count", 999)
    if limit_up <= ICE_LIMIT_UP_MAX:
        reasons.append(f"涨停家数仅 {limit_up} 家，市场极度低迷")
        hit_count += 1

    limit_down = ind.get("limit_down_count", 0)
    if limit_down >= ICE_LIMIT_DOWN_MIN:
        reasons.append(f"跌停家数 {limit_down}，恐慌情绪较重")
        hit_count += 1

    if ind.get("strong_stock_loss_effect") is True:
        reasons.append("强势股出现亏钱效应，短线情绪冰冷")
        hit_count += 1

    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    if ylu_avg is not None and ylu_avg <= ICE_YLU_AVG_PCT_CHG_MAX:
        reasons.append(f"昨日涨停股今日平均跌幅 {abs(ylu_avg):.1f}%，接力意愿极弱")
        hit_count += 1

    ylu_pos = ind.get("yesterday_limit_up_positive_ratio")
    if ylu_pos is not None and ylu_pos <= ICE_YLU_POSITIVE_RATIO_MAX:
        reasons.append(f"昨日涨停股今日仅 {ylu_pos:.0%} 收红")
        hit_count += 1

    # Check ad ratio for broad weakness
    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None and ad_ratio < 0.5:
        reasons.append(f"涨跌家数比 {ad_ratio:.2f}，市场全面走弱")
        hit_count += 1

    if hit_count >= required:
        return {"reasons": reasons}
    return None


def _check_chaotic(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if chaotic conditions detected.

    Chaotic = indicators contradict each other:
    - Many limit-ups but also many limit-downs
    - High promotion but strong loss effect
    - Mixed signals without clear direction
    """
    reasons: list[str] = []
    hit_count = 0
    required = 2

    limit_up = ind.get("limit_up_count", 0)
    limit_down = ind.get("limit_down_count", 0)
    if limit_up >= 20 and limit_down >= 15:
        reasons.append(f"涨停 {limit_up} 家但跌停也有 {limit_down} 家，多空分歧严重")
        hit_count += 1

    promotion = ind.get("promotion_rate")
    strong_loss = ind.get("strong_stock_loss_effect")
    if promotion is not None and promotion >= 0.3 and strong_loss is True:
        reasons.append("晋级率尚可但强势股亏钱效应明显，信号矛盾")
        hit_count += 1

    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    ylu_pos = ind.get("yesterday_limit_up_positive_ratio")
    if ylu_avg is not None and ylu_pos is not None:
        if ylu_avg > 1.0 and ylu_pos < 0.5:
            reasons.append("昨日涨停股平均涨幅尚可但多数收跌，赚钱效应不均匀")
            hit_count += 1

    avg_pct = ind.get("avg_pct_chg")
    ad_ratio = ind.get("advance_decline_ratio")
    if avg_pct is not None and ad_ratio is not None:
        if avg_pct > 0.5 and ad_ratio < 0.8:
            reasons.append("平均涨幅为正但下跌家数更多，结构性行情")
            hit_count += 1

    if hit_count >= required:
        return {"reasons": reasons}
    return None


def _check_cooling(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if cooling conditions detected."""
    reasons: list[str] = []
    hit_count = 0
    required = 3

    limit_up = ind.get("limit_up_count", 0)
    lu_3d = ind.get("limit_up_count_3d_avg")
    if lu_3d is not None and limit_up < lu_3d * 0.8:
        reasons.append(f"涨停家数 {limit_up} 较近期均值 {lu_3d:.0f} 下降，情绪降温")
        hit_count += 1

    promotion = ind.get("promotion_rate")
    if promotion is not None and promotion <= 0.2:
        reasons.append(f"晋级率降至 {promotion:.0%}，接力意愿减弱")
        hit_count += 1

    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    if ylu_avg is not None and ylu_avg <= COOLING_YLU_AVG_PCT_CHG_MAX:
        reasons.append("昨日涨停股今日表现转弱")
        hit_count += 1

    high_board_neg = ind.get("high_board_negative_count", 0)
    if high_board_neg >= COOLING_HIGH_BOARD_NEG_MIN:
        reasons.append(f"高位连板股 {high_board_neg} 家转跌，高位股开始亏钱")
        hit_count += 1

    max_height = ind.get("max_consecutive_limit_up_height", 0)
    if max_height is not None and max_height <= 3 and limit_up < 30:
        reasons.append("连板高度下降，赚钱效应减弱")
        hit_count += 1

    if hit_count >= required:
        return {"reasons": reasons}
    return None


def _check_repair(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if repair conditions detected.

    Repair = recovering from lows but NOT yet strong enough for warming.
    Key: must show improvement signals AND not meet warming thresholds.
    """
    reasons: list[str] = []
    hit_count = 0
    required = 3

    limit_up = ind.get("limit_up_count", 0)
    lu_3d = ind.get("limit_up_count_3d_avg")
    limit_down = ind.get("limit_down_count", 0)
    ld_3d = ind.get("limit_down_count_3d_avg")

    # Rising from low
    if lu_3d is not None and limit_up > lu_3d * 1.1:
        reasons.append(f"涨停家数 {limit_up} 较近期回升，情绪修复中")
        hit_count += 1
    elif limit_up >= 8:
        reasons.append(f"涨停家数 {limit_up}，情绪从冰点有所回暖")
        hit_count += 1

    # Falling limit-downs
    if ld_3d is not None and limit_down < ld_3d * 0.9:
        reasons.append(f"跌停家数 {limit_down} 较近期下降，恐慌缓解")
        hit_count += 1
    elif limit_down <= 15:
        reasons.append("跌停家数处于可控范围")
        hit_count += 1

    # Improving yesterday limit-up performance
    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    if ylu_avg is not None and ylu_avg >= REPAIR_YLU_AVG_PCT_CHG_MIN:
        reasons.append("昨日涨停股今日表现有所改善")
        hit_count += 1

    # Some promotion happening
    promotion = ind.get("promotion_rate")
    if promotion is not None and promotion >= REPAIR_PROMOTION_RATE_MIN:
        reasons.append(f"晋级率 {promotion:.0%}，有一定的赚钱效应延续")
        hit_count += 1

    # Not strong loss effect
    if ind.get("strong_stock_loss_effect") is False:
        reasons.append("强势股亏钱效应减弱")
        hit_count += 1

    # NOTE: repair should NOT trigger if warming conditions are clearly met.
    # If we have high board height and strong promotion, skip repair.
    max_height = ind.get("max_consecutive_limit_up_height", 0)
    if max_height is not None and max_height >= 4 and promotion is not None and promotion >= 0.35:
        return None  # Looks more like warming, skip repair

    if max_height is not None and max_height <= REPAIR_MAX_HEIGHT_MAX:
        reasons.append(f"连板高度仅 {max_height} 板，尚未进入强进攻阶段")
        hit_count += 1

    if hit_count >= required:
        return {"reasons": reasons}
    return None


def _check_warming(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if warming conditions detected."""
    reasons: list[str] = []
    hit_count = 0
    required = 3

    limit_up = ind.get("limit_up_count", 0)
    if limit_up >= WARMING_LIMIT_UP_MIN:
        reasons.append(f"涨停家数 {limit_up}，短线活跃度提升")
        hit_count += 1

    limit_down = ind.get("limit_down_count", 0)
    if limit_down <= WARMING_LIMIT_DOWN_MAX:
        reasons.append(f"跌停仅 {limit_down} 家，恐慌情绪低")
        hit_count += 1

    max_height = ind.get("max_consecutive_limit_up_height", 0)
    if max_height is not None and max_height >= WARMING_MAX_HEIGHT_MIN:
        reasons.append(f"连板高度 {max_height} 板，短线赚钱效应增强")
        hit_count += 1

    promotion = ind.get("promotion_rate")
    if promotion is not None and promotion >= WARMING_PROMOTION_RATE_MIN:
        reasons.append(f"晋级率 {promotion:.0%}，接力情绪良好")
        hit_count += 1

    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    if ylu_avg is not None and ylu_avg >= WARMING_YLU_AVG_PCT_CHG_MIN:
        reasons.append(f"昨日涨停股今日平均涨幅 {ylu_avg:.1f}%，赚钱效应延续")
        hit_count += 1

    if ind.get("strong_stock_loss_effect") is False:
        reasons.append("强势股无明显亏钱效应")
        hit_count += 1

    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None and ad_ratio > 1.2:
        reasons.append(f"涨跌家数比 {ad_ratio:.2f}，上涨家数明显多于下跌")
        hit_count += 1

    if hit_count >= required:
        return {"reasons": reasons}
    return None


def _check_climax(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return partial result if climax conditions detected."""
    reasons: list[str] = []
    hit_count = 0
    required = 3

    limit_up = ind.get("limit_up_count", 0)
    if limit_up >= CLIMAX_LIMIT_UP_MIN:
        reasons.append(f"涨停家数 {limit_up} 家，短线情绪高涨")
        hit_count += 1

    max_height = ind.get("max_consecutive_limit_up_height", 0)
    if max_height is not None and max_height >= CLIMAX_MAX_HEIGHT_MIN:
        reasons.append(f"连板高度 {max_height} 板，赚钱效应极强")
        hit_count += 1

    promotion = ind.get("promotion_rate")
    if promotion is not None and promotion >= CLIMAX_PROMOTION_RATE_HIGH:
        reasons.append(f"晋级率高达 {promotion:.0%}，情绪一致性过强")
        hit_count += 1

    # Warning signs within climax
    high_board_neg = ind.get("high_board_negative_count", 0)
    if high_board_neg > 0:
        reasons.append(f"高位连板股 {high_board_neg} 家出现分歧，需警惕次日分化")
        hit_count += 1

    if hit_count >= required:
        # Always add differentiation risk warning for climax
        if "分化" not in " ".join(reasons):
            reasons.append("高潮阶段追高风险上升，谨防次日分化")
        return {"reasons": reasons}
    return None


def _check_chase_high_allowed(ind: dict[str, Any]) -> bool:
    """Return True only when conditions support cautious chasing.

    Very conservative: requires warming + low risk + strong signals.
    """
    limit_up = ind.get("limit_up_count", 0)
    limit_down = ind.get("limit_down_count", 0)
    promotion = ind.get("promotion_rate")
    max_height = ind.get("max_consecutive_limit_up_height", 0)
    strong_loss = ind.get("strong_stock_loss_effect", True)

    conditions = [
        limit_up >= 30,
        limit_down <= 5,
        promotion is not None and promotion >= 0.4,
        max_height is not None and max_height >= 4,
        strong_loss is False,
    ]
    return all(conditions)


# ── Score computation ────────────────────────────────────────────────────────


def _compute_score(ind: dict[str, Any], phase: str) -> int:
    """Compute a 0-100 sentiment score based on indicators and phase."""
    limit_up = ind.get("limit_up_count", 0)
    limit_down = ind.get("limit_down_count", 0)
    promotion = ind.get("promotion_rate")
    ylu_avg = ind.get("yesterday_limit_up_avg_pct_chg")
    ad_ratio = ind.get("advance_decline_ratio")

    score = 50  # neutral base

    # Limit up contribution (±20)
    if limit_up >= 50:
        score += 20
    elif limit_up >= 30:
        score += 15
    elif limit_up >= 15:
        score += 8
    elif limit_up >= 5:
        score += 3
    else:
        score -= 10

    # Limit down contribution (±20)
    if limit_down >= 30:
        score -= 20
    elif limit_down >= 15:
        score -= 12
    elif limit_down >= 8:
        score -= 5
    else:
        score += 5

    # Promotion rate (±15)
    if promotion is not None:
        if promotion >= 0.6:
            score += 15
        elif promotion >= 0.4:
            score += 8
        elif promotion >= 0.2:
            score += 3
        else:
            score -= 8

    # Yesterday limit-up avg (±15)
    if ylu_avg is not None:
        if ylu_avg >= 3.0:
            score += 15
        elif ylu_avg >= 1.0:
            score += 8
        elif ylu_avg >= 0:
            score += 3
        elif ylu_avg >= -1.0:
            score -= 5
        else:
            score -= 12

    # Advance/decline ratio (±10)
    if ad_ratio is not None:
        if ad_ratio >= 2.0:
            score += 10
        elif ad_ratio >= 1.2:
            score += 5
        elif ad_ratio >= 0.8:
            score += 0
        elif ad_ratio >= 0.5:
            score -= 5
        else:
            score -= 10

    # Clamp and adjust for phase
    if phase == "ice_point":
        score = min(score, 20)
    elif phase == "retreat":
        score = min(score, 15)
    elif phase == "cooling":
        score = max(20, min(score, 45))
    elif phase == "repair":
        score = max(30, min(score, 55))
    elif phase == "chaotic":
        score = max(20, min(score, 60))
    elif phase == "warming":
        score = max(55, min(score, 85))
    elif phase == "climax":
        score = max(70, min(score, 95))

    return max(0, min(100, score))


def _add_fallback_reasons(ind: dict[str, Any], reasons: list[str]) -> None:
    """Populate reasons when no clear phase is detected."""
    limit_up = ind.get("limit_up_count", 0)
    limit_down = ind.get("limit_down_count", 0)
    max_height = ind.get("max_consecutive_limit_up_height", 0)

    if limit_up > 0 or limit_down > 0:
        reasons.append(f"涨停 {limit_up} 家，跌停 {limit_down} 家")
    if max_height and max_height > 0:
        reasons.append(f"最高连板 {max_height} 板")

    promotion = ind.get("promotion_rate")
    if promotion is not None:
        reasons.append(f"晋级率 {promotion:.0%}")

    if not reasons:
        reasons.append("市场信号不明确，情绪周期无法判断")
    else:
        reasons.append("各项指标未形成明确的周期特征，判断为混沌状态")


# ── Action hint generation ───────────────────────────────────────────────────


def _action_hint_for(phase: str, chase: bool = False) -> str:
    """Return a short Chinese action hint for the given sentiment phase."""
    hints: dict[str, str] = {
        "ice_point": (
            "市场情绪处于冰点阶段，涨停稀少、恐慌较重。"
            "目前不是进攻时机，建议观察修复信号出现后再做决策。"
        ),
        "repair": (
            "市场情绪处于修复阶段，可以小仓试错，但还不适合重仓进攻和追高。"
            "关注涨停家数是否持续回升及连板高度的恢复。"
        ),
        "warming": (
            "市场情绪进入升温阶段，短线赚钱效应增强，"
            "可以主动进攻，但仍需控制接力风险和单票仓位。"
        ),
        "climax": (
            "市场情绪处于高潮阶段，赚钱效应强但追高风险明显上升。"
            "谨防次日分化和高位股补跌，不建议在此阶段追高接力。"
        ),
        "cooling": (
            "市场情绪进入降温阶段，涨停家数回落、高位股开始亏钱。"
            "建议暂停开新仓和追高，观察是否进入退潮或修复。"
        ),
        "retreat": (
            "市场情绪处于退潮阶段，强势股亏钱效应明显。"
            "建议停止接力和追高，优先保护已有利润，等待冰点后的修复信号。"
        ),
        "chaotic": (
            "市场情绪处于混沌阶段，信号矛盾、方向不明。"
            "建议谨慎观察，不急于做方向性判断，避免追高。"
        ),
    }
    if phase == "warming" and chase:
        return (
            "市场情绪升温明显，短线赚钱效应强，可以适度追高，"
            "但仍需控制仓位并设好止损。"
        )
    return hints.get(phase, "数据不足，暂不建议对情绪周期做明确判断。")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _verdict(
    sentiment_cycle: str,
    sentiment_score: int,
    risk_level: str,
    can_try_position: bool,
    can_attack: bool,
    relay_risk_level: str,
    chase_high_allowed: bool,
    action_hint: str,
    reasons: list[str],
) -> dict[str, Any]:
    """Build a clean judgment dict."""
    return {
        "sentiment_cycle": sentiment_cycle,
        "sentiment_score": sentiment_score,
        "risk_level": risk_level,
        "can_try_position": can_try_position,
        "can_attack": can_attack,
        "relay_risk_level": relay_risk_level,
        "chase_high_allowed": chase_high_allowed,
        "action_hint": action_hint,
        "reasons": reasons,
    }
