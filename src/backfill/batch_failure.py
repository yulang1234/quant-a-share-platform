"""V1.4.9 Batch failure governance — read-only analysis of failed/empty/retryable tasks.

This module provides pure (no Streamlit) helpers for backfill batch failure
governance:

* list batches together with before/after coverage snapshots
* classify failed/empty tasks into retryable / non_retryable buckets
* aggregate provider failure rates per batch (via task ↔ task_log join)
* build *suggested* retry commands (text only — never executed here)

Design notes
------------
* Strictly read-only — no writes to the meta DB, no network calls, no real
  execution of backfill tasks. Suggested commands are returned as text for the
  user to copy and run in a terminal.
* Reuses existing ``BatchRepository`` / ``DataLoadTaskRepository`` / SQLAlchemy
  sessions — does not re-invent schema access.
* The retryable decision is **additive**: it keeps the V1.4.8
  ``attempt_count < max_attempts`` rule and additionally requires the error
  category to be transient (timeout / network / rate-limit / provider-temp /
  empty-on-valid-trading-day). The pre-existing
  ``src.backfill.batch_report._compute_counts`` is left untouched so V1.4.8
  behaviour and tests are not disturbed.
"""

from __future__ import annotations

import shlex
from typing import Any, Iterable

import pandas as pd

from sqlalchemy import func

from src.backfill.batch_repo import BatchRepository
from src.db.schema_meta import (
    DataLoadTask,
    DataLoadTaskLog,
)
from src.repositories.meta_db import get_session


# ── Retry classification ────────────────────────────────────────────────────

# Substrings (lowercased) that mark an error as transient / retryable.
_RETRYABLE_SIGNALS: tuple[str, ...] = (
    "timeout", "timed out",
    "connection", "connect", "connreset", "connectionerror",
    "network", "networkerror",
    "rate", "limit", "ratelimit", "429",
    "http 5", "502", "503", "504", "http5",
    "temporarily", "temporarily unavailable", "temporary",
    "provider unavailable", "providerunavailable",
    "retry", "retryable",
)

# Substrings that mark an error as permanent / non-retryable.
_NON_RETRYABLE_SIGNALS: tuple[str, ...] = (
    "invalid symbol", "invalidsymbol", "unknown symbol", "symbol not found",
    "invalid date", "invaliddate", "date range", "out of range",
    "unsupported provider", "unsupportedprovider",
    "non trading day", "nontradingday", "not a trading day", "holiday",
    "delisted", "suspended", "st stock", "st_stock",
    "schema", "schemaerror", "schema error",
    "validation", "validationerror", "argument", "param",
    "not supported", "notsupported",
)

# Empty-but-valid-trading-day markers (provider returned nothing for a day
# that is an open trading day — usually transient).
_EMPTY_VALID_SIGNALS: tuple[str, ...] = (
    "empty", "dataempty", "emptydata", "no data", "nodata",
)


def classify_retry_reason(
    error_type: str | None,
    error_message: str | None = None,
    *,
    status: str | None = None,
) -> tuple[bool, str]:
    """Classify an error into retryable / non-retryable and explain why.

    Parameters
    ----------
    error_type, error_message
        Fields persisted on ``DataLoadTask``. Either may be ``None``.
    status
        Optional task status. ``empty`` tasks are treated specially: an empty
        result is considered retryable unless the error message looks permanent.

    Returns
    -------
    (retryable, reason)
        ``retryable`` is the error-category verdict (independent of attempt
        count — combine with ``attempt_count < max_attempts`` for the final
        decision via :func:`is_task_retryable`). ``reason`` is a short,
        human-readable explanation in English.
    """
    et = (error_type or "").strip().lower()
    em = (error_message or "").strip().lower()
    blob = f"{et} {em}".strip()

    # Permanent errors take priority — even an empty result that mentions
    # "delisted" should not be retried.
    for sig in _NON_RETRYABLE_SIGNALS:
        if sig in blob:
            return False, f"non_retryable: matches '{sig}'"

    # Transient errors.
    for sig in _RETRYABLE_SIGNALS:
        if sig in blob:
            return True, f"retryable: matches '{sig}'"

    # Empty-result tasks are retryable when no permanent signal is present
    # (provider returned nothing on a valid trading day).
    if status == "empty":
        return True, "retryable: empty result on valid trading day (no permanent cause)"

    # Unclassified → be conservative: treat as non-retryable so we don't
    # blindly loop on unknown error shapes.
    return False, "non_retryable: unclassified error"


def is_task_retryable(task: Any) -> bool:
    """Final retryable verdict for a task: attempt budget AND error category.

    Parameters
    ----------
    task
        A ``DataLoadTask`` ORM row (or any object exposing ``attempt_count``,
        ``max_attempts``, ``error_type``, ``error_message`` and ``status``).
    """
    attempts = int(getattr(task, "attempt_count", 0) or 0)
    max_attempts = int(getattr(task, "max_attempts", 5) or 5)
    if attempts >= max_attempts:
        return False
    err_retryable, _ = classify_retry_reason(
        getattr(task, "error_type", None),
        getattr(task, "error_message", None),
        status=getattr(task, "status", None),
    )
    return err_retryable


# ── Suggested command ───────────────────────────────────────────────────────

def build_suggested_retry_command(
    batch_id: str,
    save_local: bool = False,
    dry_run: bool = True,
    limit: int = 10,
) -> str:
    """Build a *suggested* batch_runner command for the user to copy.

    The command is **never executed** by this module — it is plain text shown
    in the UI for the user to copy into a terminal. By default it is a dry-run
    so accidental copy-paste does not trigger real backfill.
    """
    save_flag = "--save-local" if save_local else "--no-save"
    dry_flag = "--dry-run" if dry_run else ""
    parts = [
        "python", "-m", "src.backfill.batch_runner",
        "--batch-id", shlex.quote(str(batch_id)),
        "--status", "retryable",
        "--limit", str(limit),
        save_flag,
        "--allow-core-500-run",
    ]
    if dry_flag:
        parts.append(dry_flag)
    return " ".join(parts)


# ── Batch listing with coverage ──────────────────────────────────────────────

_BATCH_FIELDS = (
    "batch_id", "created_at", "universe_name", "status",
    "total_tasks", "success_tasks", "failed_tasks", "empty_tasks",
    "retryable_tasks", "coverage_before", "coverage_after",
    "coverage_delta", "provider", "duration_seconds", "report_path",
)


def list_batches_with_coverage(
    limit: int = 50,
    universe_name: str | None = None,
    status: str | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """List batches with before/after coverage and derived counts.

    Returns a list of dicts (one per batch) with the keys listed in
    :data:`_BATCH_FIELDS`. Missing / uncomputable values are ``None``.

    Filters ``universe_name`` / ``status`` / ``provider`` are applied where
    supported. ``provider`` filters on the batch-level ``provider_name`` field
    (task-level provider filtering belongs to :func:`list_failed_tasks`).
    """
    repo = BatchRepository()
    batches = repo.list_batches(limit=limit, universe_name=universe_name)

    rows: list[dict[str, Any]] = []
    for b in batches:
        if status and b.status != status:
            continue
        if provider and (b.provider_name or "") != provider:
            continue

        snapshots = repo.get_batch_snapshots(b.batch_id)
        before = next((s for s in snapshots if s.snapshot_type == "before"), None)
        after = next((s for s in snapshots if s.snapshot_type == "after"), None)

        cov_before = before.avg_coverage_rate if before else None
        cov_after = after.avg_coverage_rate if after else None
        cov_delta: float | None = None
        if cov_before is not None and cov_after is not None:
            cov_delta = float(cov_after) - float(cov_before)

        # Per-batch retryable counts (read-only query on tasks).
        counts = _counts_for_batch(b.batch_id)

        duration_seconds: float | None = None
        if b.started_at and b.finished_at:
            duration_seconds = (b.finished_at - b.started_at).total_seconds()

        rows.append({
            "batch_id": b.batch_id,
            "created_at": b.created_at,
            "universe_name": b.universe_name,
            "status": b.status,
            "total_tasks": int(b.planned_task_count or 0),
            "success_tasks": int(b.success_count or 0),
            "failed_tasks": int(b.failed_count or 0),
            "empty_tasks": int(b.empty_count or 0),
            "retryable_tasks": counts["retryable"],
            "coverage_before": cov_before,
            "coverage_after": cov_after,
            "coverage_delta": cov_delta,
            "provider": b.provider_name,
            "duration_seconds": duration_seconds,
            "report_path": "-",  # no persisted report path column; see risk notes
        })
    return rows


def _counts_for_batch(batch_id: str) -> dict[str, int]:
    """Count tasks per status + retryable for a single batch (read-only)."""
    counts = {"success": 0, "failed": 0, "empty": 0, "skipped": 0,
              "retryable": 0, "non_retryable": 0}
    try:
        s = get_session()
        for st in ("success", "failed", "empty", "skipped"):
            counts[st] = int(s.query(func.count()).filter(
                DataLoadTask.batch_id == batch_id,
                DataLoadTask.status == st,
            ).scalar() or 0)
        failed_tasks = s.query(DataLoadTask).filter(
            DataLoadTask.batch_id == batch_id,
            DataLoadTask.status.in_(("failed", "empty")),
        ).all()
        counts["retryable"] = sum(1 for t in failed_tasks if is_task_retryable(t))
        counts["non_retryable"] = len(failed_tasks) - counts["retryable"]
    except Exception:
        pass
    return counts


# ── Failed / empty task detail ───────────────────────────────────────────────

_FAILED_TASK_FIELDS = (
    "batch_id", "task_id", "symbol", "ts_code", "trade_date_start",
    "trade_date_end", "provider", "data_type", "adj_type",
    "status", "error_type", "error_category", "error_message",
    "retryable", "retry_reason", "attempt_count", "max_attempts",
    "suggested_retry_command",
)


def list_failed_tasks(
    batch_id: str | None = None,
    *,
    status: str | None = None,
    provider: str | None = None,
    adj_type: str | None = None,
    retryable_only: bool = False,
    save_local_hint: bool = False,
) -> list[dict[str, Any]]:
    """Return failed/empty task detail rows.

    ``status`` filters to one of ``failed``/``empty`` (``None`` = both).
    ``provider`` filters on ``provider_preference`` (the persisted intended
    provider). ``retryable_only`` restricts to tasks :func:`is_task_retryable`
    considers retryable. ``save_local_hint`` propagates to the suggested
    command (default dry-run either way).
    """
    s = get_session()
    q = s.query(DataLoadTask).filter(DataLoadTask.status.in_(("failed", "empty")))
    if batch_id:
        q = q.filter(DataLoadTask.batch_id == batch_id)
    if status:
        q = q.filter(DataLoadTask.status == status)
    if provider:
        q = q.filter(DataLoadTask.provider_preference == provider)
    if adj_type:
        q = q.filter(DataLoadTask.adj_type == adj_type)

    rows: list[dict[str, Any]] = []
    for t in q.all():
        err_retryable, reason = classify_retry_reason(
            t.error_type, t.error_message, status=t.status,
        )
        final_retryable = err_retryable and is_task_retryable(t)
        if retryable_only and not final_retryable:
            continue

        # Best-effort effective provider (preference + latest log provider).
        effective_provider = t.provider_preference or _latest_log_provider(
            s, t.task_id,
        ) or "unknown"

        rows.append({
            "batch_id": t.batch_id,
            "task_id": t.task_id,
            "symbol": t.symbol,
            "ts_code": f"{t.symbol}.{t.exchange}" if t.symbol and t.exchange else t.symbol,
            "trade_date_start": t.start_date,
            "trade_date_end": t.end_date,
            "provider": effective_provider,
            "data_type": t.data_type,
            "adj_type": t.adj_type,
            "status": t.status,
            "error_type": t.error_type,
            "error_category": _classify_error_category(t.error_type),
            "error_message": t.error_message,
            "retryable": final_retryable,
            "retry_reason": reason,
            "attempt_count": int(t.attempt_count or 0),
            "max_attempts": int(t.max_attempts or 5),
            "suggested_retry_command": (
                build_suggested_retry_command(
                    t.batch_id, save_local=save_local_hint, dry_run=True,
                )
                if final_retryable else ""
            ),
        })
    return rows


def _latest_log_provider(session: Any, task_id: int) -> str | None:
    """Return the provider_used of the most recent task_log entry, if any."""
    try:
        log = session.query(DataLoadTaskLog).filter(
            DataLoadTaskLog.task_id == task_id,
        ).order_by(DataLoadTaskLog.created_at.desc()).first()
        return getattr(log, "provider_used", None)
    except Exception:
        return None


def _classify_error_category(error_type: str | None) -> str:
    """Reuse the existing task_stats classifier for the error_category column."""
    try:
        from src.data_tasks.task_stats import _classify_error
        return _classify_error(error_type)
    except Exception:
        return "UnknownError"


# ── Provider failure aggregation ────────────────────────────────────────────

def compute_provider_failure(batch_ids: Iterable[str]) -> pd.DataFrame:
    """Aggregate per-(batch, provider) failure stats from task ↔ task_log join.

    Returns a DataFrame with columns: batch_id, provider, total_tasks,
    success_tasks, failed_tasks, empty_tasks, retryable_tasks, failure_rate,
    empty_rate, retryable_rate. Rows with no recorded provider_used are grouped
    under ``"unknown"``.
    """
    batch_ids = list(batch_ids)
    if not batch_ids:
        return pd.DataFrame(columns=[
            "batch_id", "provider", "total_tasks", "success_tasks",
            "failed_tasks", "empty_tasks", "retryable_tasks",
            "failure_rate", "empty_rate", "retryable_rate",
        ])

    s = get_session()
    rows = (
        s.query(
            DataLoadTask.batch_id,
            DataLoadTaskLog.provider_used,
            DataLoadTaskLog.status_after,
            func.count().label("cnt"),
        )
        .join(DataLoadTaskLog, DataLoadTaskLog.task_id == DataLoadTask.task_id)
        .filter(DataLoadTask.batch_id.in_(batch_ids))
        .group_by(
            DataLoadTask.batch_id,
            DataLoadTaskLog.provider_used,
            DataLoadTaskLog.status_after,
        )
        .all()
    )

    grouped: dict[tuple[str, str], dict[str, int]] = {}
    for batch_id, prov, status_after, cnt in rows:
        provider = prov or "unknown"
        st = (status_after or "unknown")
        bucket = grouped.setdefault((batch_id, provider), {
            "total": 0, "success": 0, "failed": 0,
            "empty": 0, "skipped": 0, "retryable": 0,
        })
        bucket["total"] += int(cnt or 0)
        if st in bucket:
            bucket[st] += int(cnt or 0)

    # Retryable counts come from DataLoadTask (not the log): failed tasks that
    # pass is_task_retryable. Keep this best-effort.
    try:
        retryable_tasks = (
            s.query(DataLoadTask).filter(
                DataLoadTask.batch_id.in_(batch_ids),
                DataLoadTask.status.in_(("failed", "empty")),
            ).all()
        )
        for t in retryable_tasks:
            prov = t.provider_preference or _latest_log_provider(s, t.task_id) or "unknown"
            bid = t.batch_id
            if (bid, prov) in grouped and is_task_retryable(t):
                grouped[(bid, prov)]["retryable"] += 1
    except Exception:
        pass

    out_rows = []
    for (batch_id, provider), b in grouped.items():
        total = b["total"] or 0
        failed = b["failed"]
        empty = b["empty"]
        retryable = b["retryable"]
        out_rows.append({
            "batch_id": batch_id,
            "provider": provider,
            "total_tasks": total,
            "success_tasks": b["success"],
            "failed_tasks": failed,
            "empty_tasks": empty,
            "retryable_tasks": retryable,
            "failure_rate": (failed / total) if total else None,
            "empty_rate": (empty / total) if total else None,
            "retryable_rate": (retryable / total) if total else None,
        })

    df = pd.DataFrame(out_rows, columns=[
        "batch_id", "provider", "total_tasks", "success_tasks",
        "failed_tasks", "empty_tasks", "retryable_tasks",
        "failure_rate", "empty_rate", "retryable_rate",
    ]) if out_rows else pd.DataFrame(columns=[
        "batch_id", "provider", "total_tasks", "success_tasks",
        "failed_tasks", "empty_tasks", "retryable_tasks",
        "failure_rate", "empty_rate", "retryable_rate",
    ])
    return df


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    """Tiny read-only CLI for ad-hoc inspection (no execution side effects)."""
    import argparse
    p = argparse.ArgumentParser(description="V1.4.9 Batch failure governance (read-only)")
    p.add_argument("--batch-id", default=None, help="Filter failed/empty tasks by batch")
    p.add_argument("--status", default=None, choices=["failed", "empty"],
                   help="Filter tasks by status")
    p.add_argument("--retryable-only", action="store_true",
                   help="Restrict to retryable tasks")
    p.add_argument("--limit", type=int, default=50, help="Max batches to list")
    args = p.parse_args()

    print(f"\n{'='*60}\n  Batch Failure Governance (read-only)\n{'='*60}")

    batches = list_batches_with_coverage(limit=args.limit)
    print(f"\nBatches: {len(batches)}")
    for b in batches[:10]:
        print(f"  {b['batch_id']} | {b['universe_name']} | status={b['status']} "
              f"failed={b['failed_tasks']} retryable={b['retryable_tasks']}")

    if args.batch_id or args.status or args.retryable_only:
        tasks = list_failed_tasks(
            batch_id=args.batch_id, status=args.status,
            retryable_only=args.retryable_only,
        )
        print(f"\nFailed/empty tasks: {len(tasks)}")
        for t in tasks[:20]:
            mark = "R" if t["retryable"] else "-"
            print(f"  [{mark}] {t['batch_id']} task={t['task_id']} {t['ts_code']} "
                  f"{t['status']} {t['error_category']}  {t['retry_reason']}")

        if args.batch_id:
            print("\nProvider failure:")
            print(compute_provider_failure([args.batch_id]).to_string(index=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
