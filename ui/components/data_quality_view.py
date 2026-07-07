"""V1.4.10 Data Quality Dashboard — Streamlit UI data-prep helpers.

Strictly read-only: no writes, no scans, no real backfill. These
functions wrap :mod:`src.data_quality.quality_dashboard` and reshape its
raw dict/row output into DataFrames + display-ready fields. None of
them import ``streamlit``, so they can be unit-tested head-less.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd

from src.data_quality.quality_dashboard import (
    build_quality_overview,
    load_batch_execution_health,
    load_calendar_health,
    load_coverage_summary,
    load_provider_health,
    load_security_master_health,
    load_storage_health,
    HEALTH_HEALTHY, HEALTH_USABLE, HEALTH_RISKY,
    HEALTH_NOT_RECOMMENDED, HEALTH_UNAVAILABLE, HEALTH_UNKNOWN,
    OVERALL_HEALTHY, OVERALL_USABLE, OVERALL_RISKY,
    OVERALL_NOT_RECOMMENDED,
)


# ── Status → Chinese ────────────────────────────────────────────────────────

OVERALL_STATUS_CN: dict[str, str] = {
    OVERALL_HEALTHY: "健康",
    OVERALL_USABLE: "可用但有缺口",
    OVERALL_RISKY: "风险较高",
    OVERALL_NOT_RECOMMENDED: "不建议分析",
    HEALTH_UNKNOWN: "未知",
}

HEALTH_STATUS_CN: dict[str, str] = {
    HEALTH_HEALTHY: "健康",
    HEALTH_USABLE: "可用但有缺口",
    HEALTH_RISKY: "风险较高",
    HEALTH_NOT_RECOMMENDED: "不建议分析",
    HEALTH_UNAVAILABLE: "不可用",
    HEALTH_UNKNOWN: "未知",
}

COVERAGE_LEVEL_CN: dict[str, str] = {
    HEALTH_HEALTHY: "健康",
    HEALTH_USABLE: "可用但有缺口",
    HEALTH_RISKY: "风险较高",
    HEALTH_NOT_RECOMMENDED: "不建议分析",
    HEALTH_UNKNOWN: "未知",
}


def status_to_cn(status: str | None, mapping: Mapping[str, str] | None = None) -> str:
    """Translate an English status token to Chinese display text."""
    if status is None:
        return "未知"
    m = mapping if mapping is not None else HEALTH_STATUS_CN
    return m.get(status, status)


def overview_to_cn(overview: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of overview with sub-statuses translated to Chinese."""
    out = dict(overview)
    out["overall_status_cn"] = OVERALL_STATUS_CN.get(
        overview.get("overall_status"), "未知")
    for key in ("coverage_status", "calendar_status",
                "security_master_status", "provider_status",
                "batch_status", "storage_status"):
        out[f"{key}_cn"] = HEALTH_STATUS_CN.get(out.get(key), "未知")
    return out


# ── Canonical column orders ─────────────────────────────────────────────────

COVERAGE_COLUMNS = (
    "universe_name", "data_type", "expected_count", "actual_count",
    "missing_count", "coverage_rate", "coverage_level", "last_scan_time",
    "report_path",
)

CALENDAR_FIELDS = (
    "calendar_source", "min_trade_date", "max_trade_date",
    "total_trade_days", "latest_trade_day", "next_trade_day",
    "missing_recent_days", "is_recent_calendar_ready",
    "health_status", "issue_summary",
)

SECURITY_FIELDS = (
    "total_securities", "active_securities", "delisted_securities",
    "st_count", "suspended_count",
    "missing_name_count", "missing_list_date_count",
    "missing_delist_date_count", "missing_exchange_count",
    "missing_status_count", "completeness_rate",
    "health_status", "issue_summary",
)

PROVIDER_COLUMNS = (
    "provider", "total_tasks", "success_tasks", "failed_tasks",
    "empty_tasks", "retryable_tasks",
    "failure_rate", "empty_rate", "retryable_rate", "recent_failure_rate",
    "health_status", "suggested_action",
)

BATCH_HEALTH_FIELDS = (
    "total_batches", "success_batches", "failed_batches", "partial_batches",
    "recent_batches", "recent_failed_batches",
    "total_tasks", "failed_tasks", "retryable_tasks",
    "avg_failure_rate", "latest_batch_id", "latest_batch_status",
    "health_status", "issue_summary",
)

STORAGE_COLUMNS = (
    "storage_type", "object_name", "row_count", "file_count",
    "total_size_mb", "min_date", "max_date", "last_modified",
    "health_status", "issue_summary",
)


# ── Loaders (handle-error → empty canonical DataFrames) ────────────────────

def _empty_df(cols: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(cols))


def load_quality_overview() -> dict[str, Any]:
    """Top-level overview dict (translated to CN)."""
    try:
        o = build_quality_overview()
    except Exception:
        o = {
            "overall_status": HEALTH_UNKNOWN, "overall_score": None,
            "status_reason": "", "top_issues": [],
            "suggested_next_actions": [], "generated_at": None,
        }
    return overview_to_cn(o)


def load_coverage_table(
    universe_names: Sequence[str] | None = None,
    adj_types: Sequence[str] | None = None,
    coverage_level: str | None = None,
) -> pd.DataFrame:
    try:
        rows = load_coverage_summary(
            universe_names=universe_names, adj_types=adj_types,
            coverage_level=coverage_level,
        )
    except Exception:
        return _empty_df(COVERAGE_COLUMNS)
    if not rows:
        return _empty_df(COVERAGE_COLUMNS)
    df = pd.DataFrame(rows)
    if "coverage_level" in df.columns:
        df["coverage_level"] = df["coverage_level"].map(
            lambda x: COVERAGE_LEVEL_CN.get(x, x))
    if "last_scan_time" in df.columns:
        df["last_scan_time"] = pd.to_datetime(
            df["last_scan_time"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M").fillna("")
    return df[[c for c in COVERAGE_COLUMNS if c in df.columns]]


def load_calendar_summary() -> dict[str, Any]:
    """Calendar health dict with health_status translated to Chinese."""
    try:
        h = load_calendar_health()
    except Exception:
        h = {"health_status": HEALTH_UNKNOWN, "issue_summary": "读取失败"}
    out = dict(h)
    # Translate date fields to YYYY-MM-DD strings when present.
    for k in ("min_trade_date", "max_trade_date",
              "latest_trade_day", "next_trade_day"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d")
        elif v is None:
            out[k] = "-"
    out["health_status_cn"] = HEALTH_STATUS_CN.get(out.get("health_status"), "未知")
    return out


def load_security_master_summary() -> dict[str, Any]:
    try:
        h = load_security_master_health()
    except Exception:
        h = {"health_status": HEALTH_UNKNOWN, "issue_summary": "读取失败"}
    out = dict(h)
    if out.get("completeness_rate") is not None:
        out["completeness_rate"] = round(out["completeness_rate"], 4)
    out["health_status_cn"] = HEALTH_STATUS_CN.get(out.get("health_status"), "未知")
    return out


def load_provider_table() -> pd.DataFrame:
    try:
        rows = load_provider_health()
    except Exception:
        return _empty_df(PROVIDER_COLUMNS)
    if not rows:
        return _empty_df(PROVIDER_COLUMNS)
    df = pd.DataFrame(rows)
    if "health_status" in df.columns:
        df["health_status"] = df["health_status"].map(
            lambda x: HEALTH_STATUS_CN.get(x, x))
    return df[[c for c in PROVIDER_COLUMNS if c in df.columns]]


def load_batch_health_summary() -> dict[str, Any]:
    try:
        h = load_batch_execution_health()
    except Exception:
        h = {"health_status": HEALTH_UNKNOWN, "issue_summary": "读取失败"}
    out = dict(h)
    if out.get("avg_failure_rate") is not None:
        out["avg_failure_rate"] = round(out["avg_failure_rate"], 4)
    out["health_status_cn"] = HEALTH_STATUS_CN.get(out.get("health_status"), "未知")
    return out


def load_storage_table() -> pd.DataFrame:
    try:
        rows = load_storage_health()
    except Exception:
        return _empty_df(STORAGE_COLUMNS)
    if not rows:
        return _empty_df(STORAGE_COLUMNS)
    df = pd.DataFrame(rows)
    if "health_status" in df.columns:
        df["health_status"] = df["health_status"].map(
            lambda x: HEALTH_STATUS_CN.get(x, x))
    if "storage_type" in df.columns:
        df["storage_type"] = df["storage_type"].map(
            {"duckdb": "DuckDB", "parquet": "Parquet"}).fillna(df["storage_type"])
    return df[[c for c in STORAGE_COLUMNS if c in df.columns]]


# ── Display helpers ─────────────────────────────────────────────────────────

def overview_metrics(overview: dict[str, Any]) -> dict[str, Any]:
    """Build the per-universe / per-axis KPI card inputs from an overview dict.

    Coverage rates are recomputed from the coverage summary because the
    overview dict itself only stores the sub-status, not the rate.
    """
    metrics: dict[str, Any] = {
        "overall_status_cn": overview.get("overall_status_cn", "未知"),
        "overall_score": overview.get("overall_score"),
        "generated_at": overview.get("generated_at"),
        "status_reason": overview.get("status_reason", ""),
    }
    # Coverage rates by universe and by adj.
    try:
        cov = load_coverage_summary()
    except Exception:
        cov = []
    rates_by_uni: dict[str, float | None] = {}
    rates_by_adj: dict[str, list[float]] = {"raw": [], "qfq": []}
    for r in cov:
        u = r["universe_name"]  # e.g. "core_50"
        rate = r["coverage_rate"]
        # Keep best (max) rate per universe across raw+qfq if multiple.
        prev = rates_by_uni.get(u)
        if prev is None or (rate is not None and rate > (prev or -1)):
            rates_by_uni[u] = rate
        if rate is not None:
            rates_by_adj.get(r["data_type"], []).append(rate)
    for u in ("core_50", "core_100", "core_500"):
        metrics[f"{u}_coverage_rate"] = rates_by_uni.get(u)
    for adj in ("raw", "qfq"):
        vals = rates_by_adj.get(adj) or []
        metrics[f"{adj}_coverage_rate"] = (
            sum(vals) / len(vals) if vals else None
        )
    return metrics


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Encode a DataFrame to UTF-8 BOM-prefixed CSV bytes for download."""
    if df is None or df.empty:
        df = pd.DataFrame()
    return df.to_csv(index=False).encode("utf-8-sig")