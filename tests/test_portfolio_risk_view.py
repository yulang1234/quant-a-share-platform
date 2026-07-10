"""Test portfolio_risk_view."""

from ui.components.portfolio_risk_view import (
    correlation_pairs_to_df,
    portfolio_permission_to_cn,
    portfolio_risk_csv_bytes,
    portfolio_risk_markdown_bytes,
    portfolio_risk_to_df,
    risk_dimensions_to_df,
    risk_level_to_cn,
    sector_exposure_to_df,
)


def _result():
    return {
        "trade_date": "2026-07-01", "portfolio_name": "default", "is_simulated": False,
        "portfolio_risk_score": 45.0, "portfolio_risk_level": "medium", "portfolio_permission": "watch",
        "position_count": 2, "total_position_pct": 50.0,
        "max_single_position_pct": 30.0, "max_single_position_code": "000001",
        "max_sector_position_pct": 30.0, "max_sector_name": "银行",
        "top3_position_pct": 50.0,
        "high_correlation_pair_count": 0, "average_pairwise_correlation": 0.4, "max_pairwise_correlation": 0.4,
        "portfolio_drawdown_20d": 3.0, "portfolio_drawdown_60d": 5.0,
        "consecutive_loss_days": 1, "dangerous_position_count": 0,
        "cautious_position_count": 0, "unknown_position_count": 0,
        "market_state": "attack", "sentiment_cycle": "warming",
        "risk_dimensions": [
            {"name": "single_position", "risk_score": 40, "risk_level": "medium", "weight": 0.2, "current_value": "30%", "threshold": "15%", "reason": "test"},
        ],
        "sector_exposures": [{"sector_name": "银行", "position_count": 2, "total_position_pct": 30.0, "concentration_level": "medium"}],
        "correlation_pairs": [],
        "risk_flags": [], "recommendations": [], "observation_conditions": [], "risk_release_conditions": [],
        "data_coverage_ratio": 0.9, "data_quality_status": "ok",
        "issue_summary": [],
    }


class TestDf:
    def test_to_df(self) -> None:
        df = portfolio_risk_to_df([_result()])
        assert len(df) == 1

    def test_empty(self) -> None:
        assert portfolio_risk_to_df([]).empty
        assert portfolio_risk_to_df(None).empty

    def test_dimensions_df(self) -> None:
        df = risk_dimensions_to_df(_result())
        assert len(df) == 1

    def test_sector_df(self) -> None:
        df = sector_exposure_to_df(_result())
        assert len(df) == 1

    def test_corr_df(self) -> None:
        df = correlation_pairs_to_df(_result())
        assert df.empty


class TestCnMapping:
    def test_risk_level(self) -> None:
        assert risk_level_to_cn("low") == "低风险"
        assert risk_level_to_cn("critical") == "严重风险"

    def test_permission(self) -> None:
        assert portfolio_permission_to_cn("normal") == "正常"
        assert portfolio_permission_to_cn("freeze_new_positions") == "暂停新增持仓"


class TestExport:
    def test_csv(self) -> None:
        data = portfolio_risk_csv_bytes([_result()])
        assert len(data) > 0

    def test_md(self) -> None:
        data = portfolio_risk_markdown_bytes(_result())
        assert b"# " in data
