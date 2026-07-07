"""V1.4.10 Data Quality Dashboard — read-only health checks across the
data substrate (coverage / calendar / security master / provider / batch /
storage). Aggregated into a single ``build_quality_overview`` summary.

Design
------
* Strictly read-only. No writes, no network, no batch_runner calls, no
  coverage scans. Coverage numbers are read from the already-persisted
  ``data_coverage_report`` table; "no scan yet" universes surface as
  ``coverage_level="unknown"``.
* Graceful degradation: each ``load_*`` helper wraps its body in
  try/except and returns an "unknown" / empty result on any error so a
  single failing submodule never blanks out the whole dashboard.
* Reuses existing repositories and V1.4.9 ``batch_failure`` helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

import pandas as pd


# ── Status vocabularies ─────────────────────────────────────────────────────

COVERAGE_LEVELS = (
    "healthy",          # coverage_rate >= 0.95 and gaps are minor
    "usable_with_gaps", # 0.80 <= rate < 0.95
    "risky",            # 0.50 <= rate < 0.80
    "not_recommended",  # rate < 0.50
    "unknown",          # no scan data
)

# Sub-module health states.
HEALTH_HEALTHY = "healthy"
HEALTH_USABLE = "usable_with_gaps"
HEALTH_RISKY = "risky"
HEALTH_NOT_RECOMMENDED = "not_recommended"
HEALTH_UNAVAILABLE = "unavailable"
HEALTH_UNKNOWN = "unknown"

# Overall dashboard statuses (four buckets + unknown).
OVERALL_HEALTHY = "healthy"
OVERALL_USABLE = "usable_with_gaps"
OVERALL_RISKY = "risky"
OVERALL_NOT_RECOMMENDED = "not_recommended"

# Default universes the dashboard tracks. Other universes are still shown
# when present in coverage_report rows, but these always get a row even
# with no scan data (so the user sees "unknown" rather than nothing).
DEFAULT_UNIVERSES: tuple[str, ...] = ("core_50", "core_100", "core_500")

# DuckDB tables surfaced in the storage-health panel. Each entry is
# (table_name, label, has_trade_date). ``has_trade_date`` controls whether
# we also fetch MIN/MAX(trade_date).
QUALITY_TABLES: tuple[tuple[str, str, bool], ...] = (
    ("stock_pool", "股票池", False),
    ("stock_daily_raw", "不复权日线", True),
    ("stock_daily_qfq", "前复权日线", True),
    ("data_update_log", "更新日志", False),
    ("data_quality_report", "质量报告", True),
    ("stock_daily_factors", "基础因子", True),
    ("stock_factor_rank", "因子排名", True),
    ("factor_analysis_summary", "因子分析", False),
    ("strategy_selection_result", "候选股票", False),
    ("backtest_equity_curve", "回测曲线", True),
    ("stock_composite_score", "综合评分", True),
)


# ── Coverage helpers ───────────────────────────────────────────────────────

def _coverage_level(rate: float | None) -> str:
    """Map a coverage rate to a quality bucket."""
    if rate is None:
        return "unknown"
    if rate >= 0.95:
        return "healthy"
    if rate >= 0.80:
        return "usable_with_gaps"
    if rate >= 0.50:
        return "risky"
    return "not_recommended"


def load_coverage_summary(
    universe_names: Sequence[str] | None = None,
    adj_types: Sequence[str] | None = None,
    coverage_level: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate persisted coverage rows by (universe_name, adj_type).

    Reads ``data_coverage_report`` via :class:`CoverageReportRepository`
    (read-only ``list_all``) and resolves ``universe_id -> universe_name``
    via :class:`UniverseRepository`. Universes in :data:`DEFAULT_UNIVERSES`
    with no scan rows still appear, with ``coverage_level="unknown"``.

    Each returned row contains: universe_name, data_type (raw/qfq),
    expected_count, actual_count, missing_count, coverage_rate,
    coverage_level, last_scan_time, report_path.
    """
    out: list[dict[str, Any]] = []
    try:
        from src.data_quality.coverage_repo import CoverageReportRepository
        from src.repositories.universe_repo import UniverseRepository

        # universe_id -> universe_name
        uid_to_name: dict[int, str] = {}
        known_names: set[str] = set()
        for u in UniverseRepository().list_universes():
            uid_to_name[u.universe_id] = u.universe_name
            known_names.add(u.universe_name)

        reports = CoverageReportRepository().list_all(limit=5000)
        # Group by (universe_name, adj_type)
        agg: dict[tuple[str, str], dict[str, Any]] = {}
        for r in reports:
            uni_name = uid_to_name.get(r.universe_id) if r.universe_id is not None else None
            adj = (r.adj_type or "").lower() or "unknown"
            key = (uni_name or "未知_universe", adj)
            bucket = agg.setdefault(key, {
                "expected": 0, "actual": 0, "missing": 0,
                "samples": 0, "last_scan": None,
            })
            bucket["expected"] += int(r.expected_trade_days or 0)
            bucket["actual"] += int(r.actual_trade_days or 0)
            bucket["missing"] += int(r.missing_trade_days or 0)
            bucket["samples"] += 1
            if r.generated_at and (bucket["last_scan"] is None
                                   or r.generated_at > bucket["last_scan"]):
                bucket["last_scan"] = r.generated_at

        # Build output rows for known + DEFAULT universes
        names_to_show = (
            list(universe_names) if universe_names
            else sorted(known_names | set(DEFAULT_UNIVERSES))
        )
        for uni_name in names_to_show:
            for adj in ("raw", "qfq"):
                if adj_types and adj not in adj_types:
                    continue
                bucket = agg.get((uni_name, adj))
                if bucket is None:
                    row = {
                        "universe_name": uni_name, "data_type": adj,
                        "expected_count": 0, "actual_count": 0,
                        "missing_count": 0, "coverage_rate": None,
                        "coverage_level": "unknown",
                        "last_scan_time": None, "report_path": "-",
                    }
                else:
                    exp = bucket["expected"]
                    act = bucket["actual"]
                    rate = (act / exp) if exp > 0 else None
                    level = _coverage_level(rate)
                    row = {
                        "universe_name": uni_name, "data_type": adj,
                        "expected_count": exp, "actual_count": act,
                        "missing_count": bucket["missing"],
                        "coverage_rate": rate,
                        "coverage_level": level,
                        "last_scan_time": bucket["last_scan"],
                        "report_path": "-",
                    }
                if coverage_level and row["coverage_level"] != coverage_level:
                    continue
                out.append(row)
    except Exception:
        return out
    return out


# ── Calendar health ─────────────────────────────────────────────────────────

def load_calendar_health(lookback_days: int = 10) -> dict[str, Any]:
    """Inspect the trading calendar for completeness near "today".

    Returns a dict with calendar_source, min_trade_date, max_trade_date,
    total_trade_days, latest_trade_day, next_trade_day,
    missing_recent_days, is_recent_calendar_ready, health_status,
    issue_summary.
    """
    today = datetime.now().date()
    result: dict[str, Any] = {
        "calendar_source": None, "min_trade_date": None,
        "max_trade_date": None, "total_trade_days": 0,
        "latest_trade_day": None, "next_trade_day": None,
        "missing_recent_days": 0, "is_recent_calendar_ready": False,
        "health_status": HEALTH_UNKNOWN, "issue_summary": "暂无数据",
    }
    try:
        from sqlalchemy import func
        from src.db.schema_meta import TradingCalendar
        from src.repositories.meta_db import get_session
        from src.trading_calendar.trading_calendar_service import (
            TradingCalendarService,
        )

        info = TradingCalendarService().get_calendar_source_info("CN")
        result["calendar_source"] = info.get("calendar_source") or None

        s = get_session()
        open_q = s.query(TradingCalendar).filter(TradingCalendar.exchange == "CN",
                                                  TradingCalendar.is_open.is_(True))
        total = int(open_q.count())
        min_d = open_q.with_entities(func.min(TradingCalendar.trade_date)).scalar()
        max_d = open_q.with_entities(func.max(TradingCalendar.trade_date)).scalar()
        latest = s.query(TradingCalendar).filter(
            TradingCalendar.exchange == "CN",
            TradingCalendar.is_open.is_(True),
            TradingCalendar.trade_date <= today,
        ).order_by(TradingCalendar.trade_date.desc()).first()
        nxt = s.query(TradingCalendar).filter(
            TradingCalendar.exchange == "CN",
            TradingCalendar.is_open.is_(True),
            TradingCalendar.trade_date > today,
        ).order_by(TradingCalendar.trade_date.asc()).first()

        result["total_trade_days"] = total
        result["min_trade_date"] = min_d
        result["max_trade_date"] = max_d
        result["latest_trade_day"] = getattr(latest, "trade_date", None)
        result["next_trade_day"] = getattr(nxt, "trade_date", None)

        if total == 0:
            result["health_status"] = HEALTH_NOT_RECOMMENDED
            result["issue_summary"] = "交易日历为空"
            return result

        if not info.get("is_real_calendar", False):
            result["health_status"] = HEALTH_RISKY
            result["is_recent_calendar_ready"] = False
            result["issue_summary"] = (
                f"非真实交易日历（source={info.get('calendar_source') or 'none'}），"
                "覆盖率/补数判断可能不准"
            )
            return result

        # missing_recent_days: in the last `lookback_days` calendar days,
        # how many business open days are recorded.
        since = today - timedelta(days=lookback_days)
        recent_open = s.query(TradingCalendar).filter(
            TradingCalendar.exchange == "CN",
            TradingCalendar.is_open.is_(True),
            TradingCalendar.trade_date >= since,
            TradingCalendar.trade_date <= today,
        ).count()
        # Approx expected open days = ~60% of window for CN calendar.
        expected_recent = max(1, int(lookback_days * 0.6))
        missing = max(0, expected_recent - recent_open)
        result["missing_recent_days"] = int(missing)

        if latest is None:
            result["health_status"] = HEALTH_NOT_RECOMMENDED
            result["issue_summary"] = "今日之前最近一个开放日缺失"
            return result

        # If latest trade day more than 4 calendar days stale → risky
        latest_day = latest.trade_date
        if hasattr(latest_day, "date"):
            latest_day = latest_day.date()
        gap = (today - latest_day).days
        if missing == 0:
            result["health_status"] = HEALTH_HEALTHY
            result["is_recent_calendar_ready"] = True
            result["issue_summary"] = "最近交易日完整"
        elif gap <= 4 and missing <= 2:
            result["health_status"] = HEALTH_USABLE
            result["is_recent_calendar_ready"] = True
            result["issue_summary"] = f"最近 {lookback_days} 日缺 {missing} 个交易日（可容忍）"
        else:
            result["health_status"] = HEALTH_RISKY
            result["is_recent_calendar_ready"] = False
            result["issue_summary"] = f"最近 {lookback_days} 日缺 {missing} 个交易日"
    except Exception as e:
        result["issue_summary"] = f"读取失败: {type(e).__name__}"
    return result


# ── Security master health ──────────────────────────────────────────────────

def load_security_master_health() -> dict[str, Any]:
    """Aggregate security_master completeness (ST/delisted/suspended/fields)."""
    result: dict[str, Any] = {
        "total_securities": 0, "active_securities": 0,
        "delisted_securities": 0, "st_count": 0, "suspended_count": 0,
        "missing_name_count": 0, "missing_list_date_count": 0,
        "missing_delist_date_count": 0, "missing_exchange_count": 0,
        "missing_status_count": 0, "completeness_rate": None,
        "health_status": HEALTH_UNKNOWN, "issue_summary": "暂无数据",
    }
    try:
        from src.repositories.security_master_repo import SecurityMasterRepository
        repo = SecurityMasterRepository()
        rows = repo.list_all(limit=10000)
        total = int(repo.count() or 0)
        # Use ALL rows if list_all capped; otherwise count provides authoritative.
        total = max(total, len(rows))
        result["total_securities"] = total
        if total == 0:
            result["health_status"] = HEALTH_NOT_RECOMMENDED
            result["issue_summary"] = "证券主数据为空"
            return result

        active = delisted = st = suspended = 0
        miss_name = miss_list = miss_delist = miss_ex = miss_status = 0
        # Coverage of the 5 "essential" fields per row (used for completeness_rate).
        essential_cells = 0
        essential_total = 0
        for r in rows:
            if not getattr(r, "is_st", False) and not getattr(r, "is_st", None):
                pass
            if getattr(r, "status", None) == "active" or not getattr(r, "is_suspended", False):
                pass
            active += 1 if (getattr(r, "status", None) == "active"
                            and not getattr(r, "is_suspended", False)) else 0
            status = getattr(r, "status", None)
            if status == "delisted" or getattr(r, "delist_date", None) is not None:
                delisted += 1
            if getattr(r, "is_st", False):
                st += 1
            if getattr(r, "is_suspended", False):
                suspended += 1

            # Missing-field counters (only count when NULL).
            if not getattr(r, "security_name", None):
                miss_name += 1
            if getattr(r, "list_date", None) is None:
                miss_list += 1
            if getattr(r, "delist_date", None) is None and status == "delisted":
                miss_delist += 1
            if not getattr(r, "exchange", None):
                miss_ex += 1
            if not status:
                miss_status += 1

            # Completeness over essential fields.
            for ok in (
                bool(getattr(r, "security_name", None)),
                getattr(r, "list_date", None) is not None,
                bool(getattr(r, "exchange", None)),
                bool(status),
            ):
                essential_total += 1
                essential_cells += 1 if ok else 0

        result["active_securities"] = active
        result["delisted_securities"] = delisted
        result["st_count"] = st
        result["suspended_count"] = suspended
        result["missing_name_count"] = miss_name
        result["missing_list_date_count"] = miss_list
        result["missing_delist_date_count"] = miss_delist
        result["missing_exchange_count"] = miss_ex
        result["missing_status_count"] = miss_status
        result["completeness_rate"] = (
            essential_cells / essential_total if essential_total else None
        )
        comp = result["completeness_rate"]
        # Health decision.
        # Delist-date missing for delisted stock is a real integrity issue.
        integrity_issues = miss_delist + miss_status
        if comp is None or comp < 0.5:
            result["health_status"] = HEALTH_NOT_RECOMMENDED
            result["issue_summary"] = f"关键字段完整度仅 {comp or 0:.0%}，不可信"
        elif comp < 0.8 or integrity_issues > 0:
            result["health_status"] = HEALTH_RISKY
            result["issue_summary"] = f"关键字段缺失较多（complete={comp:.0%}，integrity_issues={integrity_issues}）"
        elif comp < 0.95:
            result["health_status"] = HEALTH_USABLE
            result["issue_summary"] = f"关键字段有小缺口（complete={comp:.0%}）"
        else:
            result["health_status"] = HEALTH_HEALTHY
            result["issue_summary"] = f"关键字段完整（complete={comp:.0%}）"
    except Exception as e:
        result["issue_summary"] = f"读取失败: {type(e).__name__}"
    return result


# ── Provider health ─────────────────────────────────────────────────────────

def _provider_health_status(
    failure_rate: float | None, recent_failure_rate: float | None,
    total_min: int = 5,
) -> str:
    """Map failure rates to a provider health status."""
    if failure_rate is None:
        return HEALTH_UNKNOWN
    if failure_rate >= 1.0:
        return HEALTH_UNAVAILABLE
    if failure_rate >= 0.5:
        return HEALTH_RISKY
    if failure_rate >= 0.3:
        return HEALTH_USABLE
    return HEALTH_HEALTHY


def load_provider_health() -> list[dict[str, Any]]:
    """Per-provider cross-batch failure aggregation + recent failure rate.

    Uses V1.4.9 ``compute_provider_failure`` over all known batch_ids, then
    collapses to provider-only totals. Recent failure rate comes from
    ``ui.components.provider_health_view.load_provider_stats`` (last ~1000
    call logs).
    """
    try:
        from src.backfill.batch_repo import BatchRepository
        from src.backfill.batch_failure import compute_provider_failure

        batches = BatchRepository().list_batches(limit=1000)
        batch_ids = [b.batch_id for b in batches]
        df = compute_provider_failure(batch_ids)
        if df.empty:
            # Fall back to recent call-log-only stats if no batch data.
            return _provider_health_from_call_log()
        # Collapse to provider totals.
        agg = df.groupby("provider", dropna=False).agg(
            total_tasks=("total_tasks", "sum"),
            success_tasks=("success_tasks", "sum"),
            failed_tasks=("failed_tasks", "sum"),
            empty_tasks=("empty_tasks", "sum"),
            retryable_tasks=("retryable_tasks", "sum"),
        ).reset_index()
        agg["failure_rate"] = (
            agg["failed_tasks"] / agg["total_tasks"].replace(0, pd.NA)
        )
        agg["empty_rate"] = (
            agg["empty_tasks"] / agg["total_tasks"].replace(0, pd.NA)
        )
        agg["retryable_rate"] = (
            agg["retryable_tasks"] / agg["total_tasks"].replace(0, pd.NA)
        )

        # Merge recent call-log stats for "recent_failure_rate".
        recent_map = _call_log_recent_failure_rate()
        rows: list[dict[str, Any]] = []
        for _, r in agg.iterrows():
            provider = (r["provider"] if pd.notna(r["provider"]) else "unknown")
            fr = float(r["failure_rate"]) if pd.notna(r["failure_rate"]) else None
            rr = float(r["retryable_rate"]) if pd.notna(r["retryable_rate"]) else None
            er = float(r["empty_rate"]) if pd.notna(r["empty_rate"]) else None
            recent_fr = recent_map.get(provider)
            status = _provider_health_status(fr, recent_fr)
            rows.append({
                "provider": provider,
                "total_tasks": int(r["total_tasks"]),
                "success_tasks": int(r["success_tasks"]),
                "failed_tasks": int(r["failed_tasks"]),
                "empty_tasks": int(r["empty_tasks"]),
                "retryable_tasks": int(r["retryable_tasks"]),
                "failure_rate": fr,
                "empty_rate": er,
                "retryable_rate": rr,
                "recent_failure_rate": recent_fr,
                "health_status": status,
                "suggested_action": _provider_action(status),
            })
        return rows
    except Exception:
        return []


def _call_log_recent_failure_rate(limit: int = 1000) -> dict[str, float | None]:
    """recent_failure_rate per provider from ProviderCallLog."""
    out: dict[str, float | None] = {}
    try:
        from src.repositories.provider_repo import ProviderCallLogRepository
        logs = ProviderCallLogRepository().recent(limit=limit)
        bucket: dict[str, dict[str, int]] = {}
        for l in logs:
            p = l.provider_name or "unknown"
            s = l.status or "unknown"
            b = bucket.setdefault(p, {"total": 0, "failed": 0})
            b["total"] += 1
            if s in ("failed",):
                b["failed"] += 1
        for p, b in bucket.items():
            out[p] = (b["failed"] / b["total"]) if b["total"] else None
    except Exception:
        pass
    return out


def _provider_health_from_call_log() -> list[dict[str, Any]]:
    """Fallback when no batch data exists — derive everything from call log."""
    try:
        from src.repositories.provider_repo import ProviderCallLogRepository
        logs = ProviderCallLogRepository().recent(limit=1000)
        if not logs:
            return []
        agg: dict[str, dict[str, int]] = {}
        for l in logs:
            p = l.provider_name or "unknown"
            s = l.status or "unknown"
            b = agg.setdefault(p, {"total": 0, "success": 0, "failed": 0,
                                   "empty": 0, "retryable": 0})
            b["total"] += 1
            if s == "success":
                b["success"] += 1
            elif s == "failed":
                b["failed"] += 1
            elif s == "empty":
                b["empty"] += 1
        rows = []
        for p, b in agg.items():
            total = b["total"]
            fr = b["failed"] / total if total else None
            rows.append({
                "provider": p, "total_tasks": total,
                "success_tasks": b["success"], "failed_tasks": b["failed"],
                "empty_tasks": b["empty"], "retryable_tasks": 0,
                "failure_rate": fr, "empty_rate": b["empty"] / total if total else None,
                "retryable_rate": None, "recent_failure_rate": fr,
                "health_status": _provider_health_status(fr, fr),
                "suggested_action": _provider_action(_provider_health_status(fr, fr)),
            })
        return rows
    except Exception:
        return []


def _provider_action(status: str) -> str:
    if status == HEALTH_HEALTHY:
        return "状态正常，无需操作"
    if status == HEALTH_USABLE:
        return "建议在「补数批次」tab 检查 retryable 任务"
    if status == HEALTH_RISKY:
        return "建议检查 Provider 稳定性，必要时降低 limit、增加 sleep"
    if status == HEALTH_UNAVAILABLE:
        return "Provider 当前不可用，建议排查并切换 Provider"
    return "暂无明确建议"


# ── Batch execution health ───────────────────────────────────────────────────

def load_batch_execution_health(recent_n: int = 5) -> dict[str, Any]:
    """Aggregate backfill batch execution health (read-only)."""
    result: dict[str, Any] = {
        "total_batches": 0, "success_batches": 0, "failed_batches": 0,
        "partial_batches": 0, "recent_batches": 0, "recent_failed_batches": 0,
        "total_tasks": 0, "failed_tasks": 0, "retryable_tasks": 0,
        "avg_failure_rate": None, "latest_batch_id": None,
        "latest_batch_status": None, "health_status": HEALTH_UNKNOWN,
        "issue_summary": "暂无数据",
    }
    try:
        from src.backfill.batch_failure import list_batches_with_coverage
        batches = list_batches_with_coverage(limit=500)
        batches = sorted(batches, key=lambda b: str(b.get("batch_id") or ""))
        batches = sorted(
            batches,
            key=lambda b: b.get("created_at") or datetime.min,
            reverse=True,
        )
        result["total_batches"] = len(batches)
        if not batches:
            result["health_status"] = HEALTH_UNKNOWN
            result["issue_summary"] = "暂无批次记录"
            return result
        success = sum(1 for b in batches if b["status"] == "success")
        failed = sum(1 for b in batches if b["status"] == "failed")
        partial = sum(1 for b in batches if b["status"] == "partial_success")
        total_t = int(sum(b.get("total_tasks") or 0 for b in batches))
        failed_t = int(sum(b.get("failed_tasks") or 0 for b in batches))
        retryable_t = int(sum(b.get("retryable_tasks") or 0 for b in batches))
        result["success_batches"] = success
        result["failed_batches"] = failed
        result["partial_batches"] = partial
        result["total_tasks"] = total_t
        result["failed_tasks"] = failed_t
        result["retryable_tasks"] = retryable_t
        result["avg_failure_rate"] = (
            failed_t / total_t if total_t > 0 else None
        )

        # Recent batches = top `recent_n` (list_batches_with_coverage is
        # ordered created_at desc).
        recent = batches[:recent_n]
        recent_failed = sum(1 for b in recent if b["status"] in ("failed", "partial_success"))
        result["recent_batches"] = len(recent)
        result["recent_failed_batches"] = recent_failed
        latest = batches[0] if batches else None
        if latest:
            result["latest_batch_id"] = latest["batch_id"]
            result["latest_batch_status"] = latest["status"]

        # Health decision.
        if latest and latest["status"] == "failed":
            result["health_status"] = HEALTH_RISKY
            result["issue_summary"] = f"最新批次 {latest['batch_id']} 失败"
        elif recent_failed >= recent_n and recent_n > 0:
            result["health_status"] = HEALTH_RISKY
            result["issue_summary"] = f"最近 {recent_n} 个批次多为失败"
        elif retryable_t > 0:
            result["health_status"] = HEALTH_USABLE
            result["issue_summary"] = f"存在 {retryable_t} 个可重试失败任务"
        elif success >= 1 and failed == 0:
            result["health_status"] = HEALTH_HEALTHY
            result["issue_summary"] = "执行健康"
        else:
            result["health_status"] = HEALTH_USABLE
            result["issue_summary"] = "有少量缺口"
    except Exception as e:
        result["issue_summary"] = f"读取失败: {type(e).__name__}"
    return result


# ── Storage health ───────────────────────────────────────────────────────────

def load_storage_health() -> list[dict[str, Any]]:
    """Inspect DuckDB tables and parquet directories (read-only).

    DuckDB: table row_count + min/max trade_date when applicable.
    Parquet: file_count + total_size_mb + best-effort min/max trade_date
    via pyarrow footer metadata.
    """
    out: list[dict[str, Any]] = []
    # DuckDB tables
    for table, label, has_tdate in QUALITY_TABLES:
        row = _inspect_duckdb_table(table, label, has_tdate)
        out.append(row)
    # Parquet dirs
    out.extend(_inspect_parquet_dirs())
    return out


def _inspect_duckdb_table(table: str, label: str, has_trade_date: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "storage_type": "duckdb", "object_name": table, "row_count": 0,
        "file_count": None, "total_size_mb": None,
        "min_date": None, "max_date": None, "last_modified": None,
        "health_status": HEALTH_UNKNOWN, "issue_summary": "暂无数据",
    }
    try:
        from src.storage.duckdb_repo import query_df
        # Table exists?
        exists = query_df(
            "SELECT COUNT(*) AS c FROM information_schema.tables "
            "WHERE table_name = ?", [table],
        )
        if exists.iloc[0, 0] == 0:
            row["health_status"] = HEALTH_UNKNOWN
            row["issue_summary"] = "表不存在（尚未初始化）"
            return row
        cnt = query_df(f"SELECT COUNT(*) AS c FROM {table}")
        n = int(cnt.iloc[0, 0]) if not cnt.empty else 0
        row["row_count"] = n
        min_d = max_d = None
        if has_trade_date:
            try:
                dr = query_df(
                    f"SELECT MIN(trade_date) AS mn, MAX(trade_date) AS mx FROM {table}"
                )
                if not dr.empty:
                    min_d = dr.iloc[0]["mn"]
                    max_d = dr.iloc[0]["mx"]
                    row["min_date"] = str(min_d)[:10] if min_d is not None else None
                    row["max_date"] = str(max_d)[:10] if max_d is not None else None
            except Exception:
                pass
        import os
        from config.settings import get_duckdb_path
        p = get_duckdb_path()
        row["last_modified"] = (
            datetime.fromtimestamp(os.path.getmtime(p)).isoformat()
            if os.path.exists(p) else None
        )
        if n == 0:
            row["health_status"] = HEALTH_RISKY
            row["issue_summary"] = "表为空"
        else:
            row["health_status"] = HEALTH_HEALTHY
            row["issue_summary"] = f"行数 {n:,}"
    except Exception as e:
        row["health_status"] = HEALTH_UNKNOWN
        row["issue_summary"] = f"读取失败: {type(e).__name__}"
    return row


def _inspect_parquet_dirs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        import os
        from config.settings import get_parquet_root
        root = get_parquet_root()
        for adj, sub in (("raw", "dwd/daily_raw"), ("qfq", "dwd/daily_qfq")):
            d = root / sub
            row = {
                "storage_type": "parquet", "object_name": sub,
                "row_count": None, "file_count": 0, "total_size_mb": 0.0,
                "min_date": None, "max_date": None, "last_modified": None,
                "health_status": HEALTH_UNKNOWN, "issue_summary": "暂无数据",
            }
            if not d.exists():
                row["health_status"] = HEALTH_UNKNOWN
                row["issue_summary"] = "目录不存在"
                rows.append(row)
                continue
            files = sorted(d.glob("*.parquet"))
            row["file_count"] = len(files)
            total_bytes = 0
            last_mtime = 0.0
            for f in files:
                total_bytes += f.stat().st_size
                last_mtime = max(last_mtime, f.stat().st_mtime)
            row["total_size_mb"] = round(total_bytes / 1024 / 1024, 2)
            if last_mtime:
                row["last_modified"] = datetime.fromtimestamp(last_mtime).isoformat()
            if not files:
                row["health_status"] = HEALTH_RISKY
                row["issue_summary"] = "目录为空"
            else:
                row["health_status"] = HEALTH_HEALTHY
                row["issue_summary"] = f"{len(files)} 个 parquet 文件，{row['total_size_mb']} MB"
                # best-effort min/max trade_date via pyarrow footer
                try:
                    min_d, max_d = _parquet_min_max(files[:200])
                    row["min_date"] = min_d
                    row["max_date"] = max_d
                except Exception:
                    pass
            rows.append(row)
    except Exception:
        pass
    return rows


def _parquet_min_max(files: list) -> tuple[str | None, str | None]:
    """Best-effort min/max trade_date from parquet file metadata."""
    try:
        import pyarrow.parquet as pq
    except Exception:
        return None, None
    mn: str | None = None
    mx: str | None = None
    for f in files:
        try:
            pf = pq.ParquetFile(str(f))
            md = pf.metadata
            # Walk row-group statistics for a 'trade_date' column.
            for i in range(md.num_row_groups):
                rg = md.row_group(i)
                for j in range(rg.num_columns):
                    col = rg.column(j)
                    name = col.path_in_schema
                    if "trade_date" not in name:
                        continue
                    stats = col.statistics
                    if stats is None:
                        continue
                    lo = stats.min
                    hi = stats.max
                    if lo is not None:
                        s = str(lo)[:10]
                        if mn is None or s < mn:
                            mn = s
                    if hi is not None:
                        s = str(hi)[:10]
                        if mx is None or s > mx:
                            mx = s
        except Exception:
            continue
    return mn, mx


# ── Overall overview ─────────────────────────────────────────────────────────

def build_quality_overview() -> dict[str, Any]:
    """Aggregate all checks into a single dashboard overview dict.

    Returns keys: overall_status, overall_score, status_reason,
    coverage_status, calendar_status, security_master_status,
    provider_status, batch_status, storage_status, top_issues,
    suggested_next_actions, generated_at.
    """
    overview: dict[str, Any] = {
        "overall_status": HEALTH_UNKNOWN,
        "overall_score": None,
        "status_reason": "",
        "coverage_status": HEALTH_UNKNOWN,
        "calendar_status": HEALTH_UNKNOWN,
        "security_master_status": HEALTH_UNKNOWN,
        "provider_status": HEALTH_UNKNOWN,
        "batch_status": HEALTH_UNKNOWN,
        "storage_status": HEALTH_UNKNOWN,
        "top_issues": [],
        "suggested_next_actions": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        cov = load_coverage_summary()
        cal = load_calendar_health()
        sec = load_security_master_health()
        prov = load_provider_health()
        bat = load_batch_execution_health()
        sto = load_storage_health()
    except Exception:
        return overview

    # Sub-statuses.
    cov_status = _coverage_overall_status(cov)
    cal_status = cal.get("health_status", HEALTH_UNKNOWN)
    sec_status = sec.get("health_status", HEALTH_UNKNOWN)
    prov_status = _provider_overall_status(prov)
    bat_status = bat.get("health_status", HEALTH_UNKNOWN)
    sto_status = _storage_overall_status(sto)
    overview["coverage_status"] = cov_status
    overview["calendar_status"] = cal_status
    overview["security_master_status"] = sec_status
    overview["provider_status"] = prov_status
    overview["batch_status"] = bat_status
    overview["storage_status"] = sto_status

    # Overall verdict by precedence.
    if cal_status in (HEALTH_NOT_RECOMMENDED,) or cov_status == HEALTH_NOT_RECOMMENDED:
        overview["overall_status"] = OVERALL_NOT_RECOMMENDED
        overview["status_reason"] = "关键依赖（交易日历或行情覆盖率）不可用"
    else:
        risky_count = sum(
            1 for s in (cov_status, cal_status, sec_status,
                        prov_status, bat_status, sto_status)
            if s in (HEALTH_RISKY, HEALTH_NOT_RECOMMENDED, HEALTH_UNAVAILABLE)
        )
        usable_count = sum(
            1 for s in (cov_status, cal_status, sec_status,
                        prov_status, bat_status, sto_status)
            if s == HEALTH_USABLE
        )
        if risky_count >= 2:
            overview["overall_status"] = OVERALL_RISKY
            overview["status_reason"] = "多模块存在风险"
        elif usable_count >= 1 or risky_count >= 1:
            overview["overall_status"] = OVERALL_USABLE
            overview["status_reason"] = "底座可用但存在缺口"
        else:
            overview["overall_status"] = OVERALL_HEALTHY
            overview["status_reason"] = "数据底座健康"

    overview["overall_score"] = _overall_score(overview["overall_status"])

    # Top issues / actions.
    overview["top_issues"] = _top_issues(
        cov=cov, cal=cal, sec=sec, prov=prov, bat=bat, sto=sto,
        cov_status=cov_status, cal_status=cal_status, sec_status=sec_status,
        prov_status=prov_status, bat_status=bat_status, sto_status=sto_status,
    )
    overview["suggested_next_actions"] = _suggested_actions(
        cov_status=cov_status, cal_status=cal_status, sec_status=sec_status,
        prov_status=prov_status, bat_status=bat_status, sto_status=sto_status,
        retryable_tasks=bat.get("retryable_tasks", 0),
    )
    return overview


def _coverage_overall_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return HEALTH_UNKNOWN
    levels = [r["coverage_level"] for r in rows]
    if any(l == HEALTH_NOT_RECOMMENDED for l in levels):
        return HEALTH_NOT_RECOMMENDED
    if any(l == "risky" for l in levels):
        return HEALTH_RISKY
    if any(l == "usable_with_gaps" for l in levels):
        return HEALTH_USABLE
    if all(l == HEALTH_UNKNOWN for l in levels):
        return HEALTH_UNKNOWN
    return HEALTH_HEALTHY


def _provider_overall_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return HEALTH_UNKNOWN
    statuses = [r["health_status"] for r in rows]
    if any(s == HEALTH_UNAVAILABLE for s in statuses):
        return HEALTH_UNAVAILABLE
    if any(s == HEALTH_RISKY for s in statuses):
        return HEALTH_RISKY
    if any(s == HEALTH_USABLE for s in statuses):
        return HEALTH_USABLE
    if all(s == HEALTH_UNKNOWN for s in statuses):
        return HEALTH_UNKNOWN
    return HEALTH_HEALTHY


def _storage_overall_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return HEALTH_UNKNOWN
    statuses = [r["health_status"] for r in rows]
    if any(s == HEALTH_NOT_RECOMMENDED for s in statuses):
        return HEALTH_NOT_RECOMMENDED
    # core DuckDB tables that must exist & have data
    core_required_empty = any(
        r["storage_type"] == "duckdb"
        and r["object_name"] in ("stock_daily_raw", "stock_daily_qfq")
        and r["row_count"] == 0 for r in rows
        if "object_name" in r
    )
    if core_required_empty:
        return HEALTH_NOT_RECOMMENDED
    if any(s == HEALTH_RISKY for s in statuses):
        return HEALTH_RISKY
    if any(s == HEALTH_USABLE for s in statuses):
        return HEALTH_USABLE
    if all(s == HEALTH_UNKNOWN for s in statuses):
        return HEALTH_UNKNOWN
    return HEALTH_HEALTHY


def _overall_score(status: str) -> int:
    return {
        OVERALL_HEALTHY: 95,
        OVERALL_USABLE: 80,
        OVERALL_RISKY: 55,
        OVERALL_NOT_RECOMMENDED: 20,
    }.get(status, 0)


def _top_issues(**ctx) -> list[str]:
    issues: list[str] = []
    cov = ctx["cov"]; cal = ctx["cal"]; sec = ctx["sec"]
    prov = ctx["prov"]; bat = ctx["bat"]; sto = ctx["sto"]
    if ctx["cov_status"] == HEALTH_NOT_RECOMMENDED:
        issues.append("核心行情覆盖率过低，不建议做后续分析")
    elif ctx["cov_status"] == HEALTH_RISKY:
        risky_unis = [r["universe_name"] for r in cov
                      if r["coverage_level"] == "risky"]
        if risky_unis:
            issues.append(f"覆盖率风险: {', '.join(sorted(set(risky_unis)))}")
    if ctx["cal_status"] == HEALTH_NOT_RECOMMENDED:
        issues.append("交易日历不可用")
    elif ctx["cal_status"] == HEALTH_RISKY:
        issues.append(f"交易日历: {cal.get('issue_summary', '风险')}")
    if ctx["sec_status"] in (HEALTH_NOT_RECOMMENDED, HEALTH_RISKY):
        issues.append(f"证券主数据: {sec.get('issue_summary', '风险')}")
    if ctx["prov_status"] in (HEALTH_UNAVAILABLE, HEALTH_RISKY):
        names = [r["provider"] for r in prov if r["health_status"] in (HEALTH_RISKY, HEALTH_UNAVAILABLE)]
        if names:
            issues.append(f"Provider 不稳定: {', '.join(names)}")
    if ctx["bat_status"] in (HEALTH_RISKY, HEALTH_NOT_RECOMMENDED):
        issues.append(f"批次执行: {bat.get('issue_summary', '风险')}")
    empty_core = [r["object_name"] for r in sto
                  if r.get("storage_type") == "duckdb"
                  and r["object_name"] in ("stock_daily_raw", "stock_daily_qfq")
                  and r.get("row_count") == 0]
    if empty_core:
        issues.append(f"DuckDB 核心表为空: {', '.join(empty_core)}")
    return issues[:10]


def _suggested_actions(**ctx) -> list[str]:
    actions: list[str] = []
    retryable = ctx["retryable_tasks"]
    if retryable and retryable > 0:
        actions.append(f"请查看「补数批次」tab 中的 {retryable} 个 retryable 任务")
    if ctx["cov_status"] in (HEALTH_UNKNOWN, HEALTH_NOT_RECOMMENDED, HEALTH_RISKY):
        actions.append("建议先在命令行 dry-run 检查覆盖率扫描: `python -m src.data_quality.coverage_scanner --adj all --dry-run`")
    if ctx["cal_status"] in (HEALTH_NOT_RECOMMENDED, HEALTH_RISKY):
        actions.append("建议检查交易日历同步状态；如需真实同步，请离开本页面后在命令行手动评估执行")
    if ctx["sec_status"] in (HEALTH_NOT_RECOMMENDED, HEALTH_RISKY):
        actions.append("建议检查 security_master 缺失字段；如需真实同步，请离开本页面后在命令行手动评估执行")
    if ctx["prov_status"] in (HEALTH_UNAVAILABLE, HEALTH_RISKY):
        actions.append("建议检查 Provider 稳定性，必要时降低批量 limit、增加 sleep")
    if ctx["bat_status"] in (HEALTH_RISKY, HEALTH_NOT_RECOMMENDED):
        actions.append("建议查看最新批次的失败原因并按建议重试命令处理")
    if not actions:
        actions.append("数据底座健康，无需立即操作")
    return actions[:5]
