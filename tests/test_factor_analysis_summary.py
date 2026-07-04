"""Tests for src/factor_analysis/analysis_summary.py"""
import pandas as pd
from src.factor_analysis.analysis_summary import save_analysis_summary, summarize_factor_analysis


class TestSummary:
    def test_basic(self) -> None:
        ic = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02"] * 5), "ic": [0.1, -0.1, 0.2, 0.0, 0.15], "rank_ic": [0.12, -0.08, 0.18, 0.02, 0.14]})
        grp = pd.DataFrame({"trade_date": ["2026-01-02"] * 3, "group_id": [1, 3, 5], "avg_forward_return": [0.01, 0.03, 0.05]})
        r = summarize_factor_analysis(ic, grp, "ret20", 5)
        assert abs(r["avg_ic"].iloc[0] - 0.07) < 0.001

    def test_inferred_dates_from_data(self) -> None:
        """When start_date/end_date are None, infer from ic_df trade_date."""
        ic = pd.DataFrame({"trade_date": pd.to_datetime(["2026-03-15", "2026-06-30"]), "ic": [0.1, 0.2]})
        r = summarize_factor_analysis(ic, pd.DataFrame(), "ret20", 5, start_date=None, end_date=None)
        assert r["start_date"].iloc[0] == "2026-03-15"
        assert r["end_date"].iloc[0] == "2026-06-30"

    def test_sentinel_dates_when_empty(self) -> None:
        """When no data at all, use sentinel 1900-01-01."""
        r = summarize_factor_analysis(pd.DataFrame(), pd.DataFrame(), "ret20", 5, start_date=None, end_date=None)
        assert r["start_date"].iloc[0] == "1900-01-01"
        assert r["end_date"].iloc[0] == "1900-01-01"

    def test_save_no_null_error(self, fresh_db) -> None:  # noqa: F811
        """Save summary with inferred dates — no NOT NULL constraint error."""
        ic = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02"]), "ic": [0.1]})
        r = summarize_factor_analysis(ic, pd.DataFrame(), "ret20", 5, start_date=None, end_date=None)
        n = save_analysis_summary(r)
        assert n == 1

    def test_upsert_idempotent(self, fresh_db) -> None:  # noqa: F811
        r = summarize_factor_analysis(pd.DataFrame(), pd.DataFrame(), "ret20", 5, start_date=None, end_date=None)
        n1 = save_analysis_summary(r)
        n2 = save_analysis_summary(r)
        assert n1 == 1
        assert n2 == 1

    def test_user_dates_preserved(self) -> None:
        r = summarize_factor_analysis(pd.DataFrame(), pd.DataFrame(), "ret20", 5, start_date="2020-01-01", end_date="2023-12-31")
        assert r["start_date"].iloc[0] == "2020-01-01"
        assert r["end_date"].iloc[0] == "2023-12-31"
