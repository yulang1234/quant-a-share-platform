"""V1.5.6 sector diagnosis tests.

Tests cover:
1. Confirmed mainline diagnosis
2. Potential mainline diagnosis
3. One-day theme diagnosis
4. Cooling sector diagnosis
5. High-risk sector diagnosis
6. Neutral sector diagnosis
7. Market environment poor fit
8. Sentiment cycle poor fit
9. Data insufficient
10. Field completeness
11. Version boundary
12. Regression
"""
from __future__ import annotations

import pytest

from src.sector.sector_diagnosis_types import (
    DIAG_HEALTHY, DIAG_WATCH, DIAG_WAIT, DIAG_CAUTIOUS,
    DIAG_HIGH_RISK, DIAG_COOLING, DIAG_AVOID, DIAG_UNKNOWN,
    FIT_GOOD, FIT_NEUTRAL, FIT_POOR, FIT_UNKNOWN,
    ACTION_OBSERVE, ACTION_FOCUS_WATCH, ACTION_AVOID_CHASE, ACTION_CANCEL_WATCH,
    ACTION_UNKNOWN,
    ODDS_GOOD, ODDS_NORMAL, ODDS_POOR, ODDS_HIGH_RISK, ODDS_UNKNOWN,
    LEADER_PENDING,
)
from src.sector.sector_mainline_types import (
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
    RISK_OVERHEAT, RISK_ONE_DAY_SPIKE, RISK_TURNOVER_ABNORMAL,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _diagnose(market=None, sentiment=None, strength=None, mainline=None) -> dict:
    from src.rules.sector_diagnosis_rules import diagnose_sector
    return diagnose_sector(market, sentiment, strength, mainline)


def _mk_market(state="attack", risk="low"):
    return {"market_state": state, "risk_level": risk}


def _mk_sentiment(cycle="warming"):
    return {"sentiment_cycle": cycle}


def _mk_strength(score=85, r5=6.0, rs5=4.0, up_ratio=0.75, t20=1.2):
    return {
        "strength_score": score, "strength_level": "very_strong",
        "return_3d": 4.0, "return_5d": r5, "return_10d": 10.0, "return_20d": 12.0,
        "relative_strength_3d": 3.0, "relative_strength_5d": rs5,
        "relative_strength_10d": 5.0, "relative_strength_20d": 6.0,
        "turnover_ratio_20d": t20,
        "up_ratio": up_ratio, "limit_up_count": 5, "big_loss_count": 1,
    }


def _mk_mainline(status=MAINLINE_CONFIRMED, score=86, confidence="high",
                 rank=3, persistence=4, risk_flags=None):
    return {
        "mainline_status": status, "mainline_score": score,
        "confidence": confidence, "rank_overall": rank,
        "persistence_days": persistence,
        "risk_flags": risk_flags or [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 1. Confirmed mainline diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestConfirmedMainlineDiagnosis:
    def test_healthy_when_all_good(self):
        result = _diagnose(
            _mk_market("attack"), _mk_sentiment("warming"),
            _mk_strength(88), _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["diagnosis_status"] in (DIAG_HEALTHY, DIAG_WATCH)
        assert result["market_fit"] == FIT_GOOD
        assert result["sentiment_fit"] == FIT_GOOD
        assert result["mainline_probability"] >= 70
        assert result["leader_structure"] == LEADER_PENDING
        assert len(result["reasons"]) >= 1
        assert result["action_hint"]

    def test_suggested_action_is_focus_watch(self):
        result = _diagnose(
            _mk_market("attack"), _mk_sentiment("warming"),
            _mk_strength(88), _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["suggested_action"] in (ACTION_FOCUS_WATCH, ACTION_OBSERVE)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Potential mainline diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestPotentialMainlineDiagnosis:
    def test_watch_with_observation_conditions(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("repair"),
            _mk_strength(72, r5=3.0, rs5=1.5),
            _mk_mainline(MAINLINE_POTENTIAL, 65, "medium", rank=10, persistence=1),
        )
        assert result["diagnosis_status"] == DIAG_WATCH
        assert len(result["observation_conditions"]) >= 1
        assert len(result["invalidation_conditions"]) >= 1
        assert result["mainline_probability"] >= 30

    def test_observation_mentions_persistence(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("repair"),
            _mk_strength(72),
            _mk_mainline(MAINLINE_POTENTIAL, 65, "medium", rank=10, persistence=1),
        )
        obs_text = " ".join(result["observation_conditions"])
        assert "排名" in obs_text or "strength" in obs_text.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 3. One-day theme diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestOneDayThemeDiagnosis:
    def test_cautious_with_poor_odds(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("chaotic"),
            _mk_strength(75, t20=2.5),
            _mk_mainline(MAINLINE_ONE_DAY, 55, "medium", rank=5, persistence=0,
                         risk_flags=[RISK_ONE_DAY_SPIKE]),
        )
        assert result["diagnosis_status"] in (DIAG_CAUTIOUS, DIAG_WATCH)
        assert result["buy_point_odds"] == ODDS_POOR
        assert result["suggested_action"] != ACTION_FOCUS_WATCH


# ══════════════════════════════════════════════════════════════════════════════
# 4. Cooling sector diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestCoolingSectorDiagnosis:
    def test_cooling_status(self):
        result = _diagnose(
            _mk_market("defense"), _mk_sentiment("cooling"),
            _mk_strength(42, r5=-2.0, rs5=-1.5, up_ratio=0.35),
            _mk_mainline(MAINLINE_COOLING, 38, "medium", rank=25, persistence=0,
                         risk_flags=["rank_drop"]),
        )
        assert result["diagnosis_status"] == DIAG_COOLING
        assert result["suggested_action"] == ACTION_CANCEL_WATCH
        assert result["risk_level"] in ("high", "medium")


# ══════════════════════════════════════════════════════════════════════════════
# 5. High-risk sector diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestHighRiskSectorDiagnosis:
    def test_high_risk_with_avoid_chase(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("climax"),
            _mk_strength(90, t20=2.2),
            _mk_mainline(MAINLINE_HIGH_RISK, 42, "high", rank=2, persistence=3,
                         risk_flags=[RISK_OVERHEAT, RISK_TURNOVER_ABNORMAL]),
        )
        assert result["diagnosis_status"] == DIAG_HIGH_RISK
        assert result["suggested_action"] == ACTION_AVOID_CHASE
        assert result["buy_point_odds"] == ODDS_HIGH_RISK
        assert result["risk_level"] in ("extreme", "high")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Neutral sector diagnosis
# ══════════════════════════════════════════════════════════════════════════════


class TestNeutralDiagnosis:
    def test_wait_when_neutral(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("unknown"),
            _mk_strength(50, r5=0.5, rs5=0.0, up_ratio=0.5),
            _mk_mainline(MAINLINE_NEUTRAL, 20, "low", rank=40, persistence=0),
        )
        assert result["diagnosis_status"] in (DIAG_WAIT, DIAG_UNKNOWN)
        assert result["mainline_probability"] <= 30


# ══════════════════════════════════════════════════════════════════════════════
# 7. Market environment poor fit
# ══════════════════════════════════════════════════════════════════════════════


class TestMarketPoorFit:
    def test_market_defense_downgrades_action(self):
        result = _diagnose(
            _mk_market("defense"), _mk_sentiment("warming"),
            _mk_strength(85),
            _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["market_fit"] == FIT_POOR
        assert result["diagnosis_status"] == DIAG_CAUTIOUS
        assert result["suggested_action"] != ACTION_FOCUS_WATCH

    def test_market_high_risk_poor_fit(self):
        result = _diagnose(
            _mk_market("high_risk"), _mk_sentiment("warming"),
            _mk_strength(85),
            _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["market_fit"] == FIT_POOR


# ══════════════════════════════════════════════════════════════════════════════
# 8. Sentiment cycle poor fit
# ══════════════════════════════════════════════════════════════════════════════


class TestSentimentPoorFit:
    def test_retreat_downgrades_action(self):
        result = _diagnose(
            _mk_market("attack"), _mk_sentiment("retreat"),
            _mk_strength(85),
            _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["sentiment_fit"] == FIT_POOR
        assert result["risk_level"] in ("high", "extreme")

    def test_cooling_sentiment_poor(self):
        result = _diagnose(
            _mk_market("neutral"), _mk_sentiment("cooling"),
            _mk_strength(60),
            _mk_mainline(MAINLINE_POTENTIAL, 65, "medium"),
        )
        assert result["sentiment_fit"] == FIT_POOR


# ══════════════════════════════════════════════════════════════════════════════
# 9. Data insufficient
# ══════════════════════════════════════════════════════════════════════════════


class TestDataInsufficient:
    def test_no_data_returns_unknown(self):
        result = _diagnose(None, None, None, None)
        assert result["diagnosis_status"] == DIAG_UNKNOWN
        assert result["suggested_action"] == ACTION_UNKNOWN
        assert len(result["missing_indicator_names"]) >= 2
        assert result["mainline_probability"] == 0

    def test_missing_sentiment_still_works(self):
        result = _diagnose(
            _mk_market("attack"), None,
            _mk_strength(85),
            _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["diagnosis_status"] != "error"
        assert "sentiment_cycle" in result["missing_indicator_names"]


# ══════════════════════════════════════════════════════════════════════════════
# 10. Field completeness
# ══════════════════════════════════════════════════════════════════════════════


class TestFieldCompleteness:
    REQUIRED = [
        "diagnosis_status", "mainline_status", "mainline_probability",
        "market_fit", "sentiment_fit", "strength_score", "strength_level",
        "strength_rank", "trend_stage", "leader_structure",
        "buy_point_odds", "risk_level", "suggested_action",
        "action_hint", "observation_conditions", "invalidation_conditions",
        "risk_flags", "missing_indicator_names", "reasons",
    ]

    def test_all_required_fields_present(self):
        result = _diagnose(
            _mk_market("attack"), _mk_sentiment("warming"),
            _mk_strength(88), _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        for field in self.REQUIRED:
            assert field in result, f"Missing field: {field}"
        assert result["action_hint"]  # non-empty

    def test_sector_diagnosis_dataclass_fields(self):
        from src.sector.sector_diagnosis_types import SectorDiagnosis
        d = SectorDiagnosis(
            trade_date="2026-07-09", sector_code="BK_X",
            sector_name="测试", sector_type="industry",
        )
        dd = d.as_dict()
        for field in self.REQUIRED:
            assert field in dd, f"Missing in dataclass: {field}"
        assert dd["version"] == "v1.5.6"


# ══════════════════════════════════════════════════════════════════════════════
# 11. Version boundary
# ══════════════════════════════════════════════════════════════════════════════


class TestVersionBoundary:
    def test_no_trading_advice(self):
        """V1.5.6 must not output buy/sell/leader names."""
        from src.sector.sector_diagnosis_types import SectorDiagnosis
        # Check field names don't contain forbidden words
        # Note: buy_point_odds is explicitly allowed per V1.5.6 spec
        allowed = {"buy_point_odds"}
        forbidden = ["sell", "买入", "卖出", "leader_name", "龙头股",
                     "龙一", "龙二", "target_price", "stop_loss"]
        for name in SectorDiagnosis.__dataclass_fields__:
            if name in allowed:
                continue
            lower = name.lower()
            for f in forbidden:
                assert f not in lower, f"Forbidden: {name}"

    def test_leader_structure_is_placeholder(self):
        result = _diagnose(
            _mk_market("attack"), _mk_sentiment("warming"),
            _mk_strength(88), _mk_mainline(MAINLINE_CONFIRMED, 86),
        )
        assert result["leader_structure"] in (
            "pending_v1.6.1", "not_available", "insufficient_data",
            "rough_structure_only",
        )
        # Must not contain actual stock names
        assert "000" not in str(result["leader_structure"])


# ══════════════════════════════════════════════════════════════════════════════
# 12. Regression
# ══════════════════════════════════════════════════════════════════════════════


class TestRegression:
    def test_v155_still_works(self):
        from src.sector.sector_mainline_types import SectorMainlineResult
        r = SectorMainlineResult(
            trade_date="2026-07-09", sector_code="BK_X",
            sector_name="test", sector_type="industry",
        )
        assert r.version == "v1.5.5"

    def test_v154_still_works(self):
        from src.sector.sector_strength_types import SectorStrengthResult
        r = SectorStrengthResult(
            trade_date="2026-07-09", sector_code="BK_X",
            sector_name="test", sector_type="industry", source="test",
        )
        assert r.version == "v1.5.4"

    def test_v152_still_works(self):
        from src.sentiment.sentiment_types import SentimentCycle
        c = SentimentCycle(
            trade_date="2026-07-09", sentiment_cycle="unknown",
            sentiment_score=0, risk_level="unknown",
            can_try_position=False, can_attack=False,
            relay_risk_level="unknown", chase_high_allowed=False,
            action_hint="test",
        )
        assert c.version == "v1.5.2"
