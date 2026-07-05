"""V1.4.2 Task statistics CLI."""

import sys


def main() -> int:
    from src.data_tasks.task_repo import DataLoadTaskRepository
    repo = DataLoadTaskRepository()
    counts = repo.count_by_status()

    if not counts:
        print("No tasks found.")
        return 0

    print(f"{'Status':<12} {'Count':>8}")
    print("-" * 22)
    for status in ["pending", "running", "success", "failed", "empty", "skipped"]:
        cnt = counts.get(status, 0)
        print(f"{status:<12} {cnt:>8}")
    print("-" * 22)
    print(f"{'TOTAL':<12} {sum(counts.values()):>8}")

    errors = repo.top_errors(limit=5)
    if errors:
        print()
        print("Top errors:")
        for msg, cnt in errors:
            print(f"  {cnt:>4}  {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
