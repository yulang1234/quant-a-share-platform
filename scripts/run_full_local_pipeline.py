"""Run the full local quant data pipeline without sample limits.

This script intentionally does not pass ``--limit`` to any downstream CLI.
It fetches historical data, writes local DuckDB/Parquet data, and then rebuilds
the derived research tables in dependency order.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"

SCORE_MODELS = [
    "momentum_quality_score",
    "trend_volume_score",
    "low_vol_stable_score",
]

STRATEGIES = [
    "single_return_20d_top20",
    "single_momentum_20d_top20",
    "multi_momentum_quality_top20",
    "low_vol_momentum_top20",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full local A-share data, factor, strategy, and backtest pipeline.",
    )
    parser.add_argument("--pool", default="core_500", help="Stock pool name.")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD, optional.")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD, optional.")
    parser.add_argument(
        "--historical-adj",
        choices=["raw", "qfq", "all"],
        default="all",
        help="Historical data adjustment type. Default: all.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.8,
        help="Seconds to sleep between AkShare requests. Default: 0.8.",
    )
    parser.add_argument(
        "--skip-historical",
        action="store_true",
        help="Skip AkShare historical download and only rebuild derived local tables.",
    )
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip data quality report.",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip factor effectiveness analysis.",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Skip TopK backtest and evaluation.",
    )
    parser.add_argument(
        "--stop-streamlit",
        action="store_true",
        help="Stop a running Streamlit app for this project before writing DuckDB.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue remaining steps after a failed step.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation for a real full local run.",
    )
    return parser.parse_args()


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def dated_args(args: argparse.Namespace) -> list[str]:
    items: list[str] = []
    if args.start_date:
        items += ["--start-date", args.start_date]
    if args.end_date:
        items += ["--end-date", args.end_date]
    return items


def run_step(name: str, cmd: list[str], log_file: Path) -> bool:
    started = datetime.now()
    printable = " ".join(cmd)
    print()
    print("=" * 80)
    print(f"[START] {name}")
    print(printable)
    print("=" * 80)

    with log_file.open("a", encoding="utf-8") as log:
        log.write("\n" + "=" * 80 + "\n")
        log.write(f"[START] {started.isoformat(timespec='seconds')} {name}\n")
        log.write(printable + "\n")
        log.flush()

        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=build_env(),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log.write(proc.stdout)
        log.write(f"\n[EXIT] code={proc.returncode}\n")

    if proc.stdout:
        print(proc.stdout)

    elapsed = (datetime.now() - started).total_seconds()
    if proc.returncode == 0:
        print(f"[OK] {name} finished in {elapsed:.1f}s")
        return True

    print(f"[FAILED] {name} exited with code {proc.returncode} after {elapsed:.1f}s")
    print(f"Log file: {log_file}")
    return False


def stop_streamlit_for_project() -> None:
    if os.name != "nt":
        print("[WARN] --stop-streamlit is only implemented for Windows in this script.")
        return

    root = str(ROOT).replace("'", "''")
    ps = f"""
$root = '{root}'
Get-CimInstance Win32_Process |
    Where-Object {{
        $_.CommandLine -like '*streamlit*' -and
        $_.CommandLine -like '*streamlit_app.py*' -and
        ($_.CommandLine -like "*$root*" -or $_.CommandLine -like '*ui\\streamlit_app.py*')
    }} |
    ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    print("[OK] Requested Streamlit stop for this project.")


def main() -> int:
    args = parse_args()

    if not args.yes:
        print("This is a real full local run.")
        print("It can request AkShare, write DuckDB, write Parquet, and take a long time.")
        print("Re-run with --yes when you are ready.")
        return 2

    if args.stop_streamlit:
        stop_streamlit_for_project()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"full_local_pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"

    py = sys.executable
    date_args = dated_args(args)

    steps: list[tuple[str, list[str]]] = []
    steps.append(("Environment and database summary", [py, "main.py"]))

    if not args.skip_historical:
        steps.append(
            (
                "Full historical data download",
                [
                    py,
                    "-m",
                    "src.data_update.historical_loader",
                    "--pool",
                    args.pool,
                    "--adj",
                    args.historical_adj,
                    "--sleep",
                    str(args.sleep),
                    *date_args,
                ],
            )
        )

    if not args.skip_quality:
        steps.append(
            (
                "Data quality report",
                [py, "-m", "src.data_quality.quality_report", "--adj", "all"],
            )
        )

    steps.extend(
        [
            (
                "Basic factor calculation",
                [
                    py,
                    "-m",
                    "src.factors.run_factor_calculation",
                    "--pool",
                    args.pool,
                    *date_args,
                ],
            ),
            (
                "Factor standardization and ranking",
                [
                    py,
                    "-m",
                    "src.factor_rank.run_factor_ranking",
                    "--pool",
                    args.pool,
                    *date_args,
                ],
            ),
        ]
    )

    if not args.skip_analysis:
        steps.append(
            (
                "Factor effectiveness analysis",
                [
                    py,
                    "-m",
                    "src.factor_analysis.run_factor_analysis",
                    "--pool",
                    args.pool,
                    *date_args,
                ],
            )
        )

    for model in SCORE_MODELS:
        steps.append(
            (
                f"Multi-factor scoring: {model}",
                [py, "-m", "src.scoring.run_scoring", "--model", model, *date_args],
            )
        )

    for strategy in STRATEGIES:
        steps.append(
            (
                f"TopK strategy: {strategy}",
                [py, "-m", "src.strategy.run_topk_strategy", "--strategy", strategy, *date_args],
            )
        )

    if not args.skip_backtest:
        for strategy in STRATEGIES:
            backtest_name = f"{strategy}_bt"
            steps.append(
                (
                    f"Backtest: {backtest_name}",
                    [
                        py,
                        "-m",
                        "src.backtest.run_backtest",
                        "--strategy",
                        strategy,
                        "--backtest-name",
                        backtest_name,
                        *date_args,
                    ],
                )
            )
            steps.append(
                (
                    f"Backtest evaluation: {backtest_name}",
                    [
                        py,
                        "-m",
                        "src.backtest_evaluation.run_backtest_evaluation",
                        "--backtest-name",
                        backtest_name,
                        *date_args,
                    ],
                )
            )

    failed: list[str] = []
    for name, cmd in steps:
        ok = run_step(name, cmd, log_file)
        if not ok:
            failed.append(name)
            if not args.keep_going:
                break

    print()
    print("=" * 80)
    print("Full local pipeline summary")
    print("=" * 80)
    print(f"Log file: {log_file}")
    if failed:
        print("[FAILED] Steps:")
        for item in failed:
            print(f"  - {item}")
        return 1

    print("[OK] All requested steps finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
