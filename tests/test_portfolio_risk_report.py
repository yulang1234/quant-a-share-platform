"""Test portfolio risk report."""

from src.portfolio.portfolio_risk_report import build_all_portfolios_risk_markdown, build_portfolio_risk_markdown

DISCLAIMER = "不构成投资建议"


def _result():
    return {
        "trade_date": "2026-07-01", "portfolio_name": "default", "is_simulated": False,
        "portfolio_risk_score": 45.0, "portfolio_risk_level": "medium", "portfolio_permission": "watch",
        "position_count": 3, "total_position_pct": 60.0, "cash_pct": 40.0,
        "max_single_position_pct": 25.0, "max_single_position_code": "000001",
        "max_sector_position_pct": 35.0, "max_sector_name": "银行",
        "top3_position_pct": 55.0,
        "high_correlation_pair_count": 1, "average_pairwise_correlation": 0.55, "max_pairwise_correlation": 0.7,
        "portfolio_drawdown_20d": 5.0, "portfolio_drawdown_60d": 8.0,
        "consecutive_loss_days": 3, "dangerous_position_count": 0,
        "cautious_position_count": 1, "unknown_position_count": 0,
        "market_state": "neutral", "sentiment_cycle": "warming",
        "sector_count": 2, "crowded_sector_count": 0,
        "risk_dimensions": [
            {"name": "single_position", "risk_score": 40, "risk_level": "medium", "reason": "test"},
            {"name": "market_exposure", "risk_score": 20, "risk_level": "low", "reason": "ok"},
        ],
        "sector_exposures": [{"sector_name": "银行", "position_count": 2, "total_position_pct": 35.0, "concentration_level": "medium"}],
        "correlation_pairs": [{"stock_a": "000001", "stock_b": "600519", "correlation": 0.55, "risk_level": "medium"}],
        "risk_flags": ["单股仓位集中"], "recommendations": ["检查高集中个股"],
        "observation_conditions": ["持续监控"], "risk_release_conditions": ["仓位下降"],
        "data_coverage_ratio": 0.85, "data_quality_status": "ok",
        "issue_summary": [],
    }


class TestReport:
    def test_single(self) -> None:
        md = build_portfolio_risk_markdown(_result())
        assert "组合风险控制报告" in md
        assert "风险总览" in md
        assert DISCLAIMER in md

    def test_empty(self) -> None:
        md = build_portfolio_risk_markdown({})
        assert "组合风险控制报告" in md

    def test_has_approx_weight_note(self) -> None:
        md = build_portfolio_risk_markdown(_result())
        assert "近似" in md

    def test_no_trading(self) -> None:
        md = build_portfolio_risk_markdown(_result())
        for forbidden in ["立即卖出", "立即清仓", "自动调仓", "满仓", "梭哈"]:
            assert forbidden not in md

    def test_all_portfolios(self) -> None:
        md = build_all_portfolios_risk_markdown([_result()])
        assert "全组合风险控制报告" in md
        assert DISCLAIMER in md
