"""V1.6.3 condition engine.

The engine emits condition states and permission summaries only. It has no
external side effects and does not trigger data repair.
"""
from __future__ import annotations

from src.conditions.condition_types import ConditionItem, ConditionSet


def build_condition_set(
    market: dict | None,
    sentiment: dict | None,
    sector: dict | None,
    leader: dict | None,
    opportunity: dict | None,
) -> ConditionSet:
    cs = ConditionSet()
    cs.opportunity_score = float((opportunity or {}).get("opportunity_score", 0) or 0)
    cs.exit = _exit_conditions()
    cs.invalidation = _invalidation_conditions()
    cs.risk = _risk_conditions(leader, opportunity)
    cs.entry = _entry_conditions(market, sentiment, sector, leader, opportunity, cs.exit, cs.invalidation)
    cs.reduce = _reduce_conditions()
    cs.cancel_watch = _cancel_conditions(sector, leader, opportunity)
    cs.observation = _observation_conditions(market, sentiment, sector, opportunity)

    if not _any_blocked(cs.entry) and cs.risk:
        cs.add_position = _add_conditions(sector, leader, opportunity, cs.risk)
    else:
        cs.add_position = [
            ConditionItem(
                "add_position",
                "entry and risk guard",
                "blocked",
                "high",
                "entry or risk guard is incomplete",
                True,
            )
        ]

    cs.permission, cs.permission_reason = _permission(cs, opportunity)
    cs.risk_warnings = [r.reason for r in cs.risk if r.severity in ("high", "critical")]
    cs.risk_warnings.append("Research aid only. No automatic execution. Not investment advice.")
    return cs


def _entry_conditions(m, s, sec, ldr, opp, exits, invalidations) -> list[ConditionItem]:
    items: list[ConditionItem] = []
    market_state = (m or {}).get("market_state", "unknown")
    if market_state in ("defense", "high_risk", "unknown"):
        items.append(_blocked("entry", "market environment", f"market_state={market_state}"))
    else:
        items.append(_ok("entry", "market environment", f"market_state={market_state}"))

    sentiment_cycle = (s or {}).get("sentiment_cycle", "unknown")
    if sentiment_cycle in ("retreat", "ice_point", "cooling", "unknown"):
        items.append(_blocked("entry", "sentiment cycle", f"sentiment_cycle={sentiment_cycle}"))
    else:
        items.append(_ok("entry", "sentiment cycle", f"sentiment_cycle={sentiment_cycle}"))

    mainline_status = (sec or {}).get("mainline_status", "unknown")
    if mainline_status in ("one_day_theme", "high_risk_sector", "cooling_sector", "unknown"):
        items.append(_blocked("entry", "sector mainline", f"mainline_status={mainline_status}"))
    else:
        items.append(_ok("entry", "sector mainline", f"mainline_status={mainline_status}"))

    leader_type = (ldr or {}).get("leader_type", "unknown")
    if leader_type in ("pseudo_leader", "high_risk_chasing", "unknown"):
        items.append(_blocked("entry", "leader quality", f"leader_type={leader_type}"))
    else:
        items.append(_ok("entry", "leader quality", f"leader_type={leader_type}"))

    score = float((opp or {}).get("opportunity_score", 0) or 0)
    if score < 40:
        items.append(_blocked("entry", "opportunity score", f"opportunity_score={score:.0f}", "medium"))
    else:
        status = "satisfied" if score >= 60 else "partial"
        items.append(ConditionItem("entry", "opportunity score", status, "low", f"opportunity_score={score:.0f}"))

    if not exits:
        items.append(_blocked("entry", "exit conditions complete", "missing exit conditions", "critical"))
    if not invalidations:
        items.append(_blocked("entry", "invalidation conditions complete", "missing invalidation conditions", "critical"))
    return items


def _exit_conditions() -> list[ConditionItem]:
    return [
        ConditionItem("exit", "market turns defensive or high risk", "not_satisfied", "high", "exit guard"),
        ConditionItem("exit", "sentiment retreats", "not_satisfied", "high", "exit guard"),
        ConditionItem("exit", "sector mainline fails", "not_satisfied", "high", "exit guard"),
        ConditionItem("exit", "leader status deteriorates", "not_satisfied", "high", "exit guard"),
        ConditionItem("exit", "opportunity score below 20", "not_satisfied", "critical", "exit guard"),
    ]


def _invalidation_conditions() -> list[ConditionItem]:
    return [
        ConditionItem("invalidation", "mainline probability below 30", "not_satisfied", "high", "invalid"),
        ConditionItem("invalidation", "leader score below 40", "not_satisfied", "high", "invalid"),
        ConditionItem("invalidation", "opportunity score below 25", "not_satisfied", "critical", "invalid"),
        ConditionItem("invalidation", "continuous data missing", "not_satisfied", "medium", "invalid"),
    ]


def _risk_conditions(leader: dict | None, opportunity: dict | None) -> list[ConditionItem]:
    items: list[ConditionItem] = []
    leader_type = (leader or {}).get("leader_type", "unknown")
    if leader_type == "high_risk_chasing":
        items.append(_blocked("risk", "chasing risk", "high-risk chasing", "critical"))
    elif leader_type == "pseudo_leader":
        items.append(_blocked("risk", "pseudo leader risk", "pseudo leader", "high"))
    if (opportunity or {}).get("risk_discount", 1) < 0.6:
        items.append(_blocked("risk", "risk discount", "risk discount below 0.6", "high"))
    items.append(ConditionItem("risk", "data quality risk", "not_satisfied", "medium", "monitor local data quality"))
    return items


def _add_conditions(sec, ldr, opp, risks) -> list[ConditionItem]:
    if not risks:
        return [_blocked("add_position", "risk conditions complete", "missing risk conditions", "critical")]
    if _any_blocked(risks):
        return [_blocked("add_position", "risk guard", "blocked by risk condition", "critical")]
    score = float((opp or {}).get("opportunity_score", 0) or 0)
    if score >= 65:
        return [ConditionItem("add_position", "opportunity remains high", "satisfied", "low", f"score={score:.0f}")]
    return [ConditionItem("add_position", "opportunity remains high", "not_satisfied", "medium", f"score={score:.0f}")]


def _reduce_conditions() -> list[ConditionItem]:
    return [
        ConditionItem("reduce", "market weakens", "not_satisfied", "medium", "monitor"),
        ConditionItem("reduce", "sentiment cools", "not_satisfied", "medium", "monitor"),
        ConditionItem("reduce", "sector ranking declines", "not_satisfied", "medium", "monitor"),
    ]


def _cancel_conditions(sec, leader, opp) -> list[ConditionItem]:
    score = float((opp or {}).get("opportunity_score", 0) or 0)
    leader_type = (leader or {}).get("leader_type", "unknown")
    if leader_type == "pseudo_leader":
        return [ConditionItem("cancel_watch", "pseudo leader", "satisfied", "high", "cancel watch condition")]
    if score < 20:
        return [ConditionItem("cancel_watch", "opportunity score very low", "satisfied", "medium", f"score={score:.0f}")]
    return [ConditionItem("cancel_watch", "opportunity score very low", "not_satisfied", "low", f"score={score:.0f}")]


def _observation_conditions(m, s, sec, opp) -> list[ConditionItem]:
    return [
        ConditionItem("observation", "wait for market risk to decline", "not_satisfied", "low", "monitor"),
        ConditionItem("observation", "wait for sentiment repair", "not_satisfied", "low", "monitor"),
        ConditionItem("observation", "wait for sector confirmation", "not_satisfied", "low", "monitor"),
    ]


def _permission(cs: ConditionSet, opp: dict | None) -> tuple[str, str]:
    if not cs.exit or not cs.invalidation:
        return "unknown", "exit or invalidation conditions are incomplete"
    if _any_blocked(cs.entry):
        return "unknown", "entry conditions are blocked"
    if _any_blocked(cs.risk):
        return "forbid_chase", "risk condition blocks chasing"
    score = float((opp or {}).get("opportunity_score", 0) or 0)
    if score >= 70:
        return "small_trial", "conditions are satisfied with explicit invalidation and risk guards"
    if score >= 55:
        return "wait_entry", "conditions are mostly satisfied; wait for a better setup"
    if score >= 30:
        return "allow_observe", "only observation is allowed"
    return "cancel", "opportunity score is too low"


def _blocked(ctype: str, name: str, reason: str, severity: str = "high") -> ConditionItem:
    return ConditionItem(ctype, name, "blocked", severity, reason, True)


def _ok(ctype: str, name: str, reason: str) -> ConditionItem:
    return ConditionItem(ctype, name, "satisfied", "low", reason)


def _any_blocked(items: list[ConditionItem]) -> bool:
    return any(item.blocking for item in items)
