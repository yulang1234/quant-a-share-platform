"""Multi-factor composite score calculator. V1.3."""
from __future__ import annotations
import json
from typing import Any
import pandas as pd
from src.scoring.factor_filter import filter_factors_by_analysis
from src.scoring.score_config import get_default_score_model, normalize_factor_weights, validate_score_model_config
from src.storage.duckdb_repo import fetch_factor_rankings, upsert_score_model_config, upsert_stock_composite_score, upsert_stock_score_detail


def get_rank_data_for_scoring(factor_names: list[str], trade_date=None, start_date=None, end_date=None, limit=None) -> pd.DataFrame:
    df = fetch_factor_rankings(factor_name=factor_names[0] if len(factor_names) == 1 else None, trade_date=trade_date, start_date=start_date, end_date=end_date, limit=limit)
    if not df.empty and "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    return df


def calculate_composite_scores(rank_df: pd.DataFrame, model_name: str, factor_weights: dict, score_method: str = "percentile_rank_weighted_sum", universe_name: str = "core_500") -> tuple:
    if rank_df is None or rank_df.empty: return pd.DataFrame(), pd.DataFrame()
    if isinstance(factor_weights, str): factor_weights = json.loads(factor_weights)
    weights = normalize_factor_weights(dict(factor_weights))
    fnames = list(weights.keys())
    expected = len(fnames)

    df = rank_df[rank_df["factor_name"].isin(fnames)].copy()
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)

    # Build detail
    score_col = "percentile_rank" if "percentile_rank" in score_method else "direction_value"
    detail_rows = []
    for _, r in df.iterrows():
        fn = r["factor_name"]; w = weights.get(fn, 0)
        sc = r.get(score_col)
        if pd.isna(sc): continue
        detail_rows.append({"trade_date": r["trade_date"], "stock_code": r["stock_code"], "factor_name": fn, "raw_value": r.get("raw_value" if score_col != "raw_value" else score_col), "factor_score": sc, "factor_weight": w, "weighted_score": sc * w, "factor_rank_value": r.get("rank_value"), "factor_percentile_rank": r.get("percentile_rank")})

    det = pd.DataFrame(detail_rows)
    if det.empty: return pd.DataFrame(), det

    # Aggregate
    agg = det.groupby(["trade_date", "stock_code"]).agg(composite_score=("weighted_score", "sum"), available_factor_count=("factor_name", "count")).reset_index()
    agg["expected_factor_count"] = expected
    agg["missing_factor_count"] = expected - agg["available_factor_count"]
    agg["factor_coverage_ratio"] = agg["available_factor_count"] / expected
    agg["model_name"] = model_name; agg["universe_name"] = universe_name

    # Rank within each trade_date
    agg["score_rank"] = agg.groupby("trade_date")["composite_score"].rank(ascending=False, method="min").astype(int)
    agg["percentile_score"] = agg.groupby("trade_date")["composite_score"].rank(pct=True, ascending=True)

    det["model_name"] = model_name; det["universe_name"] = universe_name
    return agg, det


def save_scoring_results(composite_df: pd.DataFrame, detail_df: pd.DataFrame) -> dict[str, int]:
    return {"written_composite_rows": upsert_stock_composite_score(composite_df) if not composite_df.empty else 0, "written_detail_rows": upsert_stock_score_detail(detail_df) if not detail_df.empty else 0}


def run_scoring(model_name: str, trade_date=None, start_date=None, end_date=None, limit=None, universe_name="core_500") -> dict[str, Any]:
    cfg = get_default_score_model(model_name)
    if not cfg: return {"model_name": model_name, "factor_count": 0, "source_rows": 0, "composite_rows": 0, "detail_rows": 0, "written_composite_rows": 0, "written_detail_rows": 0, "status": "skipped (unknown model)"}
    validate_score_model_config(cfg)
    w = cfg["factor_weights"]
    if isinstance(w, str): w = json.loads(w)
    fnames = list(w.keys())
    expected_total = len(fnames)

    # Apply factor effectiveness filter
    filtered = filter_factors_by_analysis(
        fnames,
        min_avg_rank_ic=cfg.get("min_avg_rank_ic"),
        min_positive_rank_ic_ratio=cfg.get("min_positive_rank_ic_ratio"),
        min_avg_group_spread=cfg.get("min_avg_group_spread"),
    )
    if not filtered:
        return {"model_name": model_name, "factor_count": expected_total, "source_rows": 0, "composite_rows": 0, "detail_rows": 0, "written_composite_rows": 0, "written_detail_rows": 0, "status": "skipped (all factors filtered)"}

    # Re-normalize weights for remaining factors
    filtered_weights = {k: v for k, v in w.items() if k in filtered}
    filtered_weights = normalize_factor_weights(filtered_weights) if filtered_weights else {}
    w = filtered_weights
    fnames = list(w.keys())

    # Save model config
    cf = {k: v for k, v in cfg.items() if k != "factor_weights"}
    cf["factor_weights"] = json.dumps(w)
    upsert_score_model_config(pd.DataFrame([cf]))

    rank = get_rank_data_for_scoring(fnames, trade_date, start_date, end_date, limit)
    if rank.empty: return {"model_name": model_name, "factor_count": len(fnames), "source_rows": 0, "composite_rows": 0, "detail_rows": 0, "written_composite_rows": 0, "written_detail_rows": 0, "status": "skipped (no rank data)"}

    comp, det = calculate_composite_scores(rank, model_name, w, cfg.get("score_method", "percentile_rank_weighted_sum"), universe_name)
    saved = save_scoring_results(comp, det)
    return {"model_name": model_name, "factor_count": len(fnames), "source_rows": len(rank), "composite_rows": len(comp), "detail_rows": len(det), "written_composite_rows": saved["written_composite_rows"], "written_detail_rows": saved["written_detail_rows"], "status": "success" if len(comp) > 0 else "skipped"}
