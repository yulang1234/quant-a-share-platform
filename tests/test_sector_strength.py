"""V1.5.4 sector strength tests.

Tests cover:
1. Single sector strength (strong, weak, neutral)
2. Sector ranking
3. Data insufficient
4. Missing turnover fields
5. Missing benchmark index
6. Approximate limit up/down
7. Dry-run / confirm
8. Regression (V1.5.1 / V1.5.2 / V1.5.3 unbroken)
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.sector.sector_strength_types import (
    STRENGTH_VERY_STRONG, STRENGTH_STRONG, STRENGTH_NEUTRAL,
    STRENGTH_WEAK, STRENGTH_VERY_WEAK, STRENGTH_UNKNOWN,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_hist_df(
    dates: list[str],
    stock_pct_map: dict[str, list[float]],
    base_close: float = 10.0,
) -> pd.DataFrame:
    """Build a historical DataFrame for multiple stocks across dates.

    Args:
        dates: list of date strings
        stock_pct_map: {stock_code: [pct_change per date]}
    """
    rows = []
    for code, pcts in stock_pct_map.items():
        close = base_close
        for i, (d, pct) in enumerate(zip(dates, pcts)):
            close = close * (1.0 + pct / 100.0)
            rows.append({
                "stock_code": str(code).zfill(6),
                "trade_date": pd.to_datetime(d).date(),
                "close": round(close, 4),
                "amount": 5_000_000.0 * (1.0 + abs(pct) / 10.0),
                "pct_change": pct,
            })
    return pd.DataFrame(rows)


def _setup_mocks(monkeypatch, sector_info, constituents, hist_df, prior_dates):
    """Mock all external dependencies for sector strength calculation."""
    monkeypatch.setattr(
        "src.sector.sector_strength._get_sector_info",
        lambda sector_code=None, sector_name=None: sector_info,
    )
    monkeypatch.setattr(
        "src.sector.sector_strength._get_constituents",
        lambda sector_code: constituents,
    )
    monkeypatch.setattr(
        "src.sector.sector_strength._fetch_stock_data",
        lambda trade_date, stock_codes: (hist_df, prior_dates),
    )


def _build_dates(base_date: str, n: int) -> list[str]:
    """Generate n consecutive trading-day-style dates."""
    from datetime import datetime, timedelta
    d = datetime.strptime(base_date, "%Y-%m-%d")
    dates = []
    for i in range(n - 1, -1, -1):
        dates.append((d - timedelta(days=i)).strftime("%Y-%m-%d"))
    return dates


# ══════════════════════════════════════════════════════════════════════════════
# 1. Single sector strength — strong
# ══════════════════════════════════════════════════════════════════════════════


class TestSectorStrengthStrong:
    """Strong sector: most stocks up, multi-period positive returns."""

    def test_strong_sector(self, monkeypatch):
        dates = _build_dates("2026-07-09", 25)
        constituents = {"000001": "StockA", "000002": "StockB", "000003": "StockC"}

        # All stocks steadily rising
        pct_map = {
            "000001": [0.5] * 20 + [1.0, 1.2, 1.5, 2.0, 3.0],
            "000002": [0.3] * 20 + [0.8, 1.0, 1.2, 1.8, 2.5],
            "000003": [0.4] * 20 + [0.9, 1.1, 1.3, 2.2, 0.5],
        }
        hist_df = _make_hist_df(dates, pct_map)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK0001", "sector_name": "强势板块",
            "sector_type": "industry", "source": "akshare",
        }, constituents, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK0001")

        assert result.strength_level in (STRENGTH_STRONG, STRENGTH_VERY_STRONG)
        assert result.strength_score >= 65
        assert result.up_ratio > 0.5
        assert len(result.reasons) >= 1
        assert result.version == "v1.5.4"
        assert result.stock_count == 3
        assert result.valid_stock_count == 3


# ══════════════════════════════════════════════════════════════════════════════
# 2. Single sector strength — weak
# ══════════════════════════════════════════════════════════════════════════════


class TestSectorStrengthWeak:
    """Weak sector: most stocks down, multi-period negative returns."""

    def test_weak_sector(self, monkeypatch):
        dates = _build_dates("2026-07-09", 25)
        constituents = {"000001": "StockA", "000002": "StockB", "000003": "StockC"}

        pct_map = {
            "000001": [-0.3] * 20 + [-1.0, -1.5, -2.0, -3.0, -4.0],
            "000002": [-0.2] * 20 + [-0.8, -1.2, -1.8, -2.5, -3.5],
            "000003": [-0.4] * 20 + [-1.2, -1.8, -2.5, -3.2, 0.2],
        }
        hist_df = _make_hist_df(dates, pct_map)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK0002", "sector_name": "弱势板块",
            "sector_type": "industry", "source": "akshare",
        }, constituents, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK0002")

        assert result.strength_level in (STRENGTH_WEAK, STRENGTH_VERY_WEAK)
        assert result.strength_score < 45
        assert result.up_ratio < 0.5
        assert len(result.reasons) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 3. Single sector strength — neutral
# ══════════════════════════════════════════════════════════════════════════════


class TestSectorStrengthNeutral:
    """Neutral sector: mixed signals."""

    def test_neutral_sector(self, monkeypatch):
        dates = _build_dates("2026-07-09", 25)
        constituents = {"000001": "StockA", "000002": "StockB", "000003": "StockC", "000004": "StockD"}

        pct_map = {
            "000001": [0.1] * 20 + [0.2, 0.1, -0.1, 0.3, 0.0],
            "000002": [0.1] * 20 + [-0.1, 0.0, 0.1, -0.2, 0.1],
            "000003": [-0.1] * 20 + [0.0, -0.1, 0.2, 0.0, -0.1],
            "000004": [-0.1] * 20 + [-0.2, 0.0, 0.0, -0.1, 0.0],
        }
        hist_df = _make_hist_df(dates, pct_map)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK0003", "sector_name": "中性板块",
            "sector_type": "industry", "source": "akshare",
        }, constituents, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK0003")

        assert result.strength_level == STRENGTH_NEUTRAL
        assert 30 <= result.strength_score <= 65


# ══════════════════════════════════════════════════════════════════════════════
# 4. Sector ranking
# ══════════════════════════════════════════════════════════════════════════════


class TestSectorRanking:
    """Rank multiple sectors by strength."""

    def test_ranking_top_n(self, monkeypatch):
        """Build 3 sectors, verify strong ranks higher."""
        dates = _build_dates("2026-07-09", 25)

        # Mock list_all_sectors
        sectors_df = pd.DataFrame([
            {"sector_code": "BK_S", "sector_name": "强板块",
             "sector_type": "industry", "source": "akshare"},
            {"sector_code": "BK_N", "sector_name": "中板块",
             "sector_type": "industry", "source": "akshare"},
            {"sector_code": "BK_W", "sector_name": "弱板块",
             "sector_type": "industry", "source": "akshare"},
        ])
        monkeypatch.setattr(
            "src.sector.sector_strength._list_all_sectors",
            lambda sector_type=None: sectors_df,
        )

        # Mock each sector's constituent and data
        def _fake_calc(trade_date, sector_code=None, sector_name=None):
            if sector_code == "BK_S" or sector_name == "强板块":
                from src.sector.sector_strength_types import SectorStrengthResult
                return SectorStrengthResult(
                    trade_date="2026-07-09", sector_code="BK_S",
                    sector_name="强板块", sector_type="industry", source="akshare",
                    strength_score=85, strength_level=STRENGTH_VERY_STRONG,
                    return_5d=6.0, up_ratio=0.85, limit_up_count=5,
                )
            elif sector_code == "BK_N" or sector_name == "中板块":
                from src.sector.sector_strength_types import SectorStrengthResult
                return SectorStrengthResult(
                    trade_date="2026-07-09", sector_code="BK_N",
                    sector_name="中板块", sector_type="industry", source="akshare",
                    strength_score=55, strength_level=STRENGTH_NEUTRAL,
                    return_5d=1.0, up_ratio=0.5, limit_up_count=1,
                )
            else:
                from src.sector.sector_strength_types import SectorStrengthResult
                return SectorStrengthResult(
                    trade_date="2026-07-09", sector_code="BK_W",
                    sector_name="弱板块", sector_type="industry", source="akshare",
                    strength_score=25, strength_level=STRENGTH_VERY_WEAK,
                    return_5d=-4.0, up_ratio=0.2, limit_up_count=0,
                )

        monkeypatch.setattr(
            "src.sector.sector_strength.calculate_sector_strength", _fake_calc,
        )

        from src.sector.sector_strength import get_sector_rank
        ranking = get_sector_rank("2026-07-09", top_n=2)

        assert ranking.top_n == 2
        assert len(ranking.sectors) == 2
        assert ranking.sectors[0]["sector_name"] == "强板块"
        assert ranking.sectors[0]["rank_overall"] == 1
        assert ranking.sectors[1]["rank_overall"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# 5. Data insufficient
# ══════════════════════════════════════════════════════════════════════════════


class TestDataInsufficient:
    """Graceful degradation when data is insufficient."""

    def test_no_constituents(self, monkeypatch):
        _setup_mocks(monkeypatch, {
            "sector_code": "BK_E", "sector_name": "空板块",
            "sector_type": "industry", "source": "akshare",
        }, {}, pd.DataFrame(), [])

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK_E")
        assert result.strength_level == STRENGTH_UNKNOWN
        assert result.stock_count == 0
        assert len(result.missing_indicator_names) >= 1

    def test_no_stock_data(self, monkeypatch):
        _setup_mocks(monkeypatch, {
            "sector_code": "BK_E", "sector_name": "无数据板块",
            "sector_type": "industry", "source": "akshare",
        }, {"000001": "StockA"}, pd.DataFrame(), [])

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK_E")
        assert result.strength_level == STRENGTH_UNKNOWN

    def test_no_sector_info(self, monkeypatch):
        monkeypatch.setattr(
            "src.sector.sector_strength._get_sector_info",
            lambda sector_code=None, sector_name=None: None,
        )
        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="XXX")
        assert result.strength_level == STRENGTH_UNKNOWN
        assert result.stock_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# 6. Missing turnover
# ══════════════════════════════════════════════════════════════════════════════


class TestMissingTurnover:
    """When amount/turnover data is missing."""

    def test_no_amount_column(self, monkeypatch):
        dates = _build_dates("2026-07-09", 10)
        # Build DataFrame without "amount" column
        rows = []
        for code in ["000001", "000002"]:
            close = 10.0
            for d in dates:
                close = close * 1.005
                rows.append({
                    "stock_code": code,
                    "trade_date": pd.to_datetime(d).date(),
                    "close": close,
                    "pct_change": 0.5,
                    # NO amount column
                })
        hist_df = pd.DataFrame(rows)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK_T", "sector_name": "无成交额板块",
            "sector_type": "industry", "source": "akshare",
        }, {"000001": "A", "000002": "B"}, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK_T")
        # Should not crash
        assert result.strength_level != "error"
        assert "turnover_ratio_5d" in result.missing_indicator_names or \
               "turnover_ratio_20d" in result.missing_indicator_names


# ══════════════════════════════════════════════════════════════════════════════
# 7. Missing benchmark
# ══════════════════════════════════════════════════════════════════════════════


class TestMissingBenchmark:
    """When benchmark index is unavailable, use market average."""

    def test_benchmark_uses_market_avg(self, monkeypatch):
        dates = _build_dates("2026-07-09", 25)
        constituents = {"000001": "A", "000002": "B"}

        pct_map = {
            "000001": [0.3] * 20 + [0.5, 0.8, 1.0, 1.5, 2.0],
            "000002": [0.3] * 20 + [0.5, 0.8, 1.0, 1.5, 2.0],
        }
        hist_df = _make_hist_df(dates, pct_map)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK_B", "sector_name": "基准测试板块",
            "sector_type": "industry", "source": "akshare",
        }, constituents, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK_B")
        # Should still compute, using market avg as benchmark
        assert result.strength_level != STRENGTH_UNKNOWN
        # reasons should mention benchmark is approximate
        assert any("benchmark" in r.lower() or "基准" in r for r in result.reasons)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Approximate limit up/down
# ══════════════════════════════════════════════════════════════════════════════


class TestApproximateLimits:
    """Limit up/down approximation."""

    def test_approximate_limit_up_flag(self, monkeypatch):
        dates = _build_dates("2026-07-09", 25)
        constituents = {"000001": "A", "000002": "B", "000003": "C"}

        pct_map = {
            "000001": [0.3] * 20 + [0.5, 1.0, 2.0, 9.9, 9.8],  # today 9.8 → limit up
            "000002": [0.3] * 20 + [0.5, 1.0, 2.0, 3.0, -9.9],  # today -9.9 → limit down
            "000003": [0.3] * 20 + [0.5, 1.0, 2.0, 3.0, 4.0],
        }
        hist_df = _make_hist_df(dates, pct_map)
        prior_dates = [pd.to_datetime(d).date() for d in dates[:-1]]

        _setup_mocks(monkeypatch, {
            "sector_code": "BK_L", "sector_name": "涨跌停测试板块",
            "sector_type": "industry", "source": "akshare",
        }, constituents, hist_df, prior_dates)

        from src.sector.sector_strength import calculate_sector_strength
        result = calculate_sector_strength("2026-07-09", sector_code="BK_L")
        assert result.limit_up_count == 1  # only stock 000001 has pct_chg >= 9.8 today
        assert result.limit_down_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# 9. Rules tests (pure functions)
# ══════════════════════════════════════════════════════════════════════════════


class TestStrengthRules:
    """Pure scoring rule tests."""

    def test_very_strong_from_good_indicators(self):
        from src.rules.sector_strength_rules import compute_strength_score
        ind = {
            "return_3d": 5.0, "return_5d": 8.0, "return_10d": 12.0,
            "return_20d": 15.0, "relative_strength_5d": 4.0,
            "up_ratio": 0.85, "turnover_ratio_20d": 1.4,
            "limit_up_count": 8, "valid_stock_count": 50,
        }
        score, level, reasons = compute_strength_score(ind)
        assert level == STRENGTH_VERY_STRONG
        assert score >= 80
        assert len(reasons) >= 1

    def test_very_weak_from_bad_indicators(self):
        from src.rules.sector_strength_rules import compute_strength_score
        ind = {
            "return_3d": -4.0, "return_5d": -6.0, "return_10d": -8.0,
            "return_20d": -10.0, "relative_strength_5d": -5.0,
            "up_ratio": 0.2, "turnover_ratio_20d": 0.6,
            "limit_up_count": 0, "valid_stock_count": 50,
        }
        score, level, reasons = compute_strength_score(ind)
        assert level in (STRENGTH_WEAK, STRENGTH_VERY_WEAK)
        assert score < 45

    def test_neutral_from_mixed(self):
        from src.rules.sector_strength_rules import compute_strength_score
        ind = {
            "return_3d": 0.5, "return_5d": 1.0, "return_10d": -0.5,
            "return_20d": 0.2, "relative_strength_5d": 0.1,
            "up_ratio": 0.5, "turnover_ratio_20d": 1.0,
            "limit_up_count": 1, "valid_stock_count": 50,
        }
        score, level, reasons = compute_strength_score(ind)
        assert level == STRENGTH_NEUTRAL
        assert 30 <= score <= 65

    def test_unknown_from_zero_stocks(self):
        from src.rules.sector_strength_rules import compute_strength_score
        ind = {"valid_stock_count": 0}
        score, level, reasons = compute_strength_score(ind)
        assert level == STRENGTH_UNKNOWN


# ══════════════════════════════════════════════════════════════════════════════
# 10. Regression tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRegression:
    """Ensure previous versions are not broken."""

    def test_strength_types_import(self):
        from src.sector.sector_strength_types import (
            SectorStrengthResult, SectorStrengthRanking,
            STRENGTH_LEVELS,
        )
        assert "very_strong" in STRENGTH_LEVELS
        assert "weak" in STRENGTH_LEVELS

    def test_sector_mapping_still_works(self, monkeypatch):
        """Quick check V1.5.3 still imports."""
        from src.sector.sector_types import StockSectorsResult
        r = StockSectorsResult(stock_code="000001", stock_name="test")
        assert r.version == "v1.5.3"

    def test_sentiment_still_works(self):
        """V1.5.2 still imports."""
        from src.sentiment.sentiment_types import SentimentCycle
        c = SentimentCycle(
            trade_date="2026-07-09", sentiment_cycle="unknown",
            sentiment_score=0, risk_level="unknown",
            can_try_position=False, can_attack=False,
            relay_risk_level="unknown", chase_high_allowed=False,
            action_hint="test",
        )
        assert c.version == "v1.5.2"
