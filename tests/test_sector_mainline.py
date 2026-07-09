"""V1.5.5 sector mainline tests.

Tests cover:
1. Confirmed mainline
2. Potential mainline
3. One-day theme
4. Cooling sector
5. High-risk sector
6. Neutral
7. Unknown / data insufficient
8. Mainline snapshot
9. Regression (V1.5.1-1.5.4 unbroken)
"""
from __future__ import annotations

import pytest

from src.sector.sector_mainline_types import (
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
    RISK_ONE_DAY_SPIKE, RISK_RANK_DROP, RISK_OVERHEAT,
    RISK_TURNOVER_ABNORMAL, RISK_BIG_LOSS_RISING,
    RISK_PERSISTENCE_INSUFFICIENT,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_today(overrides=None) -> dict:
    """Build a typical today strength dict."""
    base = {
        "sector_code": "BK_TEST", "sector_name": "测试板块",
        "sector_type": "industry",
        "strength_score": 85, "strength_level": "very_strong",
        "valid_stock_count": 50,
        "avg_pct_chg": 2.5,
        "return_3d": 5.0, "return_5d": 8.0, "return_10d": 12.0, "return_20d": 15.0,
        "relative_strength_3d": 2.0, "relative_strength_5d": 3.5,
        "relative_strength_10d": 5.0, "relative_strength_20d": 6.0,
        "turnover_ratio_5d": 1.15, "turnover_ratio_20d": 1.25,
        "up_ratio": 0.75, "limit_up_count": 5,
        "big_gain_count": 8, "big_loss_count": 1,
    }
    if overrides:
        base.update(overrides)
    return base


def _classify(today: dict, ranks: list[int] = None, strengths: list[dict] = None):
    """Shortcut to call classify_mainline."""
    from src.rules.sector_mainline_rules import classify_mainline
    return classify_mainline(
        today,
        ranks or [],
        strengths or [],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Confirmed mainline
# ══════════════════════════════════════════════════════════════════════════════


class TestConfirmedMainline:
    def test_confirmed_from_consistent_strength(self):
        today = _make_today({"strength_score": 88})
        # Consistently top-ranked for 5 days
        ranks = [5, 3, 4, 2, 3]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_CONFIRMED
        assert result["confidence"] in ("high", "medium")
        assert result["persistence_days"] >= 3
        assert len(result["reasons"]) >= 2

    def test_confirmed_high_when_very_strong(self):
        today = _make_today({"strength_score": 92})
        ranks = [1, 2, 1, 1, 1]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_CONFIRMED
        assert result["confidence"] == "high"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Potential mainline
# ══════════════════════════════════════════════════════════════════════════════


class TestPotentialMainline:
    def test_potential_from_recent_improvement(self):
        today = _make_today({"strength_score": 72})
        # Improving recently but not long history
        ranks = [40, 25, 8]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_POTENTIAL
        assert result["confidence"] == "medium"
        assert RISK_PERSISTENCE_INSUFFICIENT in result["risk_flags"]

    def test_potential_single_day_strong(self):
        today = _make_today({"strength_score": 68, "relative_strength_5d": 2.0})
        ranks = [35, 12]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_POTENTIAL


# ══════════════════════════════════════════════════════════════════════════════
# 3. One-day theme
# ══════════════════════════════════════════════════════════════════════════════


class TestOneDayTheme:
    def test_one_day_from_sudden_spike(self):
        today = _make_today({"strength_score": 78, "avg_pct_chg": 6.0})
        # Was ranked very low, suddenly jumped to top
        ranks = [55, 48, 5]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_ONE_DAY

    def test_one_day_with_abnormal_turnover(self):
        today = _make_today({
            "strength_score": 75, "avg_pct_chg": 5.5,
            "turnover_ratio_20d": 2.5,  # abnormal
        })
        ranks = [60, 50, 8]  # avg_prev=55 > 40 threshold
        result = _classify(today, ranks)
        assert RISK_TURNOVER_ABNORMAL in result["risk_flags"]


# ══════════════════════════════════════════════════════════════════════════════
# 4. Cooling sector
# ══════════════════════════════════════════════════════════════════════════════


class TestCoolingSector:
    def test_cooling_from_rank_drop(self):
        today = _make_today({
            "strength_score": 55, "up_ratio": 0.4,
            "return_3d": -1.5, "return_5d": -2.0,
        })
        # Was top-ranked, now dropping
        ranks = [3, 5, 22]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_COOLING
        assert RISK_RANK_DROP in result["risk_flags"]

    def test_cooling_from_declining_strength(self):
        today = _make_today({
            "strength_score": 45, "up_ratio": 0.38,
            "relative_strength_5d": -1.0,
        })
        ranks = [8, 12, 28]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_COOLING


# ══════════════════════════════════════════════════════════════════════════════
# 5. High-risk sector
# ══════════════════════════════════════════════════════════════════════════════


class TestHighRiskSector:
    def test_high_risk_from_overheat(self):
        today = _make_today({
            "strength_score": 90, "avg_pct_chg": 6.5,
            "turnover_ratio_20d": 2.2,
        })
        ranks = [2, 1, 1]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_HIGH_RISK
        assert RISK_OVERHEAT in result["risk_flags"]
        assert RISK_TURNOVER_ABNORMAL in result["risk_flags"]

    def test_high_risk_with_big_loss(self):
        today = _make_today({
            "strength_score": 88, "avg_pct_chg": 5.0,
            "big_loss_count": 5,
        })
        ranks = [1, 2, 1]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_HIGH_RISK
        assert RISK_BIG_LOSS_RISING in result["risk_flags"]


# ══════════════════════════════════════════════════════════════════════════════
# 6. Neutral
# ══════════════════════════════════════════════════════════════════════════════


class TestNeutral:
    def test_neutral_from_average(self):
        today = _make_today({"strength_score": 50, "avg_pct_chg": 0.2})
        ranks = [40, 35, 38]
        result = _classify(today, ranks)
        assert result["mainline_status"] == MAINLINE_NEUTRAL
        assert result["confidence"] == "low"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Unknown
# ══════════════════════════════════════════════════════════════════════════════


class TestUnknown:
    def test_unknown_from_empty_today(self):
        from src.rules.sector_mainline_rules import classify_mainline
        result = classify_mainline({}, [], [])
        assert result["mainline_status"] == MAINLINE_UNKNOWN

    def test_unknown_from_zero_stocks(self):
        today = _make_today({"valid_stock_count": 0, "strength_score": 0})
        result = _classify(today, [])
        assert result["mainline_status"] == MAINLINE_UNKNOWN


# ══════════════════════════════════════════════════════════════════════════════
# 8. Mainline snapshot
# ══════════════════════════════════════════════════════════════════════════════


class TestMainlineSnapshot:
    def test_snapshot_fields(self):
        from src.sector.sector_mainline_types import MainlineSnapshot
        snap = MainlineSnapshot(
            trade_date="2026-07-09",
            has_clear_mainline=True,
            confirmed_mainlines=[{
                "sector_code": "BK_S", "sector_name": "强板块",
                "mainline_score": 86, "confidence": "high",
                "rank_overall": 3, "risk_flags": [],
            }],
            market_mainline_summary="当前存在 1 个确认主线。",
        )
        d = snap.as_dict()
        assert d["has_clear_mainline"] is True
        assert len(d["confirmed_mainlines"]) == 1
        assert d["version"] == "v1.5.5"
        assert isinstance(d["market_mainline_summary"], str)
        assert len(d["market_mainline_summary"]) > 0

    def test_snapshot_categorization(self, monkeypatch):
        """Build a snapshot with multiple statuses."""
        from src.sector.sector_mainline_types import (
            SectorMainlineResult, MainlineSnapshot,
        )
        # Directly construct results
        fake_results = [
            SectorMainlineResult(
                trade_date="2026-07-09", sector_code="BK_A", sector_name="确认主线A",
                sector_type="industry", mainline_status=MAINLINE_CONFIRMED,
                mainline_score=86, confidence="high",
            ),
            SectorMainlineResult(
                trade_date="2026-07-09", sector_code="BK_B", sector_name="潜在主线B",
                sector_type="industry", mainline_status=MAINLINE_POTENTIAL,
                mainline_score=72, confidence="medium",
            ),
            SectorMainlineResult(
                trade_date="2026-07-09", sector_code="BK_C", sector_name="一日游C",
                sector_type="concept", mainline_status=MAINLINE_ONE_DAY,
                mainline_score=55, confidence="medium",
            ),
            SectorMainlineResult(
                trade_date="2026-07-09", sector_code="BK_D", sector_name="降温D",
                sector_type="industry", mainline_status=MAINLINE_COOLING,
                mainline_score=42, confidence="medium",
            ),
            SectorMainlineResult(
                trade_date="2026-07-09", sector_code="BK_E", sector_name="高风险E",
                sector_type="concept", mainline_status=MAINLINE_HIGH_RISK,
                mainline_score=40, confidence="high",
            ),
        ]

        # Mock the all-mainlines function
        from src.sector.sector_mainline_types import AllMainlineResult
        monkeypatch.setattr(
            "src.sector.sector_mainline.identify_all_sector_mainlines",
            lambda td, sector_type=None: AllMainlineResult(
                trade_date=td, results=fake_results, sector_count=5,
            ),
        )

        from src.sector.sector_mainline import build_mainline_snapshot
        snap = build_mainline_snapshot("2026-07-09")
        assert snap.has_clear_mainline is True
        assert len(snap.confirmed_mainlines) == 1
        assert len(snap.potential_mainlines) == 1
        assert len(snap.one_day_themes) == 1
        assert len(snap.cooling_sectors) == 1
        assert len(snap.high_risk_sectors) == 1
        assert "确认主线" in snap.market_mainline_summary
        assert "潜在主线" in snap.market_mainline_summary


# ══════════════════════════════════════════════════════════════════════════════
# 9. Regression tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRegression:
    def test_mainline_types_import(self):
        from src.sector.sector_mainline_types import MAINLINE_STATUSES, RISK_FLAGS
        assert MAINLINE_CONFIRMED in MAINLINE_STATUSES
        assert RISK_ONE_DAY_SPIKE in RISK_FLAGS

    def test_v154_still_works(self):
        from src.sector.sector_strength_types import SectorStrengthResult
        r = SectorStrengthResult(
            trade_date="2026-07-09", sector_code="BK_X",
            sector_name="test", sector_type="industry", source="test",
        )
        assert r.version == "v1.5.4"

    def test_v153_still_works(self):
        from src.sector.sector_types import StockSectorsResult
        r = StockSectorsResult(stock_code="000001", stock_name="test")
        assert r.version == "v1.5.3"

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

    def test_no_boundary_violations(self):
        """V1.5.5 should not output buy/sell/leader advice."""
        from src.sector.sector_mainline import VERSION
        assert "v1.5.5" in VERSION
        # Check that mainline types don't contain forbidden words
        from src.sector.sector_mainline_types import (
            SectorMainlineResult, MainlineSnapshot,
        )
        # Ensure no trading advice in field names
        forbidden = ["buy", "sell", "买入", "卖出", "leader", "龙头", "recommend"]
        for name in SectorMainlineResult.__dataclass_fields__:
            combined = name.lower()
            for f in forbidden:
                assert f not in combined, f"Forbidden word in field: {name}"
