"""V1.5.1 daily decision card — integrates market/sentiment/sector/rules.

Pure, read-only orchestrator. No writes, no network, no auto-backfill.
Each sub-builder is wrapped in try/except so a failure in one module
never blanks out the whole card; the affected section is filled with
``unknown`` / ``None`` / ``[]`` and an issue is recorded.

V1.5.1 adds ``market_environment`` from the real market-environment
judgment module, which computes actual indicators from ``stock_daily_raw``
instead of always returning ``unknown``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from src.data_quality.quality_dashboard import HEALTH_UNKNOWN
from src.market.market_state import build_market_snapshot, MARKET_UNKNOWN
from src.sentiment.sentiment_cycle import (
    build_sentiment_snapshot, SENTIMENT_UNKNOWN,
)
from src.sector.sector_snapshot import build_sector_snapshot
from src.rules.basic_decision_rules import (
    decide_overall_bias, build_risk_warnings, build_suggested_actions,
    build_observation_conditions, build_invalidation_conditions,
    OVERALL_UNKNOWN, OVERALL_DEFENSIVE,
)


@dataclass
class DailyDecisionCard:
    """The structured 'today decision card' (V1.5.1)."""

    trade_date: str | None
    overall_bias: str
    market_state: str
    sentiment_cycle: str
    risk_level: str
    strong_sectors: list[dict[str, Any]] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    observation_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    data_quality_status: str = HEALTH_UNKNOWN
    generated_at: str = ""
    issue_summary: list[str] = field(default_factory=list)
    # Sub-snapshots (kept for the UI / Markdown renderer).
    market_snapshot: dict[str, Any] = field(default_factory=dict)
    sentiment_snapshot: dict[str, Any] = field(default_factory=dict)
    sector_snapshot: dict[str, Any] = field(default_factory=dict)
    # V1.5.1 market environment (real indicators + judgment)
    market_environment: dict[str, Any] = field(default_factory=dict)
    # V1.5.2 sentiment cycle (real indicators + judgment)
    sentiment_cycle_v2: dict[str, Any] = field(default_factory=dict)
    # V1.5.4 sector strength ranking.
    sector_strength_top: list[dict[str, Any]] = field(default_factory=list)
    # V1.5.5 mainline sector snapshot.
    mainline_snapshot: dict[str, Any] = field(default_factory=dict)
    # V1.5.6 sector diagnosis examples.
    sector_diagnosis_examples: list[dict[str, Any]] = field(default_factory=list)
    # Stable Chinese summary hint for the integrated V1.5 card.
    action_hint: str = "数据不足，今日仅做观察"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_market(trade_date: str | None) -> tuple[Any, str, dict[str, Any]]:
    """Return (V1.5.0_snapshot, error_or_empty, V1.5.1_env_dict)."""
    env_dict: dict[str, Any] = {}
    try:
        snap = build_market_snapshot(trade_date)
    except Exception as exc:
        from src.market.market_state import MarketSnapshot
        snap = MarketSnapshot(
            trade_date=trade_date, market_state=MARKET_UNKNOWN,
            risk_level="unknown", can_open_position="unknown",
            can_add_position="unknown", chase_high_allowed="unknown",
            action_hint="数据不足，建议仅观察",
        )
        return snap, f"market_state 构建失败：{type(exc).__name__}", env_dict

    # V1.5.1: also build real market environment judgment
    try:
        from src.market.market_environment import build_market_environment
        env = build_market_environment(trade_date)
        env_dict = env.as_dict()
        # If V1.5.1 has a real judgment (not unknown), use it to enrich
        # the V1.5.0 snapshot for downstream consumers that only read the
        # old fields.
        if env.market_state != "unknown":
            snap.market_state = env.market_state
            snap.risk_level = env.risk_level
            snap.can_open_position = "true" if env.can_open_position else "false"
            snap.can_add_position = "true" if env.can_add_position else "false"
            snap.chase_high_allowed = "true" if env.chase_high_allowed else "false"
            snap.action_hint = env.action_hint
    except Exception:
        pass  # V1.5.1 optional, don't fail the whole card

    return snap, "", env_dict


def _safe_sentiment(trade_date: str | None) -> tuple[Any, str, dict[str, Any]]:
    """Return (V1.5.0_snapshot, error, V1.5.2_sentiment_cycle_dict)."""
    cycle_dict: dict[str, Any] = {}
    try:
        snap = build_sentiment_snapshot(trade_date)
    except Exception as exc:
        from src.sentiment.sentiment_cycle import SentimentSnapshot
        snap = SentimentSnapshot(
            trade_date=trade_date, sentiment_cycle=SENTIMENT_UNKNOWN,
        )
        return snap, f"sentiment_cycle 构建失败：{type(exc).__name__}", cycle_dict

    # V1.5.2: also build real sentiment cycle judgment
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle(trade_date)
        cycle_dict = cycle.as_dict()
        # If V1.5.2 has a real judgment, enrich the V1.5.0 snapshot
        if cycle.sentiment_cycle != "unknown":
            snap.sentiment_cycle = cycle_dict.get("sentiment_cycle", SENTIMENT_UNKNOWN)
            snap.risk_hint = cycle.action_hint
    except Exception:
        pass  # V1.5.2 optional, don't fail the whole card

    return snap, "", cycle_dict


def _safe_sector(trade_date: str | None) -> tuple[dict[str, Any], str]:
    try:
        snap = build_sector_snapshot(trade_date)
        return snap, ""
    except Exception as exc:
        return {
            "trade_date": trade_date, "sectors": [],
            "data_quality_status": HEALTH_UNKNOWN,
            "issue_summary": [f"sector_snapshot 构建失败：{type(exc).__name__}"],
        }, f"sector_snapshot 构建失败：{type(exc).__name__}"


def _safe_sector_strength_top(trade_date: str | None) -> tuple[list[dict[str, Any]], str]:
    try:
        from src.sector.sector_strength import get_sector_rank
        ranking = get_sector_rank(str(trade_date), top_n=5)
        return list(ranking.as_dict().get("sectors") or []), ""
    except Exception as exc:
        return [], f"sector_strength 构建失败：{type(exc).__name__}"


def _safe_mainline_snapshot(trade_date: str | None) -> tuple[dict[str, Any], str]:
    try:
        from src.sector.sector_mainline import build_mainline_snapshot
        snapshot = build_mainline_snapshot(str(trade_date))
        return snapshot.as_dict(), ""
    except Exception as exc:
        return {
            "trade_date": trade_date,
            "confirmed_mainlines": [],
            "potential_mainlines": [],
            "one_day_themes": [],
            "cooling_sectors": [],
            "high_risk_sectors": [],
            "has_clear_mainline": False,
            "market_mainline_summary": "主线数据不足，暂不判断。",
        }, f"sector_mainline 构建失败：{type(exc).__name__}"


def _safe_sector_diagnosis_examples(
    trade_date: str | None,
    sector_strength_top: list[dict[str, Any]],
    mainline_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(sector_strength_top or [])
    for key in ("confirmed_mainlines", "potential_mainlines", "one_day_themes"):
        candidates.extend(mainline_snapshot.get(key) or [])

    seen: set[str] = set()
    examples: list[dict[str, Any]] = []
    try:
        from src.sector.sector_diagnosis import diagnose_sector_by_name
        for item in candidates:
            code = str(item.get("sector_code") or "")
            name = str(item.get("sector_name") or "")
            dedupe_key = code or name
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            diag = diagnose_sector_by_name(str(trade_date), sector_code=code or None, sector_name=name or None)
            examples.append(diag.as_dict())
            if len(examples) >= 3:
                break
        return examples, ""
    except Exception as exc:
        return examples, f"sector_diagnosis 构建失败：{type(exc).__name__}"


def _build_card_action_hint(
    market_state: str,
    sentiment_cycle: str,
    sector_strength_top: list[dict[str, Any]],
    mainline_snapshot: dict[str, Any],
) -> str:
    if market_state in ("high_risk", "weak") or sentiment_cycle in ("retreat", "cooling"):
        return "市场或情绪偏弱，今日以防守观察为主。"
    if mainline_snapshot.get("has_clear_mainline"):
        return "主线较清晰，优先观察主线板块的持续性。"
    if sector_strength_top:
        return "已有板块强度线索，等待主线确认后再提高进攻性。"
    return "数据不足，今日仅做观察。"


def build_daily_decision_card(trade_date: str | None = None) -> DailyDecisionCard:
    """Build the integrated daily decision card.

    * Resolves trade_date via market_state (which falls back to today).
    * Builds market / sentiment / sector sub-snapshots (each graceful).
    * Calls the rules layer for overall_bias + four textual outputs.
    * Returns a card with stable schema even when all data is unknown.
    """
    market_snap, m_err, market_env = _safe_market(trade_date)
    td = market_snap.trade_date

    sentiment_snap, s_err, sentiment_v2 = _safe_sentiment(td)
    sector_snap, sec_err = _safe_sector(td)
    sector_strength_top, strength_err = _safe_sector_strength_top(td)
    mainline_snapshot, mainline_err = _safe_mainline_snapshot(td)
    diagnosis_examples, diagnosis_err = _safe_sector_diagnosis_examples(
        td, sector_strength_top, mainline_snapshot,
    )

    market_state = market_snap.market_state
    sentiment_cycle = sentiment_snap.sentiment_cycle
    sector_count = len(sector_snap.get("sectors") or [])
    data_quality_status = (
        market_snap.data_quality_status
        or sector_snap.get("data_quality_status")
        or sentiment_snap.data_quality_status
        or HEALTH_UNKNOWN
    )
    risk_level = market_snap.risk_level

    overall_bias = decide_overall_bias(
        market_state, sentiment_cycle, sector_count, data_quality_status,
    )
    risk_warnings = build_risk_warnings(
        market_state, sentiment_cycle, sector_count, data_quality_status,
    )
    suggested_actions = build_suggested_actions(
        market_state, sentiment_cycle, sector_count, data_quality_status,
    )
    observation_conditions = build_observation_conditions(
        market_state, sentiment_cycle, sector_count, data_quality_status,
    )
    invalidation_conditions = build_invalidation_conditions(
        market_state, sentiment_cycle, sector_count, data_quality_status,
    )

    # Issue summary — gather sub-module issues + errors.
    issues: list[str] = []
    if m_err:
        issues.append(m_err)
    if s_err:
        issues.append(s_err)
    if sec_err:
        issues.append(sec_err)
    if strength_err:
        issues.append(strength_err)
    if mainline_err:
        issues.append(mainline_err)
    if diagnosis_err:
        issues.append(diagnosis_err)
    issues.extend(market_snap.issue_summary or [])
    issues.extend(sector_snap.get("issue_summary") or [])
    if not issues:
        issues.append("V1.5.0 骨架版本：市场/情绪/板块判断口径待后续版本完善")

    # Serialise sectors to dict for downstream Markdown/UI.
    sector_dicts = [r.as_dict() for r in (sector_snap.get("sectors") or [])]
    action_hint = _build_card_action_hint(
        market_state, sentiment_cycle, sector_strength_top, mainline_snapshot,
    )

    return DailyDecisionCard(
        trade_date=td,
        overall_bias=overall_bias,
        market_state=market_state,
        sentiment_cycle=sentiment_cycle,
        risk_level=risk_level,
        strong_sectors=sector_dicts,
        risk_warnings=risk_warnings,
        suggested_actions=suggested_actions,
        observation_conditions=observation_conditions,
        invalidation_conditions=invalidation_conditions,
        data_quality_status=data_quality_status,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        issue_summary=issues,
        market_snapshot=market_snap.as_dict(),
        sentiment_snapshot=sentiment_snap.as_dict(),
        sector_snapshot=sector_snap,
        market_environment=market_env,
        sentiment_cycle_v2=sentiment_v2,
        sector_strength_top=sector_strength_top,
        mainline_snapshot=mainline_snapshot,
        sector_diagnosis_examples=diagnosis_examples,
        action_hint=action_hint,
    )
