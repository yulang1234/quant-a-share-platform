"""V1.6.1 Leader scoring tests."""
import pytest
from src.leader.leader_scoring import compute_leader_score


def _f(**kw) -> dict:
    base = {"pct_chg_5d": 10, "sector_avg_5d": 5, "turnover_rank_in_sector": 2,
            "sector_stock_count": 20, "price_rank_in_sector": 3, "drawdown_20d": 5,
            "startup_timing": "early", "above_ma5": True, "above_ma10": True,
            "above_ma20": True, "up_days_recent": 4}
    base.update(kw)
    return base


class TestLeaderScoring:
    def test_all_scores_in_range(self):
        scores = compute_leader_score(_f())
        for k in ["relative_strength_score", "turnover_score", "price_rank_score",
                   "resilience_score", "startup_score", "trend_structure_score",
                   "continuity_score", "leader_score"]:
            assert 0 <= scores[k] <= 100, f"{k} out of range: {scores[k]}"

    def test_strong_stock_scores_high(self):
        scores = compute_leader_score(_f(pct_chg_5d=15, sector_avg_5d=2))
        assert scores["leader_score"] > 60

    def test_weak_stock_scores_low(self):
        scores = compute_leader_score(_f(pct_chg_5d=-5, sector_avg_5d=2, turnover_rank_in_sector=18,
                                          price_rank_in_sector=19, drawdown_20d=20,
                                          above_ma5=False, above_ma10=False, above_ma20=False,
                                          up_days_recent=1))
        assert scores["leader_score"] < 40

    def test_missing_fields_no_crash(self):
        scores = compute_leader_score({})
        assert 0 <= scores["leader_score"] <= 100

    def test_none_fields_no_crash(self):
        scores = compute_leader_score({"pct_chg_5d": None, "sector_avg_5d": None})
        assert scores["leader_score"] >= 0


class TestSafetyKeywords:
    """Ensure leader scoring does not output buy/sell advice."""
    def test_no_forbidden_in_code(self):
        import inspect
        from src.leader import leader_scoring
        src = inspect.getsource(leader_scoring)
        forbidden = ["买入", "卖出", "加仓", "清仓", "满仓", "重仓", "梭哈", "目标价", "必涨", "稳赚", "推荐股票"]
        for w in forbidden:
            assert w not in src, f"Forbidden word in scoring: {w}"
