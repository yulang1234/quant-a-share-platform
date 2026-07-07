"""V1.4.9 Streamlit Backfill Batch view — read-only data preparation helpers.

This module contains pure pandas/data-access helpers used by the
"补数批次" tab in :mod:`ui.streamlit_app`. They are deliberately kept
free of ``streamlit`` imports so they can be unit-tested head-less.

Boundary reminder: this module **never executes** real backfill tasks.
It only prepares data for display/export and builds *suggested* retry
commands as text.
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from src.backfill.batch_failure import (
    build_suggested_retry_command,
    compute_provider_failure,
    list_batches_with_coverage,
    list_failed_tasks,
)


# Column ordering for display (English keys → Chinese display handled in the
# main app via _COL_CN).
BATCH_COLUMNS = (
    "batch_id", "created_at", "universe_name", "status",
    "total_tasks", "success_tasks", "failed_tasks", "empty_tasks",
    "retryable_tasks", "coverage_before", "coverage_after",
    "coverage_delta", "provider", "duration_seconds", "report_path",
)

FAILED_TASK_COLUMNS = (
    "batch_id", "task_id", "symbol", "ts_code",
    "trade_date_start", "trade_date_end", "provider",
    "data_type", "adj_type", "status", "error_type", "error_category",
    "error_message", "retryable", "retry_reason",
    "attempt_count", "max_attempts", "suggested_retry_command",
)

PROVIDER_COLUMNS = (
    "batch_id", "provider", "total_tasks", "success_tasks",
    "failed_tasks", "empty_tasks", "retryable_tasks",
    "failure_rate", "empty_rate", "retryable_rate",
)


def load_batches(
    limit: int = 100,
    universe_name: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> pd.DataFrame:
    """Load batches as a DataFrame, applying optional filters.

    ``created_from`` / ``created_to`` are inclusive date strings accepted by
    ``pd.to_datetime`` (e.g. ``"2024-01-01"``). On any backend error an empty
    DataFrame with the canonical columns is returned — the UI never crashes.
    """
    try:
        rows = list_batches_with_coverage(
            limit=limit, universe_name=universe_name,
            status=status, provider=provider,
        )
    except Exception:
        return pd.DataFrame(columns=list(BATCH_COLUMNS))

    if not rows:
        return pd.DataFrame(columns=list(BATCH_COLUMNS))

    df = pd.DataFrame(rows)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        if created_from:
            lo = pd.to_datetime(created_from, errors="coerce")
            if pd.notna(lo):
                df = df[df["created_at"] >= lo]
        if created_to:
            hi = pd.to_datetime(created_to, errors="coerce")
            if pd.notna(hi):
                df = df[df["created_at"] <= hi]
        # Friendly text form for display once filtering is done.
        df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
    # Honour canonical column order.
    return df[[c for c in BATCH_COLUMNS if c in df.columns]]


def load_failed_tasks(
    batch_id: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    adj_type: str | None = None,
    retryable_only: bool = False,
    save_local_hint: bool = False,
) -> pd.DataFrame:
    """Load failed/empty task detail as a DataFrame (read-only)."""
    try:
        rows = list_failed_tasks(
            batch_id=batch_id, status=status, provider=provider,
            adj_type=adj_type, retryable_only=retryable_only,
            save_local_hint=save_local_hint,
        )
    except Exception:
        return pd.DataFrame(columns=list(FAILED_TASK_COLUMNS))
    if not rows:
        return pd.DataFrame(columns=list(FAILED_TASK_COLUMNS))
    df = pd.DataFrame(rows)
    return df[[c for c in FAILED_TASK_COLUMNS if c in df.columns]]


def load_provider_failure(batch_ids: Iterable[str]) -> pd.DataFrame:
    """Load per-(batch, provider) failure stats as a DataFrame."""
    try:
        df = compute_provider_failure(batch_ids)
    except Exception:
        return pd.DataFrame(columns=list(PROVIDER_COLUMNS))
    # Ensure column order.
    return df[[c for c in PROVIDER_COLUMNS if c in df.columns]]


def overview_metrics(batches_df: pd.DataFrame) -> dict[str, Any]:
    """Compute the top-of-page KPI card numbers from a batches DataFrame."""
    if batches_df is None or batches_df.empty:
        return {
            "batch_count": 0, "total_tasks": 0, "success_tasks": 0,
            "failed_tasks": 0, "empty_tasks": 0, "retryable_tasks": 0,
            "avg_failure_rate": None, "avg_coverage_delta": None,
        }
    total = int(batches_df["total_tasks"].fillna(0).sum())
    success = int(batches_df["success_tasks"].fillna(0).sum())
    failed = int(batches_df["failed_tasks"].fillna(0).sum())
    empty = int(batches_df["empty_tasks"].fillna(0).sum())
    retryable = int(batches_df["retryable_tasks"].fillna(0).sum())
    avg_fail = (failed / total) if total > 0 else None
    deltas = batches_df["coverage_delta"].dropna()
    avg_delta = float(deltas.mean()) if not deltas.empty else None
    return {
        "batch_count": int(len(batches_df)),
        "total_tasks": total, "success_tasks": success,
        "failed_tasks": failed, "empty_tasks": empty,
        "retryable_tasks": retryable,
        "avg_failure_rate": avg_fail,
        "avg_coverage_delta": avg_delta,
    }


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Encode a DataFrame to UTF-8 BOM-prefixed CSV for download."""
    if df is None or df.empty:
        df = pd.DataFrame()
    return df.to_csv(index=False).encode("utf-8-sig")


def batch_suggested_command(batch_id: str, save_local: bool = False) -> str:
    """Convenience wrapper — a copy-friendly suggested command for a batch."""
    return build_suggested_retry_command(batch_id, save_local=save_local, dry_run=True)