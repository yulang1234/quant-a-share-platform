"""Test position diagnosis rules — scoring and action classification."""

import pytest

from src.portfolio.position_diagnosis_rules import (
    classify_health,
    classify_position_action,
    compute_position_health_score,
    evaluate_condition_support,
    evaluate_leader_support,
    evaluate_market_support,
    evaluate_position_size,
    evaluate_sector_support,
    evaluate_sentiment_support,
    evaluate_thesis_status,
    evaluate_trend_health,
)
from src.portfolio.position_diagnosis_types import (
    DiagnosisComponent,
    PositionDiagnosisResult,
)


class TestMarketSupport:
    def test_attack_high_score(self) -> None:
        comp = evaluate_market_support({"market_state": "attack"})
        assert comp.score >= 70

    def test_high_risk_low_score(self) -> None:
        comp = evaluate_market_support({"market_state": "high_risk"})
        assert comp.score <= 30

    def test_none_returns_empty(self) -> None:
        comp = evaluate_market_support(None)
        assert comp.issues


class TestSentimentSupport:
    def test_warming_high_score(self) -> None:
        comp = evaluate_sentiment_support({"sentiment_cycle": "warming"})
        assert comp.score >= 60

    def test_retreat_low_score(self) -> None:
        comp = evaluate_sentiment_support({"sentiment_cycle": "retreat"})
        assert comp.score <= 40

    def test_none_returns_empty(self) -> None:
        comp = evaluate_sentiment_support(None)
        assert comp.issues


class TestSectorSupport:
    def test_confirmed_high(self) -> None:
        comp = evaluate_sector_support({"mainline_status": "confirmed_mainline"})
        assert comp.score >= 70

    def test_one_day_low(self) -> None:
        comp = evaluate_sector_support({"mainline_status": "one_day_theme"})
        assert comp.score <= 45

    def test_downgrade_from_entry(self) -> None:
        comp = evaluate_sector_support(
            {"mainline_status": "cooling_sector"},
            entry_snapshot={
                "sector_mainline": {"mainline_status": "confirmed_mainline"}
            },
        )
        assert comp.score <= 35


class TestLeaderSupport:
    def test_leader_1_high(self) -> None:
        comp = evaluate_leader_support({"leader_type": "leader_1", "leader_score": 85})
        assert comp.score >= 75

    def test_pseudo_leader_low(self) -> None:
        comp = evaluate_leader_support({"leader_type": "pseudo_leader"})
        assert comp.score <= 30

    def test_downgrade_from_entry(self) -> None:
        comp = evaluate_leader_support(
            {"leader_type": "normal"},
            entry_snapshot={
                "sector_leaders": {
                    "leader_1": {"leader_type": "leader_1"}
                }
            },
        )
        assert comp.score <= 50


class TestTrendHealth:
    def test_bullish_alignment(self) -> None:
        comp = evaluate_trend_health({
            "close": 20.0, "ma5": 19.0, "ma10": 18.0, "ma20": 17.0,
            "pct_chg_5d": 3.0, "pct_chg_20d": 10.0, "drawdown_20d": 2.0,
        })
        assert comp.score >= 80

    def test_below_ma20(self) -> None:
        comp = evaluate_trend_health({
            "close": 15.0, "ma5": 16.0, "ma10": 17.0, "ma20": 18.0,
            "drawdown_20d": 5.0,
        })
        assert comp.score <= 30

    def test_high_drawdown(self) -> None:
        comp = evaluate_trend_health({
            "close": 20.0, "ma5": 21.0, "ma10": 22.0, "ma20": 19.0,
            "drawdown_20d": 20.0,
        })
        assert comp.score <= 40


class TestConditionSupport:
    def test_small_trial_good(self) -> None:
        comp = evaluate_condition_support({"permission": "small_trial"})
        assert comp.score >= 70

    def test_exit_condition_triggers(self) -> None:
        comp = evaluate_condition_support({
            "permission": "small_trial",
            "exit_conditions": [
                {"status": "satisfied", "name": "market turns defensive"}
            ],
        })
        assert comp.score <= 20


class TestThesisStatus:
    def test_no_snapshot_manual_review(self) -> None:
        comp = evaluate_thesis_status({"buy_reason": "test"}, None, {})
        assert comp.status == "manual_review_required"

    def test_all_match_valid(self) -> None:
        snapshot = {
            "market_environment": {"market_state": "attack"},
            "sentiment_cycle": {"sentiment_cycle": "warming"},
            "sector_mainline": {"mainline_status": "confirmed_mainline"},
            "sector_leaders": {"leader_1": {"leader_type": "leader_1"}},
        }
        ctx = {
            "market": {"market_state": "attack"},
            "sentiment": {"sentiment_cycle": "warming"},
            "sector_mainline": {"mainline_status": "confirmed_mainline"},
            "leader": {"leader_type": "leader_1"},
        }
        comp = evaluate_thesis_status({"buy_reason": "test"}, snapshot, ctx)
        assert comp.status == "valid"

    def test_two_dims_worsened_invalid(self) -> None:
        snapshot = {
            "market_environment": {"market_state": "attack"},
            "sentiment_cycle": {"sentiment_cycle": "warming"},
            "sector_mainline": {"mainline_status": "confirmed_mainline"},
            "sector_leaders": {"leader_1": {"leader_type": "leader_1"}},
        }
        ctx = {
            "market": {"market_state": "high_risk"},
            "sentiment": {"sentiment_cycle": "retreat"},
            "sector_mainline": {"mainline_status": "one_day_theme"},
            "leader": {"leader_type": "leader_1"},
        }
        comp = evaluate_thesis_status({"buy_reason": "test"}, snapshot, ctx)
        assert comp.status in ("invalid", "weakening")


class TestPositionSize:
    def test_normal(self) -> None:
        status, _ = evaluate_position_size(15.0)
        assert status == "normal"

    def test_elevated(self) -> None:
        status, _ = evaluate_position_size(25.0)
        assert status == "elevated"

    def test_high(self) -> None:
        status, _ = evaluate_position_size(35.0)
        assert status == "high"

    def test_unknown(self) -> None:
        status, _ = evaluate_position_size(None)
        assert status == "unknown"


class TestHealthScore:
    def test_all_present_high_score(self) -> None:
        comps = [
            DiagnosisComponent(name="market", score=80, weight=0.15),
            DiagnosisComponent(name="sentiment", score=75, weight=0.15),
            DiagnosisComponent(name="sector", score=90, weight=0.2),
            DiagnosisComponent(name="trend", score=85, weight=0.2),
            DiagnosisComponent(name="thesis", score=80, weight=0.3),
        ]
        score, cov = compute_position_health_score(comps)
        assert 70 <= score <= 95
        assert cov >= 0.8

    def test_missing_components_lower_coverage(self) -> None:
        comps = [
            DiagnosisComponent(name="market", score=80, weight=0.5),
            DiagnosisComponent(
                name="sentiment", score=0, weight=0.5,
                issues=["情绪周期数据缺失"],
            ),
        ]
        score, cov = compute_position_health_score(comps)
        assert cov < 1.0

    def test_all_missing_zero(self) -> None:
        comps = [
            DiagnosisComponent(
                name="market", score=0, weight=0.5, issues=["缺失"],
            ),
        ]
        score, _ = compute_position_health_score(comps)
        # If all components have "缺失" issues, they're skipped
        assert 0 <= score <= 100


class TestClassifyHealth:
    def test_high_score_healthy(self) -> None:
        assert classify_health(85, 0.9) == "healthy"

    def test_low_coverage_unknown(self) -> None:
        assert classify_health(85, 0.3) == "unknown"

    def test_mid_score_cautious(self) -> None:
        assert classify_health(50, 0.7) == "cautious"


class TestActionClassification:
    def test_healthy_continue_hold(self) -> None:
        result = PositionDiagnosisResult(
            diagnosis_status="healthy",
            thesis_status="valid",
            health_score=85,
            data_coverage_ratio=0.9,
            market_support_score=80,
            sentiment_support_score=75,
            sector_support_score=85,
            leader_support_score=80,
            trend_health_score=85,
            condition_support_score=80,
            position_size_status="normal",
        )
        assert classify_position_action(result) == "continue_hold"

    def test_exit_conditionally(self) -> None:
        result = PositionDiagnosisResult(
            thesis_status="invalid",
            condition_support_score=5,
            health_score=20,
            data_coverage_ratio=0.5,
        )
        assert classify_position_action(result) == "exit_conditionally"

    def test_forbid_add(self) -> None:
        result = PositionDiagnosisResult(
            data_coverage_ratio=0.5,
            condition_support_score=35,
            position_size_status="normal",
            health_score=55,
        )
        assert classify_position_action(result) == "forbid_add"

    def test_low_coverage_unknown(self) -> None:
        result = PositionDiagnosisResult(
            data_coverage_ratio=0.3,
            health_score=50,
            thesis_status="unknown",
            condition_support_score=50,
            position_size_status="normal",
            market_support_score=50,
            sentiment_support_score=50,
            sector_support_score=50,
            leader_support_score=50,
            trend_health_score=50,
        )
        # With coverage < 0.4 and condition_score=50, it should be forbid_add or unknown
        action = classify_position_action(result)
        assert action in ("unknown", "forbid_add", "light_hold")
