"""
Tests for quality_report.py — verifies orchestration, DB writes, queries and CLI.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_quality.quality_report import (
    get_quality_issue_summary,
    get_recent_quality_issues,
    main,
    run_data_quality_checks,
)
from src.storage.duckdb_repo import (
    count_quality_issues,
    get_connection,
    upsert_daily_data,
)
from src.universe.stock_pool import add_stock_to_pool


def _to_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert string trade_date values to ``datetime.date`` for DuckDB."""
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _prepare_qfq_table_without_pk() -> None:
    """Recreate ``stock_daily_qfq`` without a primary key so duplicates can exist."""
    con = get_connection()
    con.execute("DROP TABLE IF EXISTS stock_daily_qfq")
    con.execute(
        """
        CREATE TABLE stock_daily_qfq (
            stock_code      VARCHAR(6)   NOT NULL,
            trade_date      DATE         NOT NULL,
            open            DECIMAL(12,2),
            high            DECIMAL(12,2),
            low             DECIMAL(12,2),
            close           DECIMAL(12,2),
            volume          BIGINT,
            amount          DECIMAL(16,2),
            pct_change      DECIMAL(8,4),
            turnover_rate   DECIMAL(8,4),
            data_source     VARCHAR(16)  DEFAULT 'akshare',
            created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _seed_stock_pool() -> None:
    """Insert a few test stocks into the active pool."""
    for code, name in [("000001", "A"), ("000002", "B"), ("000003", "C")]:
        add_stock_to_pool(stock_code=code, stock_name=name)


def _raw_row(stock_code: str, trade_date: str, close: float = 10.5) -> dict:
    return {
        "stock_code": stock_code,
        "trade_date": trade_date,
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": close,
        "pre_close": 10.0,
        "volume": 1000,
        "amount": 10500.0,
        "amplitude": 0.05,
        "pct_change": 0.01,
        "change_amount": 0.5,
        "turnover_rate": 0.02,
    }


def _seed_duplicate_in_qfq() -> None:
    """Create a duplicate record in stock_daily_qfq."""
    df = pd.DataFrame(
        [
            {
                "stock_code": "000002",
                "trade_date": "2024-01-01",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000,
                "amount": 10500.0,
                "pct_change": 0.01,
                "turnover_rate": 0.02,
            }
        ]
    )
    upsert_daily_data("stock_daily_qfq", _to_trade_dates(df))
    con = get_connection()
    con.execute(
        """
        INSERT INTO stock_daily_qfq
        (stock_code, trade_date, open, high, low, close, volume, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["000002", "2024-01-01", 10.0, 11.0, 9.5, 10.5, 1000, 10500.0],
    )


class TestQualityReport:
    def test_raw_only(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        summary = run_data_quality_checks(adj="raw", write_to_db=False, limit=1)
        assert summary["checked_stocks"] == 1
        assert summary["total_issues"] == 1
        assert summary["price_issues"] == 1
        assert summary["raw_issues"] == 1
        assert summary["qfq_issues"] == 0

    def test_qfq_only(self, fresh_db) -> None:
        _seed_stock_pool()
        _prepare_qfq_table_without_pk()
        _seed_duplicate_in_qfq()
        summary = run_data_quality_checks(adj="qfq", write_to_db=False, limit=2)
        assert summary["checked_stocks"] == 2
        assert summary["total_issues"] == 1
        assert summary["duplicate_issues"] == 1
        assert summary["qfq_issues"] == 1
        assert summary["raw_issues"] == 0

    def test_all_modes(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=0.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        _prepare_qfq_table_without_pk()
        _seed_duplicate_in_qfq()
        summary = run_data_quality_checks(adj="all", write_to_db=False, limit=2)
        assert summary["checked_stocks"] == 2
        assert summary["total_issues"] == 2
        assert summary["price_issues"] == 1
        assert summary["duplicate_issues"] == 1
        assert summary["raw_issues"] == 1
        assert summary["qfq_issues"] == 1

    def test_no_write(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        before = count_quality_issues()
        summary = run_data_quality_checks(adj="raw", write_to_db=False, limit=1)
        after = count_quality_issues()
        assert summary["total_issues"] == 1
        assert before == after == 0

    def test_write_to_db(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        summary = run_data_quality_checks(adj="raw", write_to_db=True, limit=1)
        assert summary["total_issues"] == 1
        assert count_quality_issues() == 1
        assert count_quality_issues(issue_type="price_anomaly") == 1

    def test_summary_correct(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame(
            [
                _raw_row("000001", "2024-01-01", close=-1.0),
                _raw_row("000001", "2024-01-02", close=-1.0),
            ]
        )
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        summary = run_data_quality_checks(adj="raw", write_to_db=False, limit=1)
        assert summary["total_issues"] == 2
        assert summary["price_issues"] == 2

    def test_recent_issues_query(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        run_data_quality_checks(adj="raw", write_to_db=True, limit=1)
        issues = get_recent_quality_issues(limit=10)
        assert len(issues) == 1
        assert issues.iloc[0]["stock_code"] == "000001"
        assert issues.iloc[0]["issue_type"] == "price_anomaly"

    def test_get_quality_issue_summary(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000001", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        run_data_quality_checks(adj="raw", write_to_db=True, limit=1)
        summary = get_quality_issue_summary()
        assert summary["total_open_issues"] == 1
        assert len(summary["by_type_adj"]) == 1
        assert summary["by_type_adj"][0]["issue_type"] == "price_anomaly"
        assert summary["by_type_adj"][0]["adj_type"] == "raw"

    def test_limit_respected(self, fresh_db) -> None:
        _seed_stock_pool()
        summary = run_data_quality_checks(adj="raw", write_to_db=False, limit=2)
        assert summary["checked_stocks"] == 2

    def test_stock_code_exact(self, fresh_db) -> None:
        _seed_stock_pool()
        df = pd.DataFrame([_raw_row("000003", "2024-01-01", close=-1.0)])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        summary = run_data_quality_checks(
            stock_code="000003", adj="raw", write_to_db=False, limit=1
        )
        assert summary["checked_stocks"] == 1
        assert summary["total_issues"] == 1


class TestQualityReportCli:
    def test_cli_output_ascii_safe(self, fresh_db, capsys) -> None:
        _seed_stock_pool()
        code = main(["--adj", "raw", "--limit", "5", "--no-write"])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.out.encode("ascii", errors="replace") == captured.out.encode(
            "ascii", errors="replace"
        )
        assert "Summary" in captured.out
        assert "Total issues" in captured.out

    def test_cli_invalid_adj(self, fresh_db, capsys) -> None:
        code = main(["--adj", "bad"])
        captured = capsys.readouterr()
        assert code == 1
        assert "[ERROR]" in captured.out
        assert "Invalid adj" in captured.out
