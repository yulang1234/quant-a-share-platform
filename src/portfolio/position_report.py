"""V1.7.1 position report — Markdown report generation.

Produces human-readable Markdown for position lists and detail views.
No external I/O, no trading advice, no automatic decisions.
"""

from __future__ import annotations

import json
from typing import Any

DISCLAIMER = (
    "本页面仅用于本地持仓记录和个人投研辅助，不构成投资建议，"
    "不会自动执行任何交易。"
)


def build_position_list_markdown(
    positions: list[dict[str, Any]], summary: dict[str, Any] | None = None
) -> str:
    """Build a Markdown report for a list of positions.

    Args:
        positions: List of position dicts (from _position_to_dict).
        summary: Optional summary dict (from PositionSummary).

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append("# 持仓记录")
    lines.append("")

    # ── Section 1: overview ─────────────────────────────────────────
    lines.append("## 1. 持仓概览")
    lines.append("")
    if summary:
        lines.append(f"- 活跃持仓数量: {summary.get('active_count', 0)}")
        lines.append(f"- 已关闭持仓数量: {summary.get('closed_count', 0)}")
        lines.append(f"- 真实持仓数量: {summary.get('real_count', 0)}")
        lines.append(f"- 模拟持仓数量: {summary.get('simulated_count', 0)}")
        total_pct = summary.get("total_position_pct", 0)
        lines.append(f"- 已填写仓位合计: {total_pct:.1f}%")
        if not summary.get("position_pct_ok", True):
            lines.append("")
            lines.append("> ⚠️ 录入数据仓位合计超过 100%，请检查。")
    lines.append("")

    # ── Section 2: active positions ──────────────────────────────────
    active = [p for p in positions if p.get("status") == "active"]
    lines.append("## 2. 活跃持仓")
    lines.append("")
    if not active:
        lines.append("暂无活跃持仓。")
    else:
        lines.append(_build_md_table(active))
    lines.append("")

    # ── Section 3: closed positions ──────────────────────────────────
    closed = [p for p in positions if p.get("status") == "closed"]
    lines.append("## 3. 已关闭持仓")
    lines.append("")
    if not closed:
        lines.append("暂无已关闭持仓。")
    else:
        lines.append(_build_md_table(closed))
    lines.append("")

    # ── Section 4: data notes ───────────────────────────────────────
    lines.append("## 4. 数据说明")
    lines.append("")
    lines.append("- 持仓数据存储在本地 SQLite，不联网同步。")
    lines.append("- 已关闭持仓不物理删除，保留全部历史记录。")
    lines.append("- 仓位百分比由用户手动录入，系统不自动调整。")
    lines.append("")

    # ── Section 5: disclaimer ───────────────────────────────────────
    lines.append("## 5. 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    return "\n".join(lines)


def build_position_detail_markdown(position: dict[str, Any]) -> str:
    """Build a Markdown report for a single position.

    Args:
        position: Position dict (from _position_to_dict).

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append("# 持仓详情")
    lines.append("")

    # ── Section 1: basic info ───────────────────────────────────────
    lines.append("## 1. 基本信息")
    lines.append("")
    lines.append(f"- 持仓ID: {position.get('position_id', '')}")
    lines.append(f"- 组合名称: {position.get('portfolio_name', '')}")
    mode = "模拟" if position.get("is_simulated") else "真实"
    lines.append(f"- 持仓类型: {mode}")
    lines.append(f"- 股票代码: {position.get('stock_code', '')}")
    lines.append(f"- 股票名称: {position.get('stock_name', '')}")
    lines.append(f"- 交易所: {position.get('exchange', '')}")
    lines.append(f"- 买入日期: {position.get('buy_date', '')}")
    lines.append(f"- 状态: {_status_cn(position.get('status', ''))}")
    if position.get("closed_at"):
        lines.append(f"- 关闭时间: {position.get('closed_at', '')}")
    lines.append("")

    # ── Section 2: cost & position ──────────────────────────────────
    lines.append("## 2. 成本与仓位")
    lines.append("")
    lines.append(f"- 平均成本: {(position.get('avg_cost') or 0):.2f}")
    qty = position.get("quantity")
    lines.append(f"- 持仓数量: {qty if qty is not None else '未填写'}")
    lines.append(f"- 仓位百分比: {(position.get('position_pct') or 0):.1f}%")
    lines.append("")

    # ── Section 3: buy reason ───────────────────────────────────────
    lines.append("## 3. 买入理由")
    lines.append("")
    lines.append(position.get("buy_reason") or "暂无数据")
    lines.append("")

    # ── Section 4: sector ───────────────────────────────────────────
    lines.append("## 4. 所属板块")
    lines.append("")
    lines.append(position.get("sector_name") or "暂无数据")
    lines.append("")

    # ── Section 5: original strategy ────────────────────────────────
    lines.append("## 5. 原始策略")
    lines.append("")
    lines.append(position.get("original_strategy") or "暂无数据")
    lines.append("")

    # ── Section 6: entry snapshot ───────────────────────────────────
    lines.append("## 6. 建仓快照")
    lines.append("")
    snapshot_json = position.get("entry_snapshot_json")
    if snapshot_json:
        try:
            snapshot = json.loads(snapshot_json)
            version = snapshot.get("version", position.get("snapshot_version", ""))
            trade_date = snapshot.get("trade_date", "")
            lines.append(f"- 快照版本: {version}")
            lines.append(f"- 快照日期: {trade_date}")
            lines.append(f"- 生成时间: {snapshot.get('generated_at', '')}")

            market = snapshot.get("market_environment")
            if market:
                lines.append(f"- 市场环境: {market.get('market_state', '暂无数据')}")

            sentiment = snapshot.get("sentiment_cycle")
            if sentiment:
                lines.append(f"- 情绪周期: {sentiment.get('sentiment_cycle', '暂无数据')}")

            leaders = snapshot.get("sector_leaders")
            if leaders:
                l1 = leaders.get("leader_1")
                if l1:
                    lines.append(f"- 板块龙头: {l1.get('stock_name', '')} (score={l1.get('leader_score', 0):.0f})")

            opp = snapshot.get("opportunity_index")
            if opp:
                lines.append(f"- 机会指数: {opp.get('opportunity_score', 0):.0f}/100")
                lines.append(f"- 机会等级: {opp.get('opportunity_level', '暂无数据')}")

            cond = snapshot.get("condition_set")
            if cond:
                lines.append(f"- 条件权限: {cond.get('permission', '暂无数据')}")

            risk_warnings = snapshot.get("risk_warnings", [])
            if risk_warnings:
                lines.append(f"- 风险提示: {'; '.join(risk_warnings)}")
        except Exception:
            lines.append("快照数据解析失败，JSON 可能已损坏。")
    else:
        lines.append("未保存建仓快照。")
    lines.append("")

    # ── Section 7: user note ────────────────────────────────────────
    lines.append("## 7. 用户备注")
    lines.append("")
    lines.append(position.get("user_note") or "暂无数据")
    lines.append("")

    # ── Section 8: data notes ───────────────────────────────────────
    lines.append("## 8. 数据说明")
    lines.append("")
    lines.append(f"- 创建时间: {position.get('created_at', '')}")
    lines.append(f"- 更新时间: {position.get('updated_at', '')}")
    lines.append("- 持仓数据存储在本地 SQLite，不联网同步。")
    lines.append("")

    # ── Section 9: disclaimer ───────────────────────────────────────
    lines.append("## 9. 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_md_table(positions: list[dict[str, Any]]) -> str:
    """Build a Markdown table from a list of position dicts."""
    headers = [
        "ID", "类型", "股票代码", "股票名称", "买入日期",
        "成本", "数量", "仓位%", "板块", "策略", "状态", "快照",
    ]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join([" --- " for _ in headers]) + "|"
    rows: list[str] = [header_line, sep_line]

    for p in positions:
        mode = "模拟" if p.get("is_simulated") else "真实"
        qty = p.get("quantity")
        qty_str = f"{int(qty)}" if qty is not None else "—"
        snapshot = "✅" if p.get("entry_snapshot_json") else "—"
        row = [
            str(p.get("position_id", "")),
            mode,
            str(p.get("stock_code", "")),
            str(p.get("stock_name", "")),
            str(p.get("buy_date", "")),
            f"{p.get('avg_cost', 0):.2f}",
            qty_str,
            f"{p.get('position_pct', 0):.1f}%",
            str(p.get("sector_name", "") or "—"),
            str(p.get("original_strategy", "") or "—"),
            _status_cn(p.get("status", "")),
            snapshot,
        ]
        rows.append("| " + " | ".join(row) + " |")

    return "\n".join(rows)


def _status_cn(status: str) -> str:
    mapping = {"active": "活跃", "closed": "已关闭"}
    return mapping.get(status, status)
