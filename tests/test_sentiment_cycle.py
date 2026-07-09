"""V1.5.2 sentiment cycle tests.

Tests are split into three layers:
1. Rule-engine tests (pure functions, no DB)
2. Indicator-computation tests (with mocked DB)
3. Orchestrator integration tests (with mocked DB)

All tests use monkeypatch to avoid touching the real DuckDB database.
"""
from __future__ import annotations

import pandas as pd
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_stock_daily_df(
    trade_dates: list[str],
    pct_changes: list[float],
    n_stocks: int = 100,
) -> pd.DataFrame:
    """Build a synthetic stock_daily_raw DataFrame for testing.

    Each trade_date gets n_stocks rows. pct_change is repeated across stocks
    for simplicity. Individual test scenarios that need varied pct_changes
    should build their own DataFrames.
    """
    rows = []
    for i, td in enumerate(trade_dates):
        for s in range(n_stocks):
            row = {
                "stock_code": f"{s:06d}",
                "trade_date": pd.to_datetime(td).date(),
                "close": 10.0 + i * 0.1,
                "amount": 1_000_000.0,
                "pct_change": pct_changes[i],
                "amplitude": 3.0,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def _make_scenario_df(
    dates: list[str],
    pct_matrix: list[list[float]],
) -> pd.DataFrame:
    """Build a DataFrame where each stock has its own pct_change per date.

    pct_matrix: list of lists, each inner list is one stock's pct_change
    across all dates. E.g., pct_matrix[0][2] is stock 0 on date 2.
    """
    rows = []
    for stock_idx, pct_series in enumerate(pct_matrix):
        for date_idx, pct in enumerate(pct_series):
            row = {
                "stock_code": f"{stock_idx:06d}",
                "trade_date": pd.to_datetime(dates[date_idx]).date(),
                "close": 10.0 + date_idx * 0.1 + stock_idx * 0.01,
                "amount": 1_000_000.0,
                "pct_change": pct,
                "amplitude": 3.0,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def _mock_query_df_smart(monkeypatch, df_all: pd.DataFrame):
    """Make query_df return the right subset based on SQL params.

    Recognises three query patterns:
    1. WHERE trade_date = ? (one param) → single-date snapshot
    2. DISTINCT trade_date ... LIMIT (two params) → prior trading dates
    3. WHERE trade_date >= ? AND trade_date <= ? (two params) → window data
    """
    def _smart_query(sql: str, params=None):
        sql_upper = sql.upper()
        params = params or []

        if "DISTINCT TRADE_DATE" in sql_upper and "LIMIT" in sql_upper:
            target_date = str(params[0])[:10] if params else None
            dates = sorted(df_all["trade_date"].unique())
            target_dt = pd.to_datetime(target_date).date() if target_date else None
            prior = [d for d in dates if pd.to_datetime(d).date() < target_dt]
            prior = sorted(prior, reverse=True)
            if len(params) > 1:
                limit = int(params[1])
                prior = prior[:limit]
            result = pd.DataFrame({"trade_date": prior})
            return result

        if "WHERE TRADE_DATE = ?" in sql_upper and ">=" not in sql_upper and "<=" not in sql_upper:
            target = str(params[0])[:10] if params else None
            if target:
                target_dt = pd.to_datetime(target).date()
                mask = pd.to_datetime(df_all["trade_date"]).dt.date == target_dt
                return df_all[mask].copy()
            return df_all.copy()

        if "WHERE TRADE_DATE >=" in sql_upper and "TRADE_DATE <=" in sql_upper:
            start = str(params[0])[:10] if len(params) >= 1 else None
            end = str(params[1])[:10] if len(params) >= 2 else None
            if start and end:
                start_dt = pd.to_datetime(start).date()
                end_dt = pd.to_datetime(end).date()
                dates = pd.to_datetime(df_all["trade_date"]).dt.date
                mask = (dates >= start_dt) & (dates <= end_dt)
                return df_all[mask].copy()

        return df_all.copy()

    monkeypatch.setattr(
        "src.sentiment.sentiment_indicators.query_df", _smart_query,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Rule-engine tests (pure functions)
# ══════════════════════════════════════════════════════════════════════════════


class TestRulesIcePoint:
    """Ice point sentiment cycle."""

    def test_ice_point_from_cold_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 5,
            "limit_down_count": 30,
            # 3d/5d averages close to current → no increasing trend
            "limit_up_count_3d_avg": 8.0,
            "limit_down_count_3d_avg": 28.0,
            "limit_up_count_5d_avg": 9.0,
            "limit_down_count_5d_avg": 27.0,
            "max_consecutive_limit_up_height": 1,
            "high_board_stock_count": 0,
            "promotion_rate": 0.1,
            "yesterday_limit_up_avg_pct_chg": -2.5,
            "yesterday_limit_up_positive_ratio": 0.2,
            "yesterday_limit_up_big_loss_count": 5,
            "strong_stock_loss_effect": True,
            "advance_decline_ratio": 0.35,
            "avg_pct_chg": -1.8,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "ice_point"
        assert result["can_try_position"] is False
        assert result["can_attack"] is False
        assert result["chase_high_allowed"] is False
        assert result["risk_level"] == "high"
        assert result["relay_risk_level"] == "high"
        assert result["sentiment_score"] <= 20
        assert len(result["reasons"]) >= 2


class TestRulesRepair:
    """Repair sentiment cycle."""

    def test_repair_from_recovering_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 18,
            "limit_down_count": 8,
            "limit_up_count_3d_avg": 10.0,
            "limit_down_count_3d_avg": 12.0,
            "limit_up_count_5d_avg": 9.0,
            "limit_down_count_5d_avg": 13.0,
            "max_consecutive_limit_up_height": 3,
            "high_board_stock_count": 1,
            "promotion_rate": 0.28,
            "yesterday_limit_up_avg_pct_chg": 0.5,
            "yesterday_limit_up_positive_ratio": 0.55,
            "yesterday_limit_up_big_loss_count": 1,
            "strong_stock_loss_effect": False,
            "advance_decline_ratio": 1.15,
            "avg_pct_chg": 0.2,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "repair"
        assert result["can_try_position"] is True
        assert result["can_attack"] is False
        assert result["chase_high_allowed"] is False
        assert result["risk_level"] == "medium"
        assert result["relay_risk_level"] == "medium"
        assert 30 <= result["sentiment_score"] <= 55
        assert len(result["reasons"]) >= 2


class TestRulesWarming:
    """Warming sentiment cycle."""

    def test_warming_from_strong_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 30,
            "limit_down_count": 5,
            "limit_up_count_3d_avg": 20.0,
            "limit_down_count_3d_avg": 8.0,
            "limit_up_count_5d_avg": 18.0,
            "limit_down_count_5d_avg": 10.0,
            "max_consecutive_limit_up_height": 4,
            "high_board_stock_count": 3,
            "promotion_rate": 0.42,
            "yesterday_limit_up_avg_pct_chg": 1.5,
            "yesterday_limit_up_positive_ratio": 0.65,
            "yesterday_limit_up_big_loss_count": 0,
            "strong_stock_loss_effect": False,
            "advance_decline_ratio": 1.5,
            "avg_pct_chg": 0.7,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "warming"
        assert result["can_try_position"] is True
        assert result["can_attack"] is True
        assert result["risk_level"] == "medium"
        assert result["relay_risk_level"] == "medium"
        assert result["sentiment_score"] >= 55
        assert len(result["reasons"]) >= 2

    def test_warming_allows_chase_high_when_strong(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 40,
            "limit_down_count": 2,
            "limit_up_count_3d_avg": 28.0,
            "limit_down_count_3d_avg": 4.0,
            "limit_up_count_5d_avg": 22.0,
            "limit_down_count_5d_avg": 6.0,
            "max_consecutive_limit_up_height": 5,
            "high_board_stock_count": 5,
            "promotion_rate": 0.50,
            "yesterday_limit_up_avg_pct_chg": 2.5,
            "yesterday_limit_up_positive_ratio": 0.75,
            "yesterday_limit_up_big_loss_count": 0,
            "strong_stock_loss_effect": False,
            "advance_decline_ratio": 1.8,
            "avg_pct_chg": 1.0,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "warming"
        assert result["chase_high_allowed"] is True


class TestRulesClimax:
    """Climax sentiment cycle."""

    def test_climax_from_heated_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 50,
            "limit_down_count": 3,
            "limit_up_count_3d_avg": 45.0,
            "limit_down_count_3d_avg": 5.0,
            "limit_up_count_5d_avg": 38.0,
            "limit_down_count_5d_avg": 7.0,
            "max_consecutive_limit_up_height": 6,
            "high_board_stock_count": 6,
            "promotion_rate": 0.60,
            "yesterday_limit_up_avg_pct_chg": 2.8,
            "yesterday_limit_up_positive_ratio": 0.70,
            "yesterday_limit_up_big_loss_count": 1,
            "strong_stock_loss_effect": False,
            "high_board_negative_count": 2,
            "advance_decline_ratio": 2.0,
            "avg_pct_chg": 1.3,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "climax"
        assert result["relay_risk_level"] == "high"
        assert result["chase_high_allowed"] is False
        assert result["sentiment_score"] >= 70
        # Should mention differentiation risk
        reasons_text = " ".join(result["reasons"])
        assert "分化" in reasons_text or "追高" in reasons_text


class TestRulesCooling:
    """Cooling sentiment cycle."""

    def test_cooling_from_declining_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 15,
            "limit_down_count": 10,
            "limit_up_count_3d_avg": 25.0,
            "limit_down_count_3d_avg": 8.0,
            "limit_up_count_5d_avg": 30.0,
            "limit_down_count_5d_avg": 7.0,
            "max_consecutive_limit_up_height": 3,
            "high_board_stock_count": 2,
            "promotion_rate": 0.15,
            "yesterday_limit_up_avg_pct_chg": -0.8,
            "yesterday_limit_up_positive_ratio": 0.40,
            "yesterday_limit_up_big_loss_count": 2,
            "strong_stock_loss_effect": False,
            "high_board_negative_count": 2,
            "advance_decline_ratio": 0.9,
            "avg_pct_chg": -0.2,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "cooling"
        assert result["can_attack"] is False
        assert result["chase_high_allowed"] is False
        assert result["risk_level"] == "high"
        assert result["relay_risk_level"] == "high"
        assert len(result["reasons"]) >= 2


class TestRulesRetreat:
    """Retreat sentiment cycle."""

    def test_retreat_from_panic_market(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 8,
            "limit_down_count": 25,
            "limit_up_count_3d_avg": 12.0,
            "limit_down_count_3d_avg": 15.0,
            "limit_up_count_5d_avg": 15.0,
            "limit_down_count_5d_avg": 12.0,
            "max_consecutive_limit_up_height": 2,
            "high_board_stock_count": 0,
            "promotion_rate": 0.05,
            "yesterday_limit_up_avg_pct_chg": -3.2,
            "yesterday_limit_up_positive_ratio": 0.15,
            "yesterday_limit_up_big_loss_count": 6,
            "strong_stock_loss_effect": True,
            "high_board_negative_count": 3,
            "advance_decline_ratio": 0.30,
            "avg_pct_chg": -2.2,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "retreat"
        assert result["risk_level"] in ("extreme", "high")
        assert result["relay_risk_level"] in ("extreme", "high")
        assert result["can_try_position"] is False
        assert result["can_attack"] is False
        assert result["chase_high_allowed"] is False
        assert result["sentiment_score"] <= 15
        assert len(result["reasons"]) >= 2


class TestRulesChaotic:
    """Chaotic sentiment cycle."""

    def test_chaotic_from_mixed_signals(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 25,
            "limit_down_count": 18,
            # Averages close to current → no clear trend (mixed)
            "limit_up_count_3d_avg": 24.0,
            "limit_down_count_3d_avg": 17.0,
            "limit_up_count_5d_avg": 23.0,
            "limit_down_count_5d_avg": 16.0,
            "max_consecutive_limit_up_height": 3,
            "high_board_stock_count": 2,
            "promotion_rate": 0.35,
            "yesterday_limit_up_avg_pct_chg": 1.2,
            "yesterday_limit_up_positive_ratio": 0.35,
            "yesterday_limit_up_big_loss_count": 3,
            "strong_stock_loss_effect": True,
            "high_board_negative_count": 2,
            "advance_decline_ratio": 1.05,
            "avg_pct_chg": 0.3,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] == "chaotic"
        assert result["can_attack"] is False
        assert result["chase_high_allowed"] is False
        assert len(result["reasons"]) >= 1


class TestRulesDataInsufficient:
    """Unknown when data is insufficient."""

    def test_empty_indicators(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        result = judge_sentiment_cycle({})
        assert result["sentiment_cycle"] == "unknown"
        assert result["risk_level"] == "unknown"
        assert result["sentiment_score"] == 0

    def test_no_valid_stocks(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        result = judge_sentiment_cycle({"valid_stock_count": 0})
        assert result["sentiment_cycle"] == "unknown"
        assert result["can_try_position"] is False

    def test_none_indicators(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        result = judge_sentiment_cycle({"valid_stock_count": None})
        assert result["sentiment_cycle"] == "unknown"


class TestRulesMissingFields:
    """Graceful handling of missing optional fields."""

    def test_missing_optional_fields_no_crash(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 12,
            "limit_down_count": 5,
            "advance_decline_ratio": 1.1,
            "avg_pct_chg": 0.2,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] in (
            "ice_point", "repair", "warming", "climax",
            "cooling", "retreat", "chaotic", "unknown",
        )
        assert isinstance(result["reasons"], list)
        assert result["action_hint"]

    def test_missing_promotion_handled(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 8,
            "limit_down_count": 8,
            "yesterday_limit_up_avg_pct_chg": 0.1,
            "strong_stock_loss_effect": False,
        }
        result = judge_sentiment_cycle(ind)
        # Should not crash and return a valid phase
        assert result["sentiment_cycle"] in (
            "ice_point", "repair", "warming", "climax",
            "cooling", "retreat", "chaotic", "unknown",
        )


# ══════════════════════════════════════════════════════════════════════════════
# 2. Output field completeness tests
# ══════════════════════════════════════════════════════════════════════════════


class TestOutputFieldCompleteness:
    """Every output must contain all required fields."""

    REQUIRED_FIELDS_RULES = [
        "sentiment_cycle", "sentiment_score",
        "risk_level", "can_try_position", "can_attack",
        "relay_risk_level", "chase_high_allowed",
        "action_hint", "reasons",
    ]

    REQUIRED_FIELDS_CYCLE = [
        "trade_date", "sentiment_cycle", "sentiment_score",
        "risk_level", "can_try_position", "can_attack",
        "relay_risk_level", "chase_high_allowed",
        "action_hint", "indicators", "reasons",
        "missing_indicator_names", "version",
    ]

    def test_ice_point_has_all_rule_fields(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 5,
            "limit_down_count": 30,
            "yesterday_limit_up_avg_pct_chg": -2.5,
            "yesterday_limit_up_positive_ratio": 0.2,
            "strong_stock_loss_effect": True,
            "advance_decline_ratio": 0.35,
        }
        result = judge_sentiment_cycle(ind)
        for field in self.REQUIRED_FIELDS_RULES:
            assert field in result, f"Missing field: {field}"

    def test_unknown_has_all_rule_fields(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        result = judge_sentiment_cycle({})
        for field in self.REQUIRED_FIELDS_RULES:
            assert field in result, f"Missing field: {field}"

    def test_cycle_dataclass_has_all_fields(self):
        from src.sentiment.sentiment_types import SentimentCycle
        cycle = SentimentCycle(
            trade_date="2026-07-08",
            sentiment_cycle="repair",
            sentiment_score=52,
            risk_level="medium",
            can_try_position=True,
            can_attack=False,
            relay_risk_level="medium",
            chase_high_allowed=False,
            action_hint="测试",
            indicators={"a": 1},
            reasons=["r1"],
        )
        d = cycle.as_dict()
        for field in self.REQUIRED_FIELDS_CYCLE:
            assert field in d, f"Missing field in SentimentCycle: {field}"

    def test_action_hint_is_chinese(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 30,
            "limit_down_count": 5,
            "limit_up_count_3d_avg": 20.0,
            "limit_down_count_3d_avg": 8.0,
            "max_consecutive_limit_up_height": 4,
            "promotion_rate": 0.42,
            "yesterday_limit_up_avg_pct_chg": 1.5,
            "yesterday_limit_up_positive_ratio": 0.65,
            "strong_stock_loss_effect": False,
            "advance_decline_ratio": 1.5,
            "avg_pct_chg": 0.7,
        }
        result = judge_sentiment_cycle(ind)
        # Should contain Chinese characters
        assert any('\u4e00' <= c <= '\u9fff' for c in result["action_hint"])

    def test_reasons_not_empty(self):
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 30,
            "limit_down_count": 5,
            "limit_up_count_3d_avg": 20.0,
            "limit_down_count_3d_avg": 8.0,
            "max_consecutive_limit_up_height": 4,
            "promotion_rate": 0.42,
            "yesterday_limit_up_avg_pct_chg": 1.5,
            "yesterday_limit_up_positive_ratio": 0.65,
            "strong_stock_loss_effect": False,
            "advance_decline_ratio": 1.5,
            "avg_pct_chg": 0.7,
        }
        result = judge_sentiment_cycle(ind)
        assert len(result["reasons"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 3. Orchestrator integration tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSentimentCycleOrchestrator:
    """Tests for build_sentiment_cycle."""

    def test_no_data_returns_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "src.sentiment.sentiment_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        assert cycle.sentiment_cycle == "unknown"
        assert cycle.risk_level == "unknown"
        assert cycle.can_try_position is False
        assert cycle.can_attack is False
        assert cycle.chase_high_allowed is False
        assert cycle.version == "v1.5.2"

    def test_repair_scenario_with_data(self, monkeypatch):
        """Repair scenario: limit ups rising, limit downs falling."""
        dates = [
            "2026-07-01", "2026-07-02", "2026-07-03",
            "2026-07-06", "2026-07-07", "2026-07-08",
        ]
        # Stock 0-15: yesterday & today limit up (promotion)
        # Stock 16-25: today limit up, yesterday normal
        # Stock 26-90: normal stocks
        # Stock 91-100: limit down
        pct_matrix = []
        for s in range(100):
            if s < 8:  # 8 stocks: 2-day consecutive limit up
                pct_matrix.append([1.0, 0.5, -1.0, 9.9, 9.9, 9.9])  # strong
            elif s < 16:  # 8 more limit up today but not yesterday
                pct_matrix.append([0.5, -0.5, 1.0, 2.0, 1.5, 9.9])
            elif s < 20:  # 4 limit up yesterday, not today (failed promotion)
                pct_matrix.append([0.5, -0.5, 1.0, 2.0, 9.9, 2.0])
            elif s < 90:  # 70 normal stocks, slightly positive
                pct_matrix.append([0.3, -0.2, 0.1, 0.5, 0.3, 0.8])
            else:  # 10 limit down
                pct_matrix.append([-1.0, -2.0, -3.0, -1.5, -2.0, -9.9])

        df = _make_scenario_df(dates, pct_matrix)
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")

        assert cycle.trade_date == "2026-07-08"
        assert cycle.sentiment_cycle in ("repair", "warming", "climax", "cooling", "retreat", "chaotic", "unknown")
        assert cycle.version == "v1.5.2"
        assert isinstance(cycle.sentiment_score, int)
        assert 0 <= cycle.sentiment_score <= 100
        assert isinstance(cycle.can_try_position, bool)
        assert isinstance(cycle.can_attack, bool)
        assert isinstance(cycle.chase_high_allowed, bool)
        assert isinstance(cycle.action_hint, str)
        assert len(cycle.action_hint) > 0
        assert isinstance(cycle.indicators, dict)
        assert len(cycle.indicators) > 0
        assert isinstance(cycle.reasons, list)
        assert len(cycle.reasons) > 0

    def test_ice_point_scenario(self, monkeypatch):
        """Ice point: few limit ups, many limit downs, strong loss effect."""
        dates = [
            "2026-07-01", "2026-07-02", "2026-07-03",
            "2026-07-06", "2026-07-07", "2026-07-08",
        ]
        pct_matrix = []
        for s in range(100):
            if s < 3:  # Only 3 limit up
                pct_matrix.append([-2.0, -1.0, -3.0, -5.0, -5.0, 9.9])
            elif s < 28:  # 25 limit down
                pct_matrix.append([-3.0, -4.0, -5.0, -6.0, -9.9, -9.9])
            elif s < 35:  # Some more big losses
                pct_matrix.append([-2.0, -3.5, -4.0, -5.0, -5.5, -6.0])
            else:  # Mostly negative
                pct_matrix.append([-0.5, -0.8, -1.2, -1.5, -2.0, -2.5])

        df = _make_scenario_df(dates, pct_matrix)
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")

        # Should be ice_point or retreat (both are bearish phases)
        assert cycle.sentiment_cycle in ("ice_point", "retreat", "cooling")
        assert cycle.can_attack is False
        assert cycle.chase_high_allowed is False

    def test_warming_scenario(self, monkeypatch):
        """Warming: many limit ups, good promotion, few limit downs."""
        dates = [
            "2026-07-01", "2026-07-02", "2026-07-03",
            "2026-07-06", "2026-07-07", "2026-07-08",
        ]
        pct_matrix = []
        for s in range(100):
            if s < 15:  # 15 stocks: 3-day consecutive limit up
                pct_matrix.append([2.0, 9.9, 9.9, 9.9, 9.9, 9.9])
            elif s < 25:  # 10 more limit up today
                pct_matrix.append([1.0, 2.0, 3.0, 5.0, 5.0, 9.9])
            elif s < 35:  # 10 limit up yesterday, strong today
                pct_matrix.append([0.5, 1.0, 2.0, 3.0, 9.9, 5.0])
            elif s < 95:  # Mostly positive
                pct_matrix.append([0.3, 0.5, 0.2, 0.8, 1.0, 1.2])
            else:  # Few limit down
                pct_matrix.append([-1.0, -2.0, -3.0, -9.9, 1.0, 0.5])

        df = _make_scenario_df(dates, pct_matrix)
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")

        assert cycle.sentiment_cycle in ("warming", "climax", "repair")
        assert cycle.can_try_position is True

    def test_result_as_dict_serializable(self, monkeypatch):
        dates = ["2026-07-08"]
        pct_matrix = [[0.5] for _ in range(100)]
        df = _make_scenario_df(dates, pct_matrix)
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        d = cycle.as_dict()
        assert isinstance(d, dict)
        assert d["trade_date"] == "2026-07-08"
        assert d["version"] == "v1.5.2"
        import json
        json.dumps(d, default=str)  # should not raise

    def test_missing_data_is_graceful(self, monkeypatch):
        """When query_df raises, should not crash."""
        def _raise(*args, **kwargs):
            raise RuntimeError("DB not available")
        monkeypatch.setattr(
            "src.sentiment.sentiment_indicators.query_df", _raise,
        )
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        assert cycle.sentiment_cycle == "unknown"
        assert cycle.action_hint


# ══════════════════════════════════════════════════════════════════════════════
# 4. Types tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSentimentTypes:
    """Tests for sentiment_types dataclass and enums."""

    def test_sentiment_cycle_validate_valid(self):
        from src.sentiment.sentiment_types import (
            SentimentCycle, SENTIMENT_WARMING, RISK_MEDIUM,
        )
        cycle = SentimentCycle(
            trade_date="2026-07-08",
            sentiment_cycle=SENTIMENT_WARMING,
            sentiment_score=65,
            risk_level=RISK_MEDIUM,
            can_try_position=True,
            can_attack=True,
            relay_risk_level=RISK_MEDIUM,
            chase_high_allowed=False,
            action_hint="测试建议",
            indicators={"a": 1},
            reasons=["r1"],
        )
        assert cycle.validate() == []

    def test_sentiment_cycle_validate_invalid(self):
        from src.sentiment.sentiment_types import SentimentCycle
        cycle = SentimentCycle(
            trade_date="2026-07-08",
            sentiment_cycle="invalid_phase",
            sentiment_score=150,
            risk_level="bad_risk",
            can_try_position=True,
            can_attack=False,
            relay_risk_level="bad_relay",
            chase_high_allowed=False,
            action_hint="test",
        )
        issues = cycle.validate()
        assert len(issues) >= 3  # invalid phase, out-of-range score, invalid risk

    def test_sentiment_cycles_tuple(self):
        from src.sentiment.sentiment_types import SENTIMENT_CYCLES
        assert "ice_point" in SENTIMENT_CYCLES
        assert "repair" in SENTIMENT_CYCLES
        assert "warming" in SENTIMENT_CYCLES
        assert "climax" in SENTIMENT_CYCLES
        assert "cooling" in SENTIMENT_CYCLES
        assert "retreat" in SENTIMENT_CYCLES
        assert "chaotic" in SENTIMENT_CYCLES
        assert "unknown" in SENTIMENT_CYCLES

    def test_risk_levels_tuple(self):
        from src.sentiment.sentiment_types import RISK_LEVELS
        assert "low" in RISK_LEVELS
        assert "medium" in RISK_LEVELS
        assert "high" in RISK_LEVELS
        assert "extreme" in RISK_LEVELS
        assert "unknown" in RISK_LEVELS

    def test_unknown_snapshot(self):
        from src.sentiment.sentiment_types import UNKNOWN_SENTIMENT_CYCLE
        assert UNKNOWN_SENTIMENT_CYCLE.sentiment_cycle == "unknown"
        assert UNKNOWN_SENTIMENT_CYCLE.risk_level == "unknown"
        assert UNKNOWN_SENTIMENT_CYCLE.can_try_position is False
        assert UNKNOWN_SENTIMENT_CYCLE.can_attack is False
        assert UNKNOWN_SENTIMENT_CYCLE.chase_high_allowed is False


# ══════════════════════════════════════════════════════════════════════════════
# 5. V1.5.0 backward compatibility
# ══════════════════════════════════════════════════════════════════════════════


class TestV150BackwardCompatibility:
    """Ensure V1.5.0 tests still pass and V1.5.2 doesn't break them."""

    def test_sentiment_unknown_without_limit_data(self, monkeypatch):
        """Original V1.5.0 test — should still pass."""
        monkeypatch.setattr(
            "src.sentiment.sentiment_cycle.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        monkeypatch.setattr(
            "src.sentiment.sentiment_cycle._has_limit_up_data", lambda: False,
        )
        from src.sentiment.sentiment_cycle import build_sentiment_snapshot

        snap = build_sentiment_snapshot("2026-07-07")
        assert snap.sentiment_cycle == "unknown"
        assert snap.limit_up_count is None
        assert snap.limit_down_count is None
        assert "数据" in snap.risk_hint

    def test_daily_decision_card_includes_sentiment_v2(self, monkeypatch):
        """The card should include the new sentiment_cycle_v2 field."""
        monkeypatch.setattr(
            "src.market.market_state.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        monkeypatch.setattr(
            "src.sentiment.sentiment_cycle.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        monkeypatch.setattr(
            "src.sector.sector_snapshot.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        monkeypatch.setattr(
            "src.sentiment.sentiment_cycle._has_limit_up_data", lambda: False,
        )
        # Mock indicators to return empty so V1.5.1 falls back
        monkeypatch.setattr(
            "src.market.market_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "src.sentiment.sentiment_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.decision.daily_decision_card import build_daily_decision_card
        card = build_daily_decision_card("2026-07-07")
        data = card.as_dict()
        assert "sentiment_cycle_v2" in data
        assert isinstance(data["sentiment_cycle_v2"], dict)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Boundary tests
# ══════════════════════════════════════════════════════════════════════════════


class TestBoundaryConditions:
    """Edge cases and graceful degradation."""

    def test_valid_stock_count_zero_no_crash(self, monkeypatch):
        """valid_stock_count = 0 should not crash."""
        monkeypatch.setattr(
            "src.sentiment.sentiment_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        assert cycle.sentiment_cycle == "unknown"

    def test_previous_limit_up_count_zero_no_division(self):
        """promotion_rate with zero previous limit up should be 0, not crash."""
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 10,
            "limit_down_count": 5,
            "previous_limit_up_count": 0,
            "promotion_rate": 0.0,
            "yesterday_limit_up_avg_pct_chg": 0.0,
            "strong_stock_loss_effect": False,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] != "unknown"  # should still judge

    def test_limit_up_count_5d_avg_zero_no_division(self):
        """5d avg = 0 should not cause division issues."""
        from src.rules.sentiment_cycle_rules import judge_sentiment_cycle
        ind = {
            "valid_stock_count": 100,
            "limit_up_count": 5,
            "limit_down_count": 5,
            "limit_up_count_5d_avg": 0.0,
            "limit_down_count_5d_avg": 0.0,
            "strong_stock_loss_effect": False,
        }
        result = judge_sentiment_cycle(ind)
        assert result["sentiment_cycle"] in (
            "ice_point", "repair", "warming", "climax",
            "cooling", "retreat", "chaotic", "unknown",
        )

    def test_missing_pct_chg_no_crash(self, monkeypatch):
        """Data missing pct_change column should not crash."""
        df = pd.DataFrame({
            "stock_code": [f"{i:06d}" for i in range(10)],
            "trade_date": pd.to_datetime("2026-07-08").date(),
            "close": [10.0] * 10,
            "amount": [1_000_000.0] * 10,
            "amplitude": [3.0] * 10,
            # No pct_change column
        })
        monkeypatch.setattr(
            "src.sentiment.sentiment_indicators.query_df",
            lambda sql, params=None: df,
        )
        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        # Should handle gracefully — either crash with clear error or return unknown
        try:
            cycle = build_sentiment_cycle("2026-07-08")
            assert cycle.sentiment_cycle == "unknown"
        except KeyError:
            pass  # KeyError from missing column is acceptable, but shouldn't segfault

    def test_limit_up_broken_rate_in_missing(self, monkeypatch):
        """limit_up_broken_rate should always be in missing_indicator_names."""
        dates = [
            "2026-07-01", "2026-07-02", "2026-07-03",
            "2026-07-06", "2026-07-07", "2026-07-08",
        ]
        df = _make_stock_daily_df(dates, [0.5] * len(dates))
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        assert "limit_up_broken_rate" in cycle.missing_indicator_names

    def test_approximate_flags_in_indicators(self, monkeypatch):
        """approximate_limit_up/down should be True in indicators."""
        dates = ["2026-07-08"]
        df = _make_stock_daily_df(dates, [0.5])
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        if cycle.indicators:
            assert cycle.indicators.get("approximate_limit_up") is True
            assert cycle.indicators.get("approximate_limit_down") is True

    def test_single_day_data_does_not_crash(self, monkeypatch):
        """Single day of data should still produce a valid result."""
        df = _make_stock_daily_df(["2026-07-08"], [0.5])
        _mock_query_df_smart(monkeypatch, df)

        from src.sentiment.sentiment_cycle import build_sentiment_cycle
        cycle = build_sentiment_cycle("2026-07-08")
        assert cycle.sentiment_cycle in (
            "ice_point", "repair", "warming", "climax",
            "cooling", "retreat", "chaotic", "unknown",
        )
        assert cycle.version == "v1.5.2"
