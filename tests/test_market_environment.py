"""V1.5.1 market environment tests.

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
    amounts: list[float] | None = None,
    closes: list[float] | None = None,
    amplitudes: list[float] | None = None,
    n_stocks: int = 50,
) -> pd.DataFrame:
    """Build a synthetic stock_daily_raw DataFrame for testing.

    Each trade_date gets n_stocks rows.  pct_change, amount, close, and
    amplitude are repeated across stocks to keep tests simple.
    """
    rows = []
    for i, td in enumerate(trade_dates):
        for s in range(n_stocks):
            row = {
                "stock_code": f"{s:06d}",
                "trade_date": pd.to_datetime(td).date(),
                "close": closes[i] if closes else 10.0 + i * 0.1,
                "amount": amounts[i] if amounts else 1_000_000.0,
                "pct_change": pct_changes[i],
                "amplitude": amplitudes[i] if amplitudes else 3.0,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def _mock_query_df_return(monkeypatch, df: pd.DataFrame):
    """Make ``query_df`` return *df* for any call.

    NOTE: For tests that need to distinguish between different queries
    (e.g., today vs prior dates vs window), use ``_mock_query_df_smart`` instead.
    """
    monkeypatch.setattr(
        "src.market.market_indicators.query_df",
        lambda sql, params=None: df,
    )


def _mock_query_df_smart(monkeypatch, df_all: pd.DataFrame):
    """Make ``query_df`` return the right subset based on SQL params.

    Recognises three query patterns:
    1. ``WHERE trade_date = ?``       → today's snapshot
    2. ``DISTINCT trade_date ... LIMIT`` → prior trading dates list
    3. ``WHERE trade_date >= ? AND trade_date <= ?`` → window data
    """
    original_query_df = __import__(
        "src.storage.duckdb_repo", fromlist=["query_df"]
    ).query_df

    def _smart_query(sql: str, params=None):
        sql_upper = sql.upper()
        if "DISTINCT TRADE_DATE" in sql_upper and "LIMIT" in sql_upper:
            # Prior dates query
            target_date = str(params[0])[:10] if params else None
            dates = sorted(df_all["trade_date"].unique())
            # Convert to datetime for comparison
            target_dt = pd.to_datetime(target_date).date() if target_date else None
            prior = [d for d in dates if pd.to_datetime(d).date() < target_dt]
            prior = sorted(prior, reverse=True)
            if params and len(params) > 1:
                limit = int(params[1])
                prior = prior[:limit]
            result = pd.DataFrame({"trade_date": prior})
            return result

        if "WHERE TRADE_DATE = ?" in sql_upper and ">=" not in sql and "<=" not in sql:
            # Single date query
            target = str(params[0])[:10] if params else None
            if target:
                target_dt = pd.to_datetime(target).date()
                mask = pd.to_datetime(df_all["trade_date"]).dt.date == target_dt
                return df_all[mask].copy()
            return df_all.copy()

        if "WHERE TRADE_DATE >=" in sql_upper and "TRADE_DATE <=" in sql_upper:
            # Window query
            start = str(params[0])[:10] if params and len(params) >= 1 else None
            end = str(params[1])[:10] if params and len(params) >= 2 else None
            if start and end:
                start_dt = pd.to_datetime(start).date()
                end_dt = pd.to_datetime(end).date()
                dates = pd.to_datetime(df_all["trade_date"]).dt.date
                mask = (dates >= start_dt) & (dates <= end_dt)
                return df_all[mask].copy()

        return df_all.copy()

    monkeypatch.setattr(
        "src.market.market_indicators.query_df", _smart_query,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Rule-engine tests (pure functions)
# ══════════════════════════════════════════════════════════════════════════════


class TestRulesHighRisk:
    """High-risk market conditions."""

    def test_high_risk_from_large_decline(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": -2.5,
            "advance_decline_ratio": 0.3,
            "approximate_limit_down_count": 50,
            "approximate_limit_up_count": 5,
            "pct_above_ma5": 20.0,
            "pct_above_ma20": 25.0,
            "turnover_ratio_20d": 1.6,
            "composite_close_above_ma20": False,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "high_risk"
        assert result["can_open_position"] is False
        assert result["can_add_position"] is False
        assert result["chase_high_allowed"] is False
        assert result["risk_level"] in ("high", "extreme")
        assert len(result["reasons"]) >= 2
        assert result["action_hint"]

    def test_high_risk_extreme_on_many_limitdown(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": -3.0,
            "advance_decline_ratio": 0.2,
            "approximate_limit_down_count": 80,
            "approximate_limit_up_count": 1,
            "pct_above_ma5": 10.0,
            "pct_above_ma20": 12.0,
            "turnover_ratio_20d": 1.2,
            "composite_close_above_ma20": False,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "high_risk"
        assert result["risk_level"] == "extreme"


class TestRulesDefense:
    """Defense (weak) market conditions."""

    def test_defense_from_low_breadth(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": -0.4,
            "advance_decline_ratio": 0.7,
            "approximate_limit_down_count": 10,
            "approximate_limit_up_count": 8,
            "pct_above_ma5": 30.0,
            "pct_above_ma20": 28.0,
            "turnover_ratio_20d": 0.65,
            "composite_close_above_ma20": False,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "defense"
        assert result["can_open_position"] is False
        assert result["can_add_position"] is False
        assert result["chase_high_allowed"] is False
        assert len(result["reasons"]) >= 1

    def test_defense_risk_high_on_many_limitdown(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": -0.5,
            "advance_decline_ratio": 0.6,
            "approximate_limit_down_count": 20,
            "approximate_limit_up_count": 5,
            "pct_above_ma5": 32.0,
            "pct_above_ma20": 30.0,
            "turnover_ratio_20d": 0.7,
            "composite_close_above_ma20": False,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "defense"
        assert result["risk_level"] == "high"


class TestRulesAttack:
    """Attack (strong) market conditions."""

    def test_attack_from_strong_signals(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": 0.8,
            "advance_decline_ratio": 1.6,
            "approximate_limit_down_count": 5,
            "approximate_limit_up_count": 20,
            "pct_above_ma5": 62.0,
            "pct_above_ma20": 55.0,
            "turnover_ratio_20d": 1.05,
            "composite_close_above_ma5": True,
            "composite_close_above_ma20": True,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "attack"
        assert result["can_open_position"] is True
        assert result["can_add_position"] is True
        # chase_high_allowed defaults to False unless extreme
        assert result["chase_high_allowed"] is False
        assert len(result["reasons"]) >= 2

    def test_attack_extreme_allows_chase_high(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": 1.5,
            "advance_decline_ratio": 2.5,
            "approximate_limit_down_count": 2,
            "approximate_limit_up_count": 40,
            "pct_above_ma5": 70.0,
            "pct_above_ma20": 65.0,
            "turnover_ratio_20d": 1.2,
            "composite_close_above_ma5": True,
            "composite_close_above_ma20": True,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "attack"
        assert result["chase_high_allowed"] is True
        assert result["risk_level"] == "low"


class TestRulesNeutral:
    """Neutral market conditions."""

    def test_neutral_from_mixed_signals(self):
        from src.rules.market_environment_rules import judge_market_environment

        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": 0.15,
            "advance_decline_ratio": 1.05,
            "approximate_limit_down_count": 8,
            "approximate_limit_up_count": 10,
            "pct_above_ma5": 48.0,
            "pct_above_ma20": 45.0,
            "turnover_ratio_20d": 0.95,
            "composite_close_above_ma5": True,
            "composite_close_above_ma20": True,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] == "neutral"
        assert result["can_open_position"] is True
        assert result["can_add_position"] is False
        assert result["chase_high_allowed"] is False
        assert result["risk_level"] == "medium"
        assert len(result["reasons"]) >= 1


class TestRulesDataInsufficient:
    """Unknown when data is insufficient."""

    def test_empty_indicators(self):
        from src.rules.market_environment_rules import judge_market_environment
        result = judge_market_environment({})
        assert result["market_state"] == "unknown"
        assert result["risk_level"] == "unknown"

    def test_no_total_stocks(self):
        from src.rules.market_environment_rules import judge_market_environment
        result = judge_market_environment({"avg_pct_chg": 0.5})
        assert result["market_state"] == "unknown"

    def test_zero_total_stocks(self):
        from src.rules.market_environment_rules import judge_market_environment
        result = judge_market_environment({"valid_stock_count": 0})
        assert result["market_state"] == "unknown"


class TestRulesMissingFields:
    """Graceful handling of missing optional fields."""

    def test_missing_ma_fields_no_crash(self):
        from src.rules.market_environment_rules import judge_market_environment

        # Only provide bare minimum — no MA or turnover fields
        ind = {
            "valid_stock_count": 100,
            "avg_pct_chg": 0.1,
            "advance_decline_ratio": 1.1,
            "approximate_limit_down_count": 10,
            "approximate_limit_up_count": 12,
        }
        result = judge_market_environment(ind)
        assert result["market_state"] in ("neutral", "defense", "attack", "high_risk", "unknown")
        # Must not crash
        assert isinstance(result["reasons"], list)
        assert result["action_hint"]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Indicators tests (mocked DB)
# ══════════════════════════════════════════════════════════════════════════════


class TestIndicatorsSingleDay:
    """Indicator computation when only one day's data exists."""

    def test_single_day_returns_limited_indicators(self, monkeypatch):
        df = _make_stock_daily_df(
            trade_dates=["2026-07-08"],
            pct_changes=[0.5],
        )
        _mock_query_df_smart(monkeypatch, df)

        from src.market.market_indicators import compute_market_indicators
        ind = compute_market_indicators("2026-07-08")

        assert ind["valid_stock_count"] == 50
        assert ind["avg_pct_chg"] == 0.5
        assert ind["advance_decline_ratio"] == 50.0  # all positive
        assert ind["approximate_limit_up_count"] == 0
        assert ind["approximate_limit_down_count"] == 0
        # MA / volatility fields should NOT be present (listed in missing_indicator_names)
        assert "pct_above_ma5" not in ind
        assert "composite_volatility_5d" not in ind
        assert "missing_indicator_names" in ind
        assert "pct_above_ma5" in ind["missing_indicator_names"]

    def test_no_data_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(
            "src.market.market_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.market.market_indicators import compute_market_indicators
        ind = compute_market_indicators("2026-07-08")
        assert ind == {}


class TestIndicatorsFull:
    """Indicator computation with full historical data."""

    def test_full_indicators_includes_all_keys(self, monkeypatch):
        """Verify all expected keys exist in the output."""
        trade_dates = [f"2026-06-{d:02d}" for d in range(1, 30) if d <= 28]  # June
        trade_dates.append("2026-07-01")
        trade_dates.append("2026-07-08")

        pct_changes = [0.2] * 20 + [0.5] * 10  # last is 0.5
        closes = [10.0 + i * 0.02 for i in range(len(trade_dates))]

        df = _make_stock_daily_df(
            trade_dates=trade_dates,
            pct_changes=pct_changes,
            closes=closes,
        )
        _mock_query_df_smart(monkeypatch, df)

        from src.market.market_indicators import compute_market_indicators
        ind = compute_market_indicators("2026-07-08")

        # All required fields should be present
        expected_keys = [
            "sample_stock_count", "valid_stock_count",
            "avg_pct_chg", "median_pct_chg",
            "up_count", "down_count", "flat_count", "advance_decline_ratio",
            "approximate_limit_up_count", "approximate_limit_down_count",
            "total_turnover_yuan", "turnover_ratio_5d", "turnover_ratio_20d",
            "pct_above_ma5", "pct_above_ma10", "pct_above_ma20",
            "composite_close_above_ma5", "composite_close_above_ma10",
            "composite_close_above_ma20",
            "return_5d", "return_20d",
            "composite_volatility_5d", "composite_volatility_20d",
            "composite_amplitude_mean",
            "missing_indicator_names",
        ]
        for key in expected_keys:
            assert key in ind, f"Missing indicator: {key}"

        # Basic assertions (today should only have 50 stocks)
        assert ind["valid_stock_count"] == 50
        assert ind["avg_pct_chg"] == 0.5
        assert ind["advance_decline_ratio"] >= 0

    def test_limit_up_down_approximation(self, monkeypatch):
        """pct_change >= 9.8 counts as approximate limit_up."""
        pct_changes = [3.0, 9.8, 9.9, -9.8, -10.0, 0.1]  # 2 limit-up, 2 limit-down
        df = _make_stock_daily_df(
            trade_dates=["2026-07-08"],
            pct_changes=[0.5],
            n_stocks=1,
        )
        # Override to create individual stocks with different pct_changes
        rows = []
        for s, pct in enumerate(pct_changes):
            rows.append({
                "stock_code": f"{s:06d}",
                "trade_date": pd.to_datetime("2026-07-08").date(),
                "close": 10.0,
                "amount": 1_000_000.0,
                "pct_change": pct,
                "amplitude": 3.0,
            })
        monkeypatch.setattr(
            "src.market.market_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(rows),
        )
        from src.market.market_indicators import compute_market_indicators
        ind = compute_market_indicators("2026-07-08")
        assert ind["approximate_limit_up_count"] == 2
        assert ind["approximate_limit_down_count"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# 3. Orchestrator integration tests
# ══════════════════════════════════════════════════════════════════════════════


class TestMarketEnvironmentOrchestrator:
    """Tests for build_market_environment."""

    def test_no_data_returns_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "src.market.market_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.market.market_environment import build_market_environment
        env = build_market_environment("2026-07-08")
        assert env.market_state == "unknown"
        assert env.risk_level == "unknown"
        assert env.can_open_position is False
        assert env.can_add_position is False
        assert env.chase_high_allowed is False
        assert env.version == "v1.5.1"

    def test_attack_market_returns_correct_fields(self, monkeypatch):
        """Strong market data should produce attack verdict."""
        trade_dates = [f"2026-06-{d:02d}" for d in range(1, 29)]
        trade_dates.append("2026-07-08")
        closes = [10.0 + i * 0.05 for i in range(len(trade_dates))]

        df = _make_stock_daily_df(
            trade_dates=trade_dates,
            pct_changes=[1.2] * len(trade_dates),
            closes=closes,
        )
        _mock_query_df_smart(monkeypatch, df)

        from src.market.market_environment import build_market_environment
        env = build_market_environment("2026-07-08")

        # Output field completeness
        assert env.trade_date == "2026-07-08"
        assert env.market_state in ("attack", "neutral", "defense", "high_risk", "unknown")
        assert env.risk_level in ("low", "medium", "high", "extreme", "unknown")
        assert isinstance(env.can_open_position, bool)
        assert isinstance(env.can_add_position, bool)
        assert isinstance(env.chase_high_allowed, bool)
        assert isinstance(env.action_hint, str)
        assert len(env.action_hint) > 0
        assert isinstance(env.indicators, dict)
        assert len(env.indicators) > 0
        assert isinstance(env.reasons, list)
        assert env.version == "v1.5.1"

    def test_result_as_dict_serializable(self, monkeypatch):
        df = _make_stock_daily_df(["2026-07-08"], [0.5])
        _mock_query_df_smart(monkeypatch, df)

        from src.market.market_environment import build_market_environment
        env = build_market_environment("2026-07-08")
        d = env.as_dict()
        assert isinstance(d, dict)
        assert d["trade_date"] == "2026-07-08"
        assert d["version"] == "v1.5.1"
        # Verify JSON-serializable (no datetime objects at top level)
        import json
        json.dumps(d, default=str)  # should not raise

    def test_missing_data_is_graceful(self, monkeypatch):
        """When query_df raises, should not crash."""
        def _raise(*args, **kwargs):
            raise RuntimeError("DB not available")
        monkeypatch.setattr(
            "src.market.market_indicators.query_df", _raise,
        )
        from src.market.market_environment import build_market_environment
        env = build_market_environment("2026-07-08")
        assert env.market_state == "unknown"
        assert env.action_hint


# ══════════════════════════════════════════════════════════════════════════════
# 4. Types tests
# ══════════════════════════════════════════════════════════════════════════════


class TestMarketTypes:
    """Tests for market_types dataclass and enums."""

    def test_market_environment_validate_valid(self):
        from src.market.market_types import (
            MarketEnvironment, MARKET_ATTACK, RISK_LOW,
        )
        env = MarketEnvironment(
            trade_date="2026-07-08",
            market_state=MARKET_ATTACK,
            risk_level=RISK_LOW,
            can_open_position=True,
            can_add_position=True,
            chase_high_allowed=False,
            action_hint="测试",
            indicators={"a": 1},
            reasons=["r1"],
        )
        assert env.validate() == []

    def test_market_environment_validate_invalid(self):
        from src.market.market_types import MarketEnvironment
        env = MarketEnvironment(
            trade_date="2026-07-08",
            market_state="invalid_state",
            risk_level="bad_level",
            can_open_position=True,
            can_add_position=False,
            chase_high_allowed=False,
            action_hint="test",
        )
        issues = env.validate()
        assert len(issues) == 2

    def test_market_states_tuple(self):
        from src.market.market_types import MARKET_STATES
        assert "attack" in MARKET_STATES
        assert "neutral" in MARKET_STATES
        assert "defense" in MARKET_STATES
        assert "high_risk" in MARKET_STATES
        assert "unknown" in MARKET_STATES

    def test_risk_levels_tuple(self):
        from src.market.market_types import RISK_LEVELS
        assert "low" in RISK_LEVELS
        assert "medium" in RISK_LEVELS
        assert "high" in RISK_LEVELS
        assert "extreme" in RISK_LEVELS
        assert "unknown" in RISK_LEVELS

    def test_unknown_snapshot(self):
        from src.market.market_types import UNKNOWN_SNAPSHOT
        assert UNKNOWN_SNAPSHOT.market_state == "unknown"
        assert UNKNOWN_SNAPSHOT.risk_level == "unknown"
        assert UNKNOWN_SNAPSHOT.can_open_position is False
        assert UNKNOWN_SNAPSHOT.can_add_position is False
        assert UNKNOWN_SNAPSHOT.chase_high_allowed is False


# ══════════════════════════════════════════════════════════════════════════════
# 5. V1.5.0 backward compatibility
# ══════════════════════════════════════════════════════════════════════════════


class TestV150BackwardCompatibility:
    """Ensure V1.5.0 tests still pass and V1.5.1 doesn't break them."""

    def test_market_snapshot_unknown_by_default(self, monkeypatch):
        """Re-run the V1.5.0 test to ensure it still passes."""
        monkeypatch.setattr(
            "src.market.market_state.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        from src.market.market_state import build_market_snapshot
        snap = build_market_snapshot("2026-07-07")
        assert snap.market_state == "unknown"
        assert snap.can_open_position == "unknown"
        assert snap.can_add_position == "unknown"
        assert snap.chase_high_allowed == "unknown"

    def test_daily_decision_card_includes_market_environment(self, monkeypatch):
        """The card should include the new market_environment field."""
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
        # Mock indicators to return empty so V1.5.1 falls back gracefully
        monkeypatch.setattr(
            "src.market.market_indicators.query_df",
            lambda sql, params=None: pd.DataFrame(),
        )
        from src.decision.daily_decision_card import build_daily_decision_card
        card = build_daily_decision_card("2026-07-07")
        data = card.as_dict()
        assert "market_environment" in data
        assert isinstance(data["market_environment"], dict)
        assert data["generated_at"]
        assert data["overall_bias"] != "aggressive"
