"""V1.6.2 Opportunity scoring tests."""
import pytest
from src.opportunity.opportunity_scoring import (
    market_safety, sentiment_safety, sector_mainline_score,
    leader_certainty, entry_odds, risk_discount, compute_opportunity,
)


class TestMarketSafety:
    def test_attack_low_risk(self):
        s, _ = market_safety({"market_state": "attack", "risk_level": "low"})
        assert s >= 75

    def test_defense(self):
        s, _ = market_safety({"market_state": "defense"})
        assert s < 50

    def test_none(self):
        s, _ = market_safety(None)
        assert 0 <= s <= 100


class TestSentimentSafety:
    def test_warming(self):
        s, _ = sentiment_safety({"sentiment_cycle": "warming"})
        assert s >= 70

    def test_retreat(self):
        s, _ = sentiment_safety({"sentiment_cycle": "retreat"})
        assert s < 30

    def test_none(self):
        s, _ = sentiment_safety(None)
        assert 0 <= s <= 100


class TestMainline:
    def test_confirmed(self):
        s, _ = sector_mainline_score({"mainline_status": "confirmed_mainline", "mainline_probability": 80})
        assert s >= 70

    def test_one_day(self):
        s, _ = sector_mainline_score({"mainline_status": "one_day_theme"})
        assert s < 45


class TestLeaderCertainty:
    def test_leader_1(self):
        s, _ = leader_certainty({"leader_type": "leader_1", "leader_score": 90})
        assert s >= 80

    def test_high_risk(self):
        s, _ = leader_certainty({"leader_type": "high_risk_chasing"})
        assert s < 30


class TestComputeOpportunity:
    def test_good_signals_score_high(self):
        r = compute_opportunity(
            {"market_state": "attack", "risk_level": "low"},
            {"sentiment_cycle": "warming"},
            {"mainline_status": "confirmed_mainline", "mainline_probability": 85},
            {"leader_type": "leader_1", "leader_score": 90},
            {"pct_chg_5d": 5, "above_ma5": True, "above_ma10": True, "above_ma20": True, "drawdown_20d": 3},
        )
        assert r["opportunity_score"] >= 65
        assert r["opportunity_level"] in ("high", "very_high")

    def test_bad_signals_score_low(self):
        r = compute_opportunity(
            {"market_state": "defense"}, {"sentiment_cycle": "retreat"},
            {"mainline_status": "cooling_sector"},
            {"leader_type": "pseudo_leader", "leader_score": 30},
            {"pct_chg_5d": 25, "above_ma5": False, "above_ma10": False, "drawdown_20d": 15},
        )
        assert r["opportunity_score"] < 40

    def test_score_in_range(self):
        r = compute_opportunity(None, None, None, None, None)
        assert 0 <= r["opportunity_score"] <= 100


class TestSafetyKeywords:
    def test_no_forbidden(self):
        with open("src/opportunity/opportunity_scoring.py") as f:
            src = f.read()
        for w in ["买入", "卖出", "加仓", "清仓", "满仓", "重仓", "梭哈"]:
            assert w not in src, f"Forbidden: {w}"
