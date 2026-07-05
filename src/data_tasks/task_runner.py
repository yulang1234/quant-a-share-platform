"""V1.4.2 Task runner — execute pending data_load_tasks."""

from __future__ import annotations

import sys
import time
from datetime import datetime


def run_tasks(
    limit: int = 5,
    status_filter: str = "pending",
    adj_filter: str = "all",
    no_save: bool = True,
    save_local: bool = False,
    confirm: bool = False,
    sleep_seconds: float = 1.0,
    provider_name: str | None = None,
) -> dict[str, int]:
    from src.data_tasks.task_repo import DataLoadTaskRepository, DataLoadTaskLogRepository
    from src.data_tasks.retry_policy import calculate_next_retry

    task_repo = DataLoadTaskRepository()
    log_repo = DataLoadTaskLogRepository()
    svc = None

    tasks = task_repo.list_pending(limit=limit, status=status_filter)
    if not tasks:
        return {"total": 0, "success": 0, "failed": 0, "empty": 0, "skipped": 0}

    result = {"total": len(tasks), "success": 0, "failed": 0, "empty": 0, "skipped": 0}

    for task in tasks:
        if adj_filter != "all" and task.adj_type != adj_filter:
            result["skipped"] += 1
            continue

        if not confirm:
            print(f"[DRY-RUN] {task.symbol}.{task.exchange} {task.data_type} {task.adj_type} {task.start_date}-{task.end_date}")
            result["skipped"] += 1
            continue

        status_before = task.status
        t0 = time.time()
        try:
            if svc is None:
                from src.data_sources.market_data_service import MarketDataService
                svc = MarketDataService()
            df, prov = svc.get_daily_bars(
                f"{task.symbol}.{task.exchange}",
                str(task.start_date)[:10] if task.start_date else "20060101",
                str(task.end_date)[:10] if task.end_date else "20261231",
                task.adj_type or "raw",
            )
            elapsed = int((time.time() - t0) * 1000)
            if df is not None and not df.empty:
                task_repo.update_status(task.task_id, "success", row_count=len(df),
                                        attempt_count=task.attempt_count + 1,
                                        last_attempt_at=datetime.now())
                log_repo.log(task.task_id, status_before, "success", provider_used=prov,
                             row_count=len(df), duration_ms=elapsed)
                result["success"] += 1
            else:
                task_repo.update_status(task.task_id, "empty", attempt_count=task.attempt_count + 1,
                                        last_attempt_at=datetime.now())
                log_repo.log(task.task_id, status_before, "empty", provider_used=prov, duration_ms=elapsed)
                result["empty"] += 1
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            new_attempts = task.attempt_count + 1
            next_retry = calculate_next_retry(new_attempts)
            task_repo.update_status(task.task_id, "failed" if next_retry is None else "pending",
                                    attempt_count=new_attempts, next_retry_at=next_retry,
                                    error_type=type(e).__name__, error_message=str(e)[:500],
                                    last_attempt_at=datetime.now())
            log_repo.log(task.task_id, status_before, "failed", error_type=type(e).__name__,
                         error_message=str(e)[:500], duration_ms=elapsed)
            result["failed"] += 1

        time.sleep(sleep_seconds)

    return result


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.2 Task Runner")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--status", default="pending")
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--no-save", action="store_true", default=True)
    p.add_argument("--save-local", action="store_true", default=False)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--sleep", type=float, default=1.0)
    args = p.parse_args()

    if not args.confirm:
        print("[DRY-RUN MODE] Use --confirm to execute real tasks.\n")

    result = run_tasks(
        limit=args.limit, confirm=args.confirm,
        status_filter=args.status, adj_filter=args.adj,
        no_save=args.no_save, save_local=args.save_local,
        sleep_seconds=args.sleep,
    )
    print(f"\n--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
