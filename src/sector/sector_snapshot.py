"""V1.5.0 sector snapshot — on-the-fly aggregation, empty-by-default.

There is **no pre-computed sector daily-return table** in the substrate.
Sectors are derived on the fly by joining ``security_master.industry``
with ``stock_daily_raw.pct_change`` for the latest trade date.

Design:
* Always returns a well-formed dict (never raises).
* If either ``security_master`` (meta DB) or ``stock_daily_raw`` (DuckDB)
  has no usable rows, returns ``sectors=[]`` plus an explanatory
  ``issue_summary``.
* ``limit_up_count`` is **always None** — there is no persisted limit-up
  flag column (a 9.9% heuristic is unreliable for ST 5% / 科创板 20% / 北交
  所 30% and is intentionally not used).
* ``strength_score`` is a simple, explainable value:
  ``round(mean(pct_change), 4)`` — no complex algorithm in this version.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from src.data_quality.quality_dashboard import (
    build_quality_overview, HEALTH_UNKNOWN,
)

SECTOR_TYPE_INDUSTRY = "industry"
SECTOR_TYPE_POOL = "pool"


@dataclass
class SectorRow:
    """One row in the strong-sector table."""

    sector_name: str
    sector_type: str
    strength_score: float
    rank: int
    change_pct: float
    turnover_amount: float
    up_stock_count: int
    down_stock_count: int
    limit_up_count: int | None  # always None in V1.5.0
    data_quality_status: str = HEALTH_UNKNOWN
    issue_summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_quality_status() -> tuple[str, list[str]]:
    try:
        ov = build_quality_overview()
        return (
            str(ov.get("overall_status") or HEALTH_UNKNOWN),
            list(ov.get("top_issues") or []),
        )
    except Exception:
        return HEALTH_UNKNOWN, []


def _symbol_industry_map() -> dict[str, str]:
    """Return {symbol: industry} from security_master (meta DB).

    Symbols are zero-padded to 6 digits in the meta DB; we keep both the
    6-digit and stripped forms as keys for a lenient join.
    """
    out: dict[str, str] = {}
    try:
        from src.repositories.security_master_repo import SecurityMasterRepository
        rows = SecurityMasterRepository().list_all(limit=5000)
        for sm in rows:
            ind = (sm.industry or "").strip()
            if not ind:
                continue
            sym = str(sm.symbol or "").strip()
            if not sym:
                continue
            out[sym] = ind
            stripped = sym.lstrip("0")
            if stripped:
                out[stripped] = ind
    except Exception:
        pass
    return out


def _aggregates_for_date(trade_date: str) -> list[dict[str, Any]]:
    """Return per-stock rows {stock_code, pct_change, amount} for trade_date."""
    try:
        from src.storage.duckdb_repo import query_df
        df = query_df(
            "SELECT stock_code, pct_change, amount "
            "FROM stock_daily_raw WHERE trade_date = ?",
            [trade_date],
        )
        if df is None or df.empty:
            return []
        return df.to_dict("records")
    except Exception:
        return []


def _group_by_industry(
    rows: list[dict[str, Any]], ind_map: dict[str, str],
) -> list[SectorRow]:
    """Aggregate per-stock rows into SectorRow by industry."""
    bucket: dict[str, dict[str, Any]] = {}
    for r in rows:
        code = str(r.get("stock_code") or "").strip()
        if not code:
            continue
        ind = ind_map.get(code) or ind_map.get(code.lstrip("0"))
        if not ind:
            continue
        try:
            pct = float(r.get("pct_change") or 0.0)
            amt = float(r.get("amount") or 0.0)
        except (TypeError, ValueError):
            continue
        b = bucket.setdefault(ind, {
            "pct_sum": 0.0, "amt_sum": 0.0, "up": 0, "down": 0, "n": 0,
        })
        b["pct_sum"] += pct
        b["amt_sum"] += amt
        b["n"] += 1
        if pct > 0:
            b["up"] += 1
        elif pct < 0:
            b["down"] += 1

    sector_rows: list[SectorRow] = []
    for ind, b in bucket.items():
        if b["n"] == 0:
            continue
        change_pct = round(b["pct_sum"] / b["n"], 6)
        sector_rows.append(SectorRow(
            sector_name=ind,
            sector_type=SECTOR_TYPE_INDUSTRY,
            strength_score=round(change_pct, 4),
            rank=0,  # filled by rank_strong_sectors
            change_pct=change_pct,
            turnover_amount=round(b["amt_sum"], 4),
            up_stock_count=b["up"],
            down_stock_count=b["down"],
            limit_up_count=None,
            data_quality_status=HEALTH_UNKNOWN,
            issue_summary=f"{b['n']} 只成分股",
        ))
    return sector_rows


# ── Public API ─────────────────────────────────────────────────────────────────

def build_sector_snapshot(trade_date: str | None = None) -> dict[str, Any]:
    """Build the sector snapshot dict.

    Returns keys: trade_date, sectors, data_quality_status, issue_summary.
    Never raises — empty data → empty sectors list + explanatory text.
    """
    quality_status, top_issues = _load_quality_status()
    sectors: list[SectorRow] = []
    issues: list[str] = []

    if not trade_date:
        issues.append("未解析到交易日期，暂无板块数据")
    else:
        try:
            ind_map = _symbol_industry_map()
            if not ind_map:
                issues.append("security_master 无 industry 字段，暂无板块数据，等待 V1.5.3 / V1.5.4 完善")
            else:
                rows = _aggregates_for_date(trade_date)
                if not rows:
                    issues.append("当日无行情数据，暂无板块数据，等待 V1.5.3 / V1.5.4 完善")
                else:
                    sectors = _group_by_industry(rows, ind_map)
                    sectors = rank_strong_sectors(sectors)
                    if not sectors:
                        issues.append("行情与板块标签未能匹配，暂无板块数据，等待 V1.5.3 / V1.5.4 完善")
        except Exception as exc:  # graceful: any failure → empty list + reason
            issues.append(f"板块聚合失败：{type(exc).__name__}，暂无板块数据")

    if not issues and not sectors:
        issues.append("暂无板块数据，等待 V1.5.3 / V1.5.4 完善")
    if not issues and sectors:
        issues.append(f"共 {len(sectors)} 个板块（实时聚合，非正式强度算法）")

    return {
        "trade_date": trade_date,
        "sectors": sectors,
        "data_quality_status": quality_status,
        "issue_summary": issues,
    }


def rank_strong_sectors(rows: list[SectorRow]) -> list[SectorRow]:
    """Order sectors by ``change_pct`` descending and assign ``rank`` (1-based).

    Pure sort — no extra I/O, no fabricated rows.
    """
    ordered = sorted(rows, key=lambda r: r.change_pct, reverse=True)
    for i, r in enumerate(ordered, start=1):
        r.rank = i
    return ordered