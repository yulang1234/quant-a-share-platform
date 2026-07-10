"""V1.7.2 position diagnosis rules — scoring thresholds and action logic.

All magic numbers live here, not in service or UI.
"""

from __future__ import annotations

from typing import Any

from src.portfolio.position_diagnosis_types import (
    DiagnosisComponent,
    DiagnosisStatus,
    PositionDiagnosisResult,
    PositionSizeStatus,
    SuggestedAction,
    ThesisStatus,
    safe_float,
)

RULE_VERSION = "v1.7.2"

# ── Component weights (must sum to 1.0) ─────────────────────────────────────

COMPONENT_WEIGHTS: dict[str, float] = {
    "market": 0.10,
    "sentiment": 0.10,
    "sector": 0.20,
    "leader": 0.15,
    "trend": 0.20,
    "condition": 0.15,
    "thesis": 0.10,
}

POSITION_SIZE_THRESHOLDS: dict[str, float] = {
    "elevated": 20.0,
    "high": 30.0,
}


# ── Market support ───────────────────────────────────────────────────────────


def evaluate_market_support(market: dict[str, Any] | None) -> DiagnosisComponent:
    """Score the market environment's support for an existing position."""
    comp = DiagnosisComponent(name="market", weight=COMPONENT_WEIGHTS["market"])
    if not market:
        comp.issues.append("市场环境数据缺失")
        return comp

    state = market.get("market_state", "unknown")
    risk_level = market.get("risk_level", "")

    score_map: dict[str, tuple[float, float]] = {
        "attack": (80, 100),
        "neutral": (55, 75),
        "defense": (25, 50),
        "high_risk": (0, 30),
    }

    if state in score_map:
        lo, hi = score_map[state]
        # center of range
        comp.score = (lo + hi) / 2
        comp.status = "satisfied" if comp.score >= 60 else "warning"
    else:
        comp.score = 0
        comp.status = "unknown"
        comp.issues.append(f"未知市场状态: {state}")

    if risk_level in ("high", "extreme"):
        comp.score = min(comp.score, 25)
        comp.status = "warning"
        comp.reason = f"市场风险等级: {risk_level}"

    if state == "high_risk":
        comp.reason = "市场处于高风险状态，对持仓支持度低"

    comp.evidence.append(f"market_state={state}")
    return comp


# ── Sentiment support ────────────────────────────────────────────────────────


def evaluate_sentiment_support(sentiment: dict[str, Any] | None) -> DiagnosisComponent:
    """Score the sentiment cycle's support for an existing position."""
    comp = DiagnosisComponent(name="sentiment", weight=COMPONENT_WEIGHTS["sentiment"])
    if not sentiment:
        comp.issues.append("情绪周期数据缺失")
        return comp

    cycle = sentiment.get("sentiment_cycle", "unknown")

    score_map: dict[str, tuple[float, float]] = {
        "repair": (65, 80),
        "warming": (70, 90),
        "rising": (70, 90),
        "climax": (45, 70),
        "cooling": (30, 55),
        "retreat": (10, 35),
        "ice_point": (15, 40),
        "chaotic": (25, 50),
    }

    if cycle in score_map:
        lo, hi = score_map[cycle]
        comp.score = (lo + hi) / 2
        if cycle in ("climax",):
            comp.reason = "情绪处于高位，注意高位风险"
        comp.status = "satisfied" if comp.score >= 55 else "warning"
    else:
        comp.status = "unknown"
        comp.issues.append(f"未知情绪周期: {cycle}")

    comp.evidence.append(f"sentiment_cycle={cycle}")
    return comp


# ── Sector support ───────────────────────────────────────────────────────────


def evaluate_sector_support(
    sector_mainline: dict[str, Any] | None,
    entry_snapshot: dict[str, Any] | None = None,
) -> DiagnosisComponent:
    """Score sector support, including changes from entry snapshot."""
    comp = DiagnosisComponent(name="sector", weight=COMPONENT_WEIGHTS["sector"])
    if not sector_mainline:
        comp.issues.append("板块主线数据缺失")
        return comp

    status = sector_mainline.get("mainline_status", "unknown")
    prob = safe_float(sector_mainline.get("mainline_probability", 0))

    score_map: dict[str, tuple[float, float]] = {
        "confirmed_mainline": (75, 95),
        "potential_mainline": (55, 75),
        "confirmed": (75, 95),
        "potential": (55, 75),
        "one_day_theme": (15, 40),
        "cooling_sector": (20, 50),
        "cooling": (20, 50),
        "high_risk_sector": (0, 30),
    }

    if status in score_map:
        lo, hi = score_map[status]
        comp.score = (lo + hi) / 2
    else:
        comp.score = 0
        comp.status = "unknown"
        comp.issues.append(f"未知板块主线状态: {status}")

    # Downgrade if sector weakened from entry snapshot
    if entry_snapshot:
        entry_ml = entry_snapshot.get("sector_mainline") or {}
        entry_status = entry_ml.get("mainline_status", "")
        if entry_status in ("confirmed_mainline", "confirmed"):
            if status in ("potential_mainline", "potential"):
                comp.score = min(comp.score, 55)
                comp.reason = "板块主线从确认降为潜在"
            elif status in ("cooling_sector", "cooling", "one_day_theme", "high_risk_sector"):
                comp.score = min(comp.score, 35)
                comp.reason = "板块主线状态明显恶化"
                comp.issues.append("板块主线弱化风险")

    comp.status = "satisfied" if comp.score >= 60 else "warning" if comp.score >= 30 else "danger"
    comp.evidence.append(f"mainline_status={status}")
    return comp


# ── Leader support ───────────────────────────────────────────────────────────


def evaluate_leader_support(
    current_leader: dict[str, Any] | None,
    entry_snapshot: dict[str, Any] | None = None,
) -> DiagnosisComponent:
    """Score leader position, comparing against entry snapshot."""
    comp = DiagnosisComponent(name="leader", weight=COMPONENT_WEIGHTS["leader"])
    if not current_leader:
        comp.issues.append("无当前龙头数据")
        if entry_snapshot and entry_snapshot.get("sector_leaders"):
            comp.issues.append("建仓时有龙头快照但当前无法评估，需人工复核")
        return comp

    leader_type = current_leader.get("leader_type", "unknown")
    leader_score = safe_float(current_leader.get("leader_score", 0))

    type_score_map: dict[str, tuple[float, float]] = {
        "leader_1": (80, 95),
        "leader_2": (55, 75),
        "make_up_candidate": (45, 70),
        "normal": (25, 50),
        "pseudo_leader": (0, 30),
        "high_risk_chasing": (0, 25),
    }

    if leader_type in type_score_map:
        lo, hi = type_score_map[leader_type]
        comp.score = (lo + hi) / 2
    else:
        comp.status = "unknown"
        comp.issues.append(f"未知龙头类型: {leader_type}")

    # Compare with entry snapshot
    if entry_snapshot:
        entry_leaders = entry_snapshot.get("sector_leaders") or {}
        entry_l1 = entry_leaders.get("leader_1") or {}
        entry_lt = entry_l1.get("leader_type", "")

        if entry_lt == "leader_1" and leader_type != "leader_1":
            comp.score = min(comp.score, 50)
            if leader_type == "pseudo_leader":
                comp.score = min(comp.score, 25)
                comp.issues.append("龙头地位严重弱化: leader_1 → pseudo_leader")
            else:
                comp.reason = f"龙头地位减弱: {entry_lt} → {leader_type}"

    comp.status = "satisfied" if comp.score >= 60 else "warning" if comp.score >= 30 else "danger"
    comp.evidence.append(f"leader_type={leader_type}, leader_score={leader_score:.0f}")
    return comp


# ── Trend health ─────────────────────────────────────────────────────────────


def evaluate_trend_health(price_context: dict[str, Any] | None) -> DiagnosisComponent:
    """Score trend health from price and moving average context."""
    comp = DiagnosisComponent(name="trend", weight=COMPONENT_WEIGHTS["trend"])
    if not price_context:
        comp.issues.append("趋势数据缺失")
        return comp

    close = safe_float(price_context.get("close"))
    ma5 = safe_float(price_context.get("ma5"))
    ma10 = safe_float(price_context.get("ma10"))
    ma20 = safe_float(price_context.get("ma20"))
    pct_5d = safe_float(price_context.get("pct_chg_5d"))
    pct_20d = safe_float(price_context.get("pct_chg_20d"))
    drawdown = safe_float(price_context.get("drawdown_20d"))

    # Start neutral and adjust
    comp.score = 70.0

    if close <= 0:
        comp.issues.append("无有效收盘价")
        comp.score = 0
        return comp

    # MA alignment
    above_ma20 = ma20 > 0 and close > ma20
    above_ma10 = ma10 > 0 and close > ma10
    above_ma5 = ma5 > 0 and close > ma5
    ma_aligned = above_ma5 and above_ma10 and above_ma20 and ma5 > ma10 > ma20 if all(v > 0 for v in (ma5, ma10, ma20)) else False

    if ma_aligned:
        comp.score = 85
        comp.reason = "多头排列，趋势健康"
    elif above_ma20 and above_ma10:
        comp.score = 70
        comp.reason = "在MA10/MA20上方，结构正常"
    elif above_ma20:
        comp.score = 55
        comp.reason = "跌破MA10但仍在MA20上方"
    elif ma20 > 0 and close < ma20:
        comp.score = 25
        comp.reason = "跌破MA20，趋势明显破坏"
        comp.issues.append("跌破MA20，趋势结构严重破坏")

    if drawdown > 15:
        comp.score = min(comp.score, 40)
        comp.issues.append(f"20日回撤较大: {drawdown:.1f}%")

    if pct_20d < -10:
        comp.score = min(comp.score, 35)
        comp.issues.append(f"近20日跌幅较大: {pct_20d:.1f}%")

    if pct_5d < -5 and not above_ma10:
        comp.score = min(comp.score, 45)

    comp.status = "satisfied" if comp.score >= 60 else "warning" if comp.score >= 30 else "danger"
    comp.evidence.append(f"close={close:.2f}, above_ma20={above_ma20}, drawdown_20d={drawdown:.1f}%")
    return comp


# ── Condition engine support ─────────────────────────────────────────────────


def evaluate_condition_support(condition_set: dict[str, Any] | None) -> DiagnosisComponent:
    """Score condition engine support for holding."""
    comp = DiagnosisComponent(name="condition", weight=COMPONENT_WEIGHTS["condition"])
    if not condition_set:
        comp.issues.append("条件引擎数据缺失")
        return comp

    permission = condition_set.get("permission", "unknown")

    perm_score: dict[str, float] = {
        "small_trial": 80,
        "wait_entry": 60,
        "allow_observe": 50,
        "forbid_chase": 35,
    }

    if permission in perm_score:
        comp.score = perm_score[permission]
    else:
        comp.score = 0
        comp.status = "unknown"

    # Check reduce/exit conditions
    reduce_conds = condition_set.get("reduce_conditions") or []
    exit_conds = condition_set.get("exit_conditions") or []

    if reduce_conds:
        satisfied_reduce = [c for c in reduce_conds if c.get("status") == "satisfied"]
        if satisfied_reduce:
            comp.score = min(comp.score, 30)
            comp.issues.append(f"{len(satisfied_reduce)} 条减仓条件已满足")

    if exit_conds:
        satisfied_exit = [c for c in exit_conds if c.get("status") == "satisfied"]
        if satisfied_exit:
            comp.score = min(comp.score, 15)
            comp.issues.append(f"{len(satisfied_exit)} 条清仓条件已满足")

    comp.status = "satisfied" if comp.score >= 60 else "warning" if comp.score >= 30 else "danger"
    comp.evidence.append(f"permission={permission}")
    return comp


# ── Thesis evaluation ────────────────────────────────────────────────────────


def evaluate_thesis_status(
    position: dict[str, Any] | None,
    entry_snapshot: dict[str, Any] | None,
    current_context: dict[str, Any] | None = None,
) -> DiagnosisComponent:
    """Evaluate whether the original investment thesis remains valid.

    Does NOT attempt NLP on buy_reason text.
    Relies entirely on structured entry_snapshot_json comparison.
    """
    comp = DiagnosisComponent(name="thesis", weight=COMPONENT_WEIGHTS["thesis"])

    if not position:
        comp.issues.append("持仓数据缺失")
        return comp

    if not entry_snapshot or not isinstance(entry_snapshot, dict):
        comp.score = 50
        comp.status = "manual_review_required"
        comp.reason = "无结构化建仓快照，系统无法自动验证原始逻辑，需要人工确认"
        comp.issues.append("manual_review_required: 无建仓快照或快照损坏")
        return comp

    # Compare key dimensions
    matches = 0
    total = 0
    changes: list[str] = []

    # Market state
    entry_market = entry_snapshot.get("market_environment") or {}
    curr_market = (current_context or {}).get("market") or {}
    total += 1
    if entry_market.get("market_state") == curr_market.get("market_state"):
        matches += 1
    elif entry_market.get("market_state") in ("attack", "neutral") and curr_market.get("market_state") in ("defense", "high_risk"):
        changes.append("市场环境恶化")

    # Sentiment
    entry_sent = entry_snapshot.get("sentiment_cycle") or {}
    curr_sent = (current_context or {}).get("sentiment") or {}
    total += 1
    entry_sc = entry_sent.get("sentiment_cycle", "")
    curr_sc = curr_sent.get("sentiment_cycle", "")
    if entry_sc == curr_sc:
        matches += 1
    elif curr_sc in ("retreat", "ice_point", "cooling"):
        changes.append("情绪周期明显恶化")

    # Sector mainline
    entry_ml = entry_snapshot.get("sector_mainline") or {}
    curr_ml = (current_context or {}).get("sector_mainline") or {}
    total += 1
    entry_mls = entry_ml.get("mainline_status", "")
    curr_mls = curr_ml.get("mainline_status", "")
    if entry_mls == curr_mls:
        matches += 1
    elif entry_mls in ("confirmed_mainline", "confirmed") and curr_mls in ("one_day_theme", "cooling", "high_risk_sector"):
        changes.append("板块主线明显恶化")

    # Leader
    entry_leaders = entry_snapshot.get("sector_leaders") or {}
    entry_l1 = entry_leaders.get("leader_1") or {}
    curr_leader = (current_context or {}).get("leader") or {}
    total += 1
    if entry_l1.get("leader_type") == curr_leader.get("leader_type"):
        matches += 1
    elif curr_leader.get("leader_type") == "pseudo_leader":
        changes.append("龙头变为伪龙头")

    # Compute thesis_score
    if total > 0:
        ratio = matches / total
        comp.score = round(ratio * 100)
    else:
        comp.score = 50

    # Classification
    if changes:
        if any(m in "".join(changes) for m in ("恶化", "伪龙头", "失效")):
            if len(changes) >= 2:
                comp.status = "invalid"
                comp.issues.extend(changes)
                comp.score = min(comp.score, 30)
            else:
                comp.status = "weakening"
                comp.reason = "; ".join(changes)
                comp.score = min(comp.score, 55)
        else:
            comp.status = "weakening"
            comp.score = min(comp.score, 60)
    elif matches == total:
        comp.status = "valid"
        comp.reason = "原始逻辑与当前状态一致"
    else:
        comp.status = "weakening"
        comp.reason = "部分维度发生变化"

    comp.evidence.append(f"dimensions_matched={matches}/{total}")
    return comp


# ── Position size ────────────────────────────────────────────────────────────


def evaluate_position_size(position_pct: float | None) -> tuple[str, str]:
    """Evaluate position size status.

    Returns:
        (PositionSizeStatus, reason).
    """
    if position_pct is None:
        return ("unknown", "仓位百分比未填写")
    try:
        pct = float(position_pct)
    except (TypeError, ValueError):
        return ("unknown", "仓位百分比无效")

    if pct < 0:
        return ("unknown", "仓位百分比异常")
    if pct < POSITION_SIZE_THRESHOLDS["elevated"]:
        return ("normal", "仓位正常")
    if pct < POSITION_SIZE_THRESHOLDS["high"]:
        return ("elevated", f"仓位偏高 {pct:.1f}%")
    return ("high", f"仓位过重 {pct:.1f}%")


# ── Composite health score ───────────────────────────────────────────────────


def compute_position_health_score(components: list[DiagnosisComponent]) -> tuple[float, float]:
    """Compute weighted health_score and data_coverage_ratio.

    Returns:
        (health_score, data_coverage_ratio).
    """
    total_weight = 0.0
    weighted_sum = 0.0
    components_with_data = 0
    total_components = len(components)

    for comp in components:
        if comp.issues and any("缺失" in i for i in comp.issues):
            continue  # skip completely missing components
        weighted_sum += comp.score * comp.weight
        total_weight += comp.weight
        if comp.score > 0 or (comp.issues and len(comp.issues) > 0):
            components_with_data += 1

    coverage = components_with_data / max(total_components, 1)

    if total_weight > 0:
        raw = weighted_sum / total_weight
    else:
        raw = 0.0

    # Confidence adjustment
    if coverage < 0.4:
        raw = raw * 0.5  # severe penalty
    elif coverage < 0.6:
        raw = raw * 0.8

    return (round(min(max(raw, 0), 100), 1), round(coverage, 2))


def classify_health(health_score: float, coverage: float) -> str:
    """Classify health score into DiagnosisStatus."""
    if coverage < 0.4:
        return "unknown"
    if health_score >= 75:
        return "healthy"
    if health_score >= 60:
        return "watch"
    if health_score >= 40:
        return "cautious"
    return "dangerous"


# ── Action classification ────────────────────────────────────────────────────


def classify_position_action(result: PositionDiagnosisResult) -> str:
    """Determine suggested_action from diagnosis result.

    Priority order: exit → reduce → forbid_add → light_hold → continue_hold → allow_add.
    """
    risk_issues = " ".join(result.issue_summary).lower()
    condition_score = result.condition_support_score

    # Priority 1: hard risk → exit
    exit_triggers = [
        "exit" in risk_issues or result.condition_support_score < 15,
        result.thesis_status == "invalid",
        (result.sector_component and result.sector_component.score < 25
         and "恶化" in (result.sector_component.reason or "")),
        result.leader_component is not None and result.leader_component.score < 25,
        result.trend_component is not None and result.trend_component.score < 20,
    ]
    # Convert None to False for sum
    exit_triggers_bool = [bool(t) for t in exit_triggers]
    if sum(exit_triggers_bool) >= 2 or result.condition_support_score < 10:
        return "exit_conditionally"

    # Priority 2: clear weakening → reduce
    reduce_triggers = [
        condition_score < 30,
        result.thesis_status == "weakening",
        result.health_score < 45,
    ]
    if sum(reduce_triggers) >= 2:
        return "reduce_conditionally"

    # Priority 3: risk blocking → forbid_add
    forbid_triggers = [
        condition_score < 40,
        result.data_coverage_ratio < 0.6,
        result.position_size_status == "high",
        (result.sentiment_component is not None and result.sentiment_component.score < 35),
    ]
    if any(forbid_triggers):
        return "forbid_add"

    # Priority 4: healthy but cautious → light_hold
    if result.health_score < 65 or result.thesis_status in ("weakening",):
        return "light_hold"

    # Priority 5: healthy → continue_hold
    if result.thesis_status == "valid" and result.health_score >= 65:
        return "continue_hold"

    # Priority 6: strict allow_add
    allow_add_checks = [
        result.diagnosis_status == "healthy",
        result.thesis_status == "valid",
        result.market_support_score >= 65,
        result.sentiment_support_score >= 60,
        result.sector_support_score >= 70,
        result.leader_support_score >= 65,
        result.trend_health_score >= 70,
        result.condition_support_score >= 65,
        result.position_size_status != "high",
        result.data_coverage_ratio >= 0.8,
    ]
    if all(allow_add_checks):
        return "allow_add_conditionally"

    if result.data_coverage_ratio < 0.4:
        return "unknown"

    return "light_hold"
