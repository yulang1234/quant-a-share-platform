"""V1.4.7 Batch service — batch lifecycle management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.backfill.batch_repo import BatchRepository


def generate_batch_id(universe_name: str, adj_type: str) -> str:
    """Generate a unique batch_id: bf_YYYYMMDD_HHMMSS_{universe}_{adj}."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uni = str(universe_name).replace(" ", "_")[:30]
    adj = str(adj_type)[:8]
    return f"bf_{ts}_{uni}_{adj}"


def create_batch_plan(
    universe_name: str,
    adj_type: str,
    start_date: str,
    end_date: str,
    split: str = "yearly",
    batch_name: str | None = None,
    planned_task_count: int = 0,
    limit: int = 20,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Create a batch record in planned status. Returns batch info dict."""
    repo = BatchRepository()

    if batch_id is None:
        batch_id = generate_batch_id(universe_name, adj_type)

    if batch_name is None:
        batch_name = f"{universe_name} {adj_type} {start_date}-{end_date}"

    batch = repo.create_batch(
        batch_id=batch_id,
        batch_name=batch_name,
        universe_name=universe_name,
        adj_type=adj_type,
        start_date=start_date,
        end_date=end_date,
        split=split,
        planned_task_count=planned_task_count,
        status="planned",
        max_limit=limit,
    )

    return {
        "batch_id": batch.batch_id,
        "batch_name": batch.batch_name,
        "universe_name": batch.universe_name,
        "status": batch.status,
    }


def mark_tasks_written(batch_id: str, written_count: int) -> None:
    """Update batch status to tasks_written."""
    repo = BatchRepository()
    repo.update_batch_status(
        batch_id, "tasks_written",
        written_task_count=written_count,
    )


def mark_running(batch_id: str) -> None:
    repo = BatchRepository()
    repo.update_batch_status(batch_id, "running", started_at=datetime.now())


def update_batch_results(batch_id: str, results: dict[str, int]) -> None:
    """Update batch counts after execution."""
    repo = BatchRepository()
    counts = {
        "success_count": results.get("success", 0),
        "failed_count": results.get("failed", 0),
        "empty_count": results.get("empty", 0),
        "skipped_count": results.get("skipped", 0),
    }
    repo.update_batch_counts(batch_id, **counts)

    # Determine status
    b = repo.get_batch(batch_id)
    if b:
        failed = (b.failed_count or 0)
        success = (b.success_count or 0)
        if failed > 0 and success > 0:
            new_status = "partial_success"
        elif failed > 0 and success == 0:
            new_status = "failed"
        elif success > 0:
            new_status = "success"
        else:
            new_status = b.status
        repo.update_batch_status(batch_id, new_status, finished_at=datetime.now())


def record_snapshot(
    batch_id: str,
    snapshot_type: str,
    report: dict[str, Any],
) -> dict[str, Any] | None:
    """Record a before/after coverage snapshot. Returns snapshot info or None on failure."""
    try:
        repo = BatchRepository()
        snap = repo.create_snapshot(
            batch_id=batch_id,
            snapshot_type=snapshot_type,
            universe_name=report.get("universe", ""),
            adj_type=report.get("adj_type", ""),
            start_date=report.get("start_date", ""),
            end_date=report.get("end_date", ""),
            stock_count=report.get("stock_count", 0),
            complete_count=report.get("complete_count", 0),
            partial_count=report.get("partial_count", 0),
            empty_count=report.get("empty_count", 0),
            calendar_missing_count=report.get("calendar_missing_count", 0),
            avg_coverage_rate=report.get("avg_coverage_rate"),
            min_coverage_rate=report.get("min_coverage_rate"),
            max_coverage_rate=report.get("max_coverage_rate"),
            calendar_source=report.get("calendar_source", "unknown"),
            is_real_calendar=report.get("is_real_calendar", False),
        )
        return {
            "snapshot_id": snap.snapshot_id,
            "snapshot_type": snap.snapshot_type,
            "avg_coverage_rate": snap.avg_coverage_rate,
        }
    except Exception as e:
        return {"error": str(e)}
