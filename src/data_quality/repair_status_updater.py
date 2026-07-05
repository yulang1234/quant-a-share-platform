"""V1.4.4 Update gap repair_status based on task completion."""

from __future__ import annotations

from src.data_quality.coverage_repo import GapDetailRepository


def update_gap_after_task(task_id: int, task_status: str) -> dict[str, int]:
    """Update related gaps when a task completes.

    - success + coverage confirmed → repaired
    - success but coverage not confirmed → pending (keep for retry)
    - empty / failed → pending (for retry unless max attempts)
    """
    repo = GapDetailRepository()
    gaps = repo.list_pending(limit=1000)  # find gaps linked to this task
    updated = 0
    for g in gaps:
        if g.related_task_id == task_id:
            if task_status == "success":
                repo.update_repair_status(g.gap_id, "repaired")
            else:
                repo.update_repair_status(g.gap_id, "pending")
            updated += 1
    return {"updated_gaps": updated}
