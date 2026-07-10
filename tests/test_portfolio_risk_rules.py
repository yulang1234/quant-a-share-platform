"""Test portfolio risk rules — scoring, thresholds, permissions."""

import pytest

from src.portfolio.portfolio_risk_rules import (
    calculate_top_n_concentration,
    calculate_total_position_pct,
    classify_portfolio_permission,
    classify_risk_level,
    evaluate_consecutive_loss_risk,
    evaluate_market_exposure_risk,
    evaluate_portfolio_drawdown_risk,
    evaluate_sector_concentration_risk,
    evaluate_single_position_risk,
    generate_risk_recommendations,
)
from src.portfolio.portfolio_risk_types import PortfolioRiskResult


def _pos(code, pct):
    return {"stock_code": code, "position_pct": pct, "sector_name": "测试板块"}


class TestTotalPosition:
    def test_normal(self) -> None:
        r = calculate_total_position_pct([_pos("a", 30), _pos("b", 20)])
        assert r["total_position_pct"] == 50
        assert r["cash_pct"] == 50

    def test_over_100(self) -> None:
        r = calculate_total_position_pct([_pos("a", 60), _pos("b", 50)])
        assert r["total_position_pct"] == 110
        assert r["cash_pct"] is None

    def test_missing(self) -> None:
        r = calculate_total_position_pct([{"stock_code": "a"}])
        assert r["issues"]


class TestSinglePositionRisk:
    def test_low(self) -> None:
        dim = evaluate_single_position_risk([_pos("a", 10)])
        assert dim.risk_level == "low"

    def test_high(self) -> None:
        dim = evaluate_single_position_risk([_pos("a", 25)])
        assert dim.risk_level == "high"

    def test_critical(self) -> None:
        dim = evaluate_single_position_risk([_pos("a", 35)])
        assert dim.risk_level == "critical"


class TestSectorConcentration:
    def test_low(self) -> None:
        r = evaluate_sector_concentration_risk([_pos("a", 15), _pos("b", 10)])
        assert r["dimension"].risk_level == "low"

    def test_high(self) -> None:
        r = evaluate_sector_concentration_risk([_pos("a", 30), _pos("b", 15)])
        assert r["dimension"].risk_level == "high"

    def test_critical(self) -> None:
        r = evaluate_sector_concentration_risk([_pos("a", 40), _pos("b", 20)])
        assert r["dimension"].risk_level == "critical"


class TestTopN:
    def test_top3(self) -> None:
        positions = [_pos("a", 30), _pos("b", 20), _pos("c", 10), _pos("d", 5)]
        assert calculate_top_n_concentration(positions, 3) == 60


class TestMarketExposure:
    def test_attack_ok(self) -> None:
        dim = evaluate_market_exposure_risk(50, {"market_state": "attack"}, {"sentiment_cycle": "warming"})
        assert dim.risk_level == "low"

    def test_defense_high_position(self) -> None:
        dim = evaluate_market_exposure_risk(70, {"market_state": "defense"}, {"sentiment_cycle": "cooling"})
        assert dim.risk_level in ("high", "critical")

    def test_high_risk_high_position(self) -> None:
        dim = evaluate_market_exposure_risk(50, {"market_state": "high_risk"}, {"sentiment_cycle": "retreat"})
        assert dim.risk_level == "critical"


class TestDrawdown:
    def test_low(self) -> None:
        cumulative = [{"trade_date": f"2026-07-{i:02d}", "cumulative": 1.0 - i * 0.001} for i in range(30)]
        r = evaluate_portfolio_drawdown_risk({"cumulative": cumulative})
        assert r["dimension"].risk_level == "low"

    def test_high(self) -> None:
        cumulative = [{"trade_date": f"2026-07-{i:02d}", "cumulative": 1.0 - i * 0.008} for i in range(30)]
        r = evaluate_portfolio_drawdown_risk({"cumulative": cumulative})
        assert r["dimension"].risk_level in ("high", "critical")


class TestConsecutiveLoss:
    def test_low(self) -> None:
        dr = [{"return": -0.01} for _ in range(2)] + [{"return": 0.01}]
        dim = evaluate_consecutive_loss_risk({"daily_returns": dr})
        assert dim.risk_level == "low"

    def test_high(self) -> None:
        dr = [{"return": -0.01} for _ in range(5)]
        dim = evaluate_consecutive_loss_risk({"daily_returns": dr})
        assert dim.risk_level == "high"


class TestClassifyLevel:
    def test_low(self) -> None:
        assert classify_risk_level(10, 0.9) == "low"

    def test_critical(self) -> None:
        assert classify_risk_level(80, 0.9) == "critical"

    def test_low_coverage_unknown(self) -> None:
        assert classify_risk_level(10, 0.3) == "unknown"


class TestPermission:
    def test_normal(self) -> None:
        r = PortfolioRiskResult(portfolio_risk_level="low", data_coverage_ratio=0.9)
        assert classify_portfolio_permission(r) == "normal"

    def test_critical(self) -> None:
        r = PortfolioRiskResult(portfolio_risk_level="critical", data_coverage_ratio=0.9)
        assert classify_portfolio_permission(r) == "reduce_exposure_conditionally"

    def test_low_coverage_manual_review(self) -> None:
        r = PortfolioRiskResult(data_coverage_ratio=0.3)
        assert classify_portfolio_permission(r) == "manual_review"


class TestRecommendations:
    def test_generates(self) -> None:
        r = PortfolioRiskResult(
            max_single_position_pct=30, max_single_position_code="000001",
            max_sector_position_pct=45, max_sector_name="银行",
            high_correlation_pair_count=2, portfolio_drawdown_60d=12,
            consecutive_loss_days=5, dangerous_position_count=1,
            total_position_pct=80, market_state="defense",
            data_coverage_ratio=0.8,
        )
        recs = generate_risk_recommendations(r)
        assert recs["risk_flags"]
        assert recs["recommendations"]

    def test_empty_flags_default(self) -> None:
        r = PortfolioRiskResult(data_coverage_ratio=0.9)
        recs = generate_risk_recommendations(r)
        assert "暂无严重风险标记" in recs["risk_flags"]
