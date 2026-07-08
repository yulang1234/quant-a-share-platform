"""V1.5.1 market environment rules — pure judgment functions.

Converts a flat ``indicators`` dict (produced by
:mod:`src.market.market_indicators`) into a structured market-environment
verdict.

All thresholds are defined as module-level constants so they can be
adjusted without touching logic (and later wired into a config file for
V2.3 rule-version management).

Design principles
-----------------
* **Conservative** — when evidence is missing or ambiguous, default to
  defensive / unknown.  ``chase_high_allowed`` is almost always False.
* **Readable** — every rule is a named function that returns a partial
  result.  The top-level ``judge_market_environment`` merges them with
  a clear precedence (high_risk > defense > attack > neutral > unknown).
* **Explainable** — every rule appends human-readable ``reasons``.
* **No I/O** — pure functions, trivially testable.
"""
from __future__ import annotations

from typing import Any

# ── Configurable thresholds (candidates for V2.3 rule-version config) ─────────

# High-risk triggers
HIGH_RISK_COMPOSITE_PCT_CHG = -1.5        # avg pct_change below this → high risk
HIGH_RISK_AD_RATIO = 0.6                  # advance/decline below this → high risk
HIGH_RISK_LIMIT_DOWN_MIN = 30             # approx limit-down count >= this → alert
HIGH_RISK_TURNOVER_SPIKE = 1.5            # turnover > 1.5× 20d avg while index ↓

# Defense triggers
DEFENSE_PCT_ABOVE_MA20_MAX = 35.0         # < 35% stocks above MA20 → defense
DEFENSE_AD_RATIO_MAX = 0.85               # advance/decline below this → weakness
DEFENSE_TURNOVER_SHRINK = 0.75            # turnover < 0.75× 20d avg → weak
DEFENSE_COMPOSITE_PCT_CHG_NEG = -0.3      # avg pct_change below this → weak

# Attack triggers (must satisfy ALL to reach attack)
ATTACK_PCT_ABOVE_MA5_MIN = 55.0           # > 55% stocks above MA5
ATTACK_PCT_ABOVE_MA20_MIN = 50.0          # > 50% stocks above MA20
ATTACK_AD_RATIO_MIN = 1.3                 # advance/decline > 1.3
ATTACK_COMPOSITE_PCT_CHG_MIN = 0.3        # avg pct_change > 0.3%
ATTACK_TURNOVER_RATIO_MIN = 0.85          # turnover vs 20d avg
ATTACK_LIMIT_DOWN_MAX = 10                # fewer than this many approx limit-downs

# Extreme attack (for chase_high_allowed = True)
EXTREME_COMPOSITE_PCT_CHG = 1.0           # avg pct_change > 1.0%
EXTREME_AD_RATIO = 2.0                    # advance/decline > 2.0
EXTREME_PCT_ABOVE_MA5 = 65.0              # > 65% above MA5
EXTREME_LIMIT_DOWN_MAX = 5                # very few limit-downs

# Risk level mapping
RISK_HIGH_LIMIT_DOWN = 15                 # limit-down count triggers risk high


# ── Public API ───────────────────────────────────────────────────────────────


def judge_market_environment(indicators: dict[str, Any]) -> dict[str, Any]:
    """Return a complete market-environment judgment dict.

    Merges multiple rules with precedence:
    1. data insufficient → ``unknown``
    2. high-risk conditions → ``high_risk``
    3. defense conditions → ``defense``
    4. attack conditions → ``attack``
    5. fallback → ``neutral``

    Returns a dict with keys: market_state, risk_level, can_open_position,
    can_add_position, chase_high_allowed, action_hint, reasons.
    """
    if not indicators or not indicators.get("valid_stock_count"):
        return _verdict(
            market_state="unknown",
            risk_level="unknown",
            can_open=False,
            can_add=False,
            chase_high=False,
            action_hint="数据不足，暂不建议做明确判断。",
            reasons=["缺少当日个股数据，无法进行市场环境判断"],
        )

    reasons: list[str] = []

    # Note missing indicators (graceful degradation)
    missing = indicators.get("missing_indicator_names") or []
    if missing:
        reasons.append(
            f"部分指标因历史数据窗口不足未参与判断 "
            f"（{', '.join(missing[:5])}"
            + (f" 等共 {len(missing)} 项" if len(missing) > 5 else "")
            + "）"
        )

    # ---- 1. Check high-risk first ----
    high_risk_result = _check_high_risk(indicators)
    if high_risk_result:
        reasons.extend(high_risk_result["reasons"])
        risk_level = "extreme" if indicators.get("approximate_limit_down_count", 0) >= 50 else "high"
        return _verdict(
            market_state="high_risk",
            risk_level=risk_level,
            can_open=False,
            can_add=False,
            chase_high=False,
            action_hint=_action_hint_for("high_risk"),
            reasons=reasons,
        )

    # ---- 2. Check defense ----
    defense_result = _check_defense(indicators)
    if defense_result:
        reasons.extend(defense_result["reasons"])
        risk = "high" if indicators.get("approximate_limit_down_count", 0) >= RISK_HIGH_LIMIT_DOWN else "medium"
        return _verdict(
            market_state="defense",
            risk_level=risk,
            can_open=False,
            can_add=False,
            chase_high=False,
            action_hint=_action_hint_for("defense"),
            reasons=reasons,
        )

    # ---- 3. Check attack ----
    attack_result = _check_attack(indicators)
    if attack_result:
        reasons.extend(attack_result["reasons"])
        chase = _check_extreme_attack(indicators)
        risk = "low" if chase else "medium"
        return _verdict(
            market_state="attack",
            risk_level=risk,
            can_open=True,
            can_add=True,
            chase_high=chase,
            action_hint=_action_hint_for("attack", chase),
            reasons=reasons,
        )

    # ---- 4. Fallback: neutral ----
    _add_neutral_reasons(indicators, reasons)
    return _verdict(
        market_state="neutral",
        risk_level="medium",
        can_open=True,
        can_add=False,
        chase_high=False,
        action_hint=_action_hint_for("neutral"),
        reasons=reasons,
    )


# ── Rule functions (each returns None if the condition is NOT met) ────────────


def _check_high_risk(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return a partial result if high-risk conditions are detected."""
    reasons: list[str] = []
    hit_count = 0

    avg_pct = ind.get("avg_pct_chg")
    if avg_pct is not None and avg_pct <= HIGH_RISK_COMPOSITE_PCT_CHG:
        reasons.append(f"样本平均跌幅 {avg_pct:.2f}%，显著偏弱")
        hit_count += 1

    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None and ad_ratio < HIGH_RISK_AD_RATIO:
        reasons.append(f"涨跌家数比 {ad_ratio:.2f}，下跌家数远多于上涨家数")
        hit_count += 1

    limit_down = ind.get("approximate_limit_down_count", 0)
    if limit_down >= HIGH_RISK_LIMIT_DOWN_MIN:
        reasons.append(f"近似跌停家数 {limit_down}，跌停数量偏高")
        hit_count += 1

    # Turnover spike + price decline = potential distribution
    turnover_20 = ind.get("turnover_ratio_20d")
    if (
        avg_pct is not None and avg_pct < 0
        and turnover_20 is not None and turnover_20 > HIGH_RISK_TURNOVER_SPIKE
    ):
        reasons.append(f"成交额放大至 20 日均值的 {turnover_20:.1f} 倍但价格下跌，疑似放量杀跌")
        hit_count += 1

    if hit_count >= 2:
        return {"reasons": reasons}
    return None


def _check_defense(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return a partial result if defense conditions are detected."""
    reasons: list[str] = []
    hit_count = 0

    pct_above_ma20 = ind.get("pct_above_ma20")
    if pct_above_ma20 is not None and pct_above_ma20 < DEFENSE_PCT_ABOVE_MA20_MAX:
        reasons.append(f"仅 {pct_above_ma20:.0f}% 个股站上 20 日均线，市场广度偏弱")
        hit_count += 1

    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None and ad_ratio < DEFENSE_AD_RATIO_MAX:
        reasons.append(f"涨跌家数比 {ad_ratio:.2f}，下跌家数多于上涨家数")
        hit_count += 1

    turnover_20 = ind.get("turnover_ratio_20d")
    if turnover_20 is not None and turnover_20 < DEFENSE_TURNOVER_SHRINK:
        reasons.append(f"成交额萎缩至 20 日均值的 {turnover_20:.1%}，市场交投清淡")
        hit_count += 1

    avg_pct = ind.get("avg_pct_chg")
    if avg_pct is not None and avg_pct <= DEFENSE_COMPOSITE_PCT_CHG_NEG:
        reasons.append(f"样本平均涨跌 {avg_pct:.2f}%，短期偏弱")
        hit_count += 1

    # Composite close below MAs
    if ind.get("composite_close_above_ma20") is False:
        reasons.append("市场综合均价在 20 日均线下方")
        hit_count += 1

    if hit_count >= 2:
        return {"reasons": reasons}
    return None


def _check_attack(ind: dict[str, Any]) -> dict[str, Any] | None:
    """Return a partial result if attack conditions are met."""
    reasons: list[str] = []
    required = 0
    met = 0

    pct_above_ma5 = ind.get("pct_above_ma5")
    if pct_above_ma5 is not None:
        required += 1
        if pct_above_ma5 >= ATTACK_PCT_ABOVE_MA5_MIN:
            reasons.append(f"{pct_above_ma5:.0f}% 个股站上 5 日均线，短期强势")
            met += 1

    pct_above_ma20 = ind.get("pct_above_ma20")
    if pct_above_ma20 is not None:
        required += 1
        if pct_above_ma20 >= ATTACK_PCT_ABOVE_MA20_MIN:
            reasons.append(f"{pct_above_ma20:.0f}% 个股站上 20 日均线，中期趋势向好")
            met += 1

    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None:
        required += 1
        if ad_ratio >= ATTACK_AD_RATIO_MIN:
            reasons.append(f"涨跌家数比 {ad_ratio:.2f}，上涨家数明显多于下跌家数")
            met += 1

    avg_pct = ind.get("avg_pct_chg")
    if avg_pct is not None:
        required += 1
        if avg_pct >= ATTACK_COMPOSITE_PCT_CHG_MIN:
            reasons.append(f"样本平均涨幅 {avg_pct:.2f}%，整体偏强")
            met += 1

    turnover_20 = ind.get("turnover_ratio_20d")
    if turnover_20 is not None:
        if turnover_20 >= ATTACK_TURNOVER_RATIO_MIN:
            reasons.append(f"成交额维持近期均量以上（{turnover_20:.1%}），量能配合")
        else:
            reasons.append(f"成交额相对 20 日均值偏低（{turnover_20:.1%}），量能不足")

    limit_down = ind.get("approximate_limit_down_count", 0)
    if limit_down <= ATTACK_LIMIT_DOWN_MAX:
        reasons.append(f"近似跌停仅 {limit_down} 家，恐慌情绪低")
    else:
        reasons.append(f"近似跌停 {limit_down} 家，局部风险存在")

    # Require at least half of checked conditions to pass (+ ad_ratio must pass)
    if required > 0 and met >= required * 0.5 and ad_ratio is not None and ad_ratio >= 1.0:
        return {"reasons": reasons}
    return None


def _check_extreme_attack(ind: dict[str, Any]) -> bool:
    """Return True only when market is extremely strong (chase_high_allowed)."""
    avg_pct = ind.get("avg_pct_chg")
    ad_ratio = ind.get("advance_decline_ratio")
    pct_ma5 = ind.get("pct_above_ma5")
    limit_down = ind.get("approximate_limit_down_count", 999)

    conditions = [
        avg_pct is not None and avg_pct >= EXTREME_COMPOSITE_PCT_CHG,
        ad_ratio is not None and ad_ratio >= EXTREME_AD_RATIO,
        pct_ma5 is not None and pct_ma5 >= EXTREME_PCT_ABOVE_MA5,
        limit_down <= EXTREME_LIMIT_DOWN_MAX,
    ]
    return all(conditions)


def _add_neutral_reasons(ind: dict[str, Any], reasons: list[str]) -> None:
    """Populate reasons for neutral market."""
    avg_pct = ind.get("avg_pct_chg")
    if avg_pct is not None:
        direction = "上涨" if avg_pct > 0 else "下跌" if avg_pct < 0 else "持平"
        reasons.append(f"样本平均{direction} {abs(avg_pct):.2f}%")

    ad_ratio = ind.get("advance_decline_ratio")
    if ad_ratio is not None:
        if ad_ratio > 1.05:
            reasons.append("上涨家数略多于下跌家数")
        elif ad_ratio < 0.95:
            reasons.append("下跌家数略多于上涨家数")
        else:
            reasons.append("涨跌家数接近")

    turnover_20 = ind.get("turnover_ratio_20d")
    if turnover_20 is not None:
        if turnover_20 > 1.1:
            reasons.append("成交额温和放大")
        elif turnover_20 < 0.9:
            reasons.append("成交额略有萎缩")
        else:
            reasons.append("成交额处于正常水平")

    limit_up = ind.get("approximate_limit_up_count", 0)
    limit_down = ind.get("approximate_limit_down_count", 0)
    if limit_up > 0 or limit_down > 0:
        reasons.append(f"近似涨停 {limit_up} 家，近似跌停 {limit_down} 家")

    if not reasons:
        reasons.append("市场信号不明确，保持中性判断")


# ── Action hint generation ───────────────────────────────────────────────────


def _action_hint_for(state: str, chase: bool = False) -> str:
    """Return a short Chinese action hint for the given market state."""
    hints: dict[str, str] = {
        "high_risk": (
            "市场风险较高，建议控制仓位，暂停开仓和加仓，不要追高。"
            "优先保护已有利润，等待风险释放后再评估。"
        ),
        "defense": (
            "市场环境偏弱，不建议开新仓或加仓。"
            "可以观察抗跌个股，但不要急于进场。追高坚决禁止。"
        ),
        "neutral": (
            "市场环境中性，可以观察主线方向，小仓试错可以，"
            "但不适合重仓进攻和追高。等待更明确的信号。"
        ),
        "attack": (
            "市场环境偏强，可以小仓试错，开仓和加仓均可考虑，"
            "但不建议盲目追高。关注主线板块的持续性。"
        ),
    }
    if state == "attack" and chase:
        return (
            "市场环境极强，可以适度进攻，开仓加仓均可，"
            "但仍需控制单票仓位，设好止损。"
        )
    return hints.get(state, "数据不足，暂不建议做明确判断。")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _verdict(
    market_state: str,
    risk_level: str,
    can_open: bool,
    can_add: bool,
    chase_high: bool,
    action_hint: str,
    reasons: list[str],
) -> dict[str, Any]:
    """Build a clean judgment dict."""
    return {
        "market_state": market_state,
        "risk_level": risk_level,
        "can_open_position": can_open,
        "can_add_position": can_add,
        "chase_high_allowed": chase_high,
        "action_hint": action_hint,
        "reasons": reasons,
    }
