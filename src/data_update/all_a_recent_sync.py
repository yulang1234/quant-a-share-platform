"""V1.5.7 Unified all-A recent sync entry point.

Recommended daily workflow for syncing all A-stock data.

Usage::

    # Preview
    python -m src.data_update.all_a_recent_sync --recent-days 30 --adj qfq --dry-run

    # Plan only (write tasks)
    python -m src.data_update.all_a_recent_sync --recent-days 30 --adj qfq --plan-only --confirm

    # Run a batch
    python -m src.data_update.all_a_recent_sync --recent-days 30 --adj qfq --run --batch-size 50 --confirm --save-local
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from typing import Any


def sync_all_a_recent(
    recent_days: int = 30,
    adj: str = "qfq",
    batch_size: int = 50,
    dry_run: bool = True,
    plan_only: bool = False,
    run: bool = False,
    save_local: bool = False,
    sleep: float = 1.0,
    stop_on_failed_rate: bool = True,
    max_failed_rate: float = 0.3,
) -> dict[str, Any]:
    """Sync all A-stock recent data.

    Args:
        recent_days: Number of recent trading days to sync.
        adj: 'raw', 'qfq', or 'all'.
        batch_size: Tasks per batch execution.
        dry_run: Preview only.
        plan_only: Only create batch plan, don't execute.
        run: Execute a batch after planning.
        save_local: Save data locally.
        sleep: Sleep seconds between requests.
        stop_on_failed_rate: Stop if failure rate exceeds max.
        max_failed_rate: Maximum allowed failure rate.

    Returns:
        Summary dict.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=recent_days + 10)  # buffer

    summary: dict[str, Any] = {
        "status": "dry_run" if dry_run else "ok",
        "universe": "universe_all_a",
        "recent_days": recent_days,
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
        "adj": adj,
        "version": "v1.5.7",
    }

    if dry_run:
        summary["message"] = (
            f"预览：将同步 universe_all_a 近 {recent_days} 天 {adj} 数据。"
            f"日期范围: {start_date} ~ {end_date}。"
            f"使用 --confirm 确认执行。"
        )
        return summary

    # ── Plan phase ──
    try:
        from src.backfill.batch_planner import plan_batch
        plan_result = plan_batch(
            universe_name="universe_all_a",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adj=adj,
            split="none",
            limit=batch_size,
            dry_run=False,
            allow_core_500_plan=True,  # all_a now allowed
        )
    except Exception as e:
        return {**summary, "status": "error", "message": f"Plan failed: {e}"}

    batch_id = plan_result.get("batch_id", "")
    task_count = plan_result.get("task_count", 0)
    summary["batch_id"] = batch_id
    summary["task_count"] = task_count

    if plan_only:
        summary["message"] = f"任务已生成: batch_id={batch_id}, tasks={task_count}"
        return summary

    # ── Run phase ──
    if run and batch_id:
        try:
            from src.backfill.batch_runner import run_batch
            run_result = run_batch(
                batch_id=batch_id,
                limit=batch_size,
                dry_run=False,
                save_local=save_local,
                sleep=sleep,
                stop_on_failed_rate=stop_on_failed_rate,
                max_failed_rate=max_failed_rate,
            )
            summary["run_result"] = run_result
            summary["message"] = f"Batch {batch_id}: {run_result.get('success',0)} ok, {run_result.get('failed',0)} failed"
        except Exception as e:
            summary["run_error"] = str(e)

    return summary


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="V1.5.7 All-A Recent Sync")
    p.add_argument("--recent-days", type=int, default=30, help="Recent trading days (default: 30)")
    p.add_argument("--adj", default="qfq", choices=["raw", "qfq", "all"])
    p.add_argument("--batch-size", type=int, default=50, help="Tasks per batch")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--plan-only", action="store_true", help="Only create plan")
    p.add_argument("--run", action="store_true", help="Execute batch")
    p.add_argument("--save-local", action="store_true", help="Save data locally")
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--no-stop-on-failed", action="store_true")
    p.add_argument("--max-failed-rate", type=float, default=0.3)
    args = p.parse_args()

    dry_run = not args.confirm

    result = sync_all_a_recent(
        recent_days=args.recent_days,
        adj=args.adj,
        batch_size=args.batch_size,
        dry_run=dry_run,
        plan_only=args.plan_only,
        run=args.run,
        save_local=args.save_local,
        sleep=args.sleep,
        stop_on_failed_rate=not args.no_stop_on_failed,
        max_failed_rate=args.max_failed_rate,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
