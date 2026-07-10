"""V1.7.2 position diagnosis Markdown report generation."""

from __future__ import annotations

import json
from typing import Any

DISCLAIMER = (
    "本报告仅用于本地持仓记录、投研辅助和系统测试，不构成投资建议，"
    "不构成买卖依据，不会自动执行任何交易。所有持仓动作均须由用户人工确认。"
)

STATUS_CN: dict[str, str] = {
    "healthy": "健康", "watch": "关注", "cautious": "谨慎",
    "dangerous": "危险", "unknown": "暂无判断",
}
ACTION_CN: dict[str, str] = {
    "continue_hold": "继续持有", "light_hold": "轻仓持有",
    "forbid_add": "禁止加仓", "allow_add_conditionally": "条件允许加仓",
    "reduce_conditionally": "触发减仓条件", "exit_conditionally": "触发清仓条件",
    "cancel_watch": "取消关注", "unknown": "暂无判断",
}
THESIS_CN: dict[str, str] = {
    "valid": "有效", "weakening": "弱化", "invalid": "失效",
    "manual_review_required": "需人工复核", "unknown": "暂无判断",
}
SIZE_CN: dict[str, str] = {
    "normal": "正常", "elevated": "偏高", "high": "过重", "unknown": "未知",
}


def build_position_diagnosis_markdown(result: dict[str, Any]) -> str:
    """Build a single-position diagnosis Markdown report."""
    lines: list[str] = []
    lines.append("# 每日持仓体检报告")
    lines.append("")

    # 1. Position info
    lines.append("## 1. 持仓信息")
    lines.append("")
    lines.append(f"- 持仓ID: {result.get('position_id', '')}")
    lines.append(f"- 组合: {result.get('portfolio_name', '')}")
    lines.append(f"- 股票: {result.get('stock_code', '')} {result.get('stock_name', '')}")
    lines.append(f"- 板块: {result.get('sector_name') or '暂无数据'}")
    lines.append(f"- 交易日期: {result.get('trade_date', '')}")
    lines.append("")

    # 2. Conclusion
    lines.append("## 2. 体检结论")
    lines.append("")
    lines.append(f"- 体检状态: **{STATUS_CN.get(result.get('diagnosis_status', ''), result.get('diagnosis_status', ''))}**")
    lines.append(f"- 建议动作: **{ACTION_CN.get(result.get('suggested_action', ''), result.get('suggested_action', ''))}**")
    lines.append(f"- 健康分数: {result.get('health_score', 0):.1f}/100")
    lines.append(f"- 数据覆盖率: {result.get('data_coverage_ratio', 0):.0%}")
    lines.append("")

    # 3. Thesis
    lines.append("## 3. 原始逻辑状态")
    lines.append("")
    lines.append(f"- 状态: {THESIS_CN.get(result.get('thesis_status', ''), result.get('thesis_status', ''))}")
    lines.append(f"- 得分: {result.get('thesis_score', 0):.0f}/100")
    lines.append("")

    # 4. Floating P&L
    lines.append("## 4. 当前浮动收益")
    lines.append("")
    unreal = result.get("unrealized_return_pct")
    if unreal is not None:
        lines.append(f"- 浮动收益率: {unreal:+.2f}%")
    else:
        lines.append("- 浮动收益率: 暂无数据")
    lines.append(f"- 最新收盘价: {result.get('latest_close') or '暂无数据'}")
    lines.append(f"- 20日最大回撤: {result.get('drawdown_20d') or '暂无数据'}%")
    lines.append("")

    # 5-10. Component scores
    _component_section(lines, "5. 市场环境", result, "market")
    _component_section(lines, "6. 情绪周期", result, "sentiment")
    _component_section(lines, "7. 板块状态", result, "sector")
    _component_section(lines, "8. 龙头地位", result, "leader")
    _component_section(lines, "9. 趋势结构", result, "trend")
    _component_section(lines, "10. 条件引擎", result, "condition")

    # 11. Position size
    lines.append("## 11. 仓位状态")
    lines.append("")
    lines.append(f"- 仓位百分比: {result.get('position_pct') or '暂无数据'}%")
    lines.append(f"- 仓位状态: {SIZE_CN.get(result.get('position_size_status', ''), result.get('position_size_status', ''))}")
    lines.append("")

    # 12. Risk
    lines.append("## 12. 风险提示")
    lines.append("")
    warnings = result.get("risk_warnings", [])
    for w in warnings:
        lines.append(f"- {w}")
    if not warnings:
        lines.append("暂无严重风险提示。")
    lines.append("")

    # 13. Observation
    lines.append("## 13. 观察条件")
    lines.append("")
    obs = result.get("observation_conditions", [])
    for o in obs:
        lines.append(f"- {o}")
    if not obs:
        lines.append("暂无。")
    lines.append("")

    # 14. Invalidation
    lines.append("## 14. 失效条件")
    lines.append("")
    inv = result.get("invalidation_conditions", [])
    for i in inv:
        lines.append(f"- {i}")
    if not inv:
        lines.append("暂无。")
    lines.append("")

    # 15. Data quality
    lines.append("## 15. 数据质量")
    lines.append("")
    lines.append(f"- 状态: {result.get('data_quality_status', 'unknown')}")
    issues = result.get("issue_summary", "")
    if isinstance(issues, str) and issues:
        for i in issues.split("; "):
            lines.append(f"- {i}")
    elif isinstance(issues, list):
        for i in issues:
            lines.append(f"- {i}")
    lines.append("")

    # 16. Disclaimer
    lines.append("## 16. 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    return "\n".join(lines)


def build_daily_position_diagnosis_markdown(
    results: list[dict[str, Any]], summary: dict[str, Any] | None = None
) -> str:
    """Build a daily diagnosis summary Markdown report."""
    lines: list[str] = []
    lines.append("# 每日持仓体检汇总")
    lines.append("")

    # 1. Overview
    lines.append("## 1. 今日体检概览")
    lines.append("")
    if summary:
        lines.append(f"- 总体检数: {summary.get('total', len(results))}")
        for status in ("healthy", "watch", "cautious", "dangerous", "unknown"):
            cnt = summary.get(status, 0)
            if cnt:
                lines.append(f"- {STATUS_CN.get(status, status)}: {cnt}")
    else:
        lines.append(f"- 总体检数: {len(results)}")
    lines.append("")

    # 2-7. Group by action
    groups = {
        "continue_hold": ("2. 继续持有", []),
        "light_hold": ("3. 轻仓持有", []),
        "forbid_add": ("4. 禁止加仓", []),
        "allow_add_conditionally": ("5. 条件允许加仓", []),
        "reduce_conditionally": ("6. 触发减仓条件", []),
        "exit_conditionally": ("7. 触发清仓条件", []),
    }

    for r in results:
        action = r.get("suggested_action", "unknown")
        if action in groups:
            groups[action][1].append(r)

    for action, (title, items) in groups.items():
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("（无）")
        else:
            for item in items:
                status = STATUS_CN.get(item.get("diagnosis_status", ""), "")
                name = item.get("stock_name") or item.get("stock_code", "")
                lines.append(
                    f"- {item.get('stock_code', '')} {name} | "
                    f"状态={status} | 健康={item.get('health_score', 0):.0f} | "
                    f"收益率={item.get('unrealized_return_pct') or 'N/A'}%"
                )
        lines.append("")

    # 8. Data issues
    lines.append("## 8. 数据问题")
    lines.append("")
    unknowns = [r for r in results if r.get("diagnosis_status") == "unknown"]
    if unknowns:
        for u in unknowns:
            lines.append(f"- {u.get('stock_code', '')}: 数据不足无法判断")
    else:
        lines.append("（无）")
    lines.append("")

    # 9. Disclaimer
    lines.append("## 9. 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    return "\n".join(lines)


def _component_section(
    lines: list[str], title: str, result: dict[str, Any], prefix: str
) -> None:
    comp = result.get(f"{prefix}_component") or {}
    score_key = f"{prefix}_support_score"
    if prefix == "trend":
        score_key = "trend_health_score"
    if prefix == "condition":
        score_key = "condition_support_score"

    lines.append(f"## {title}")
    lines.append("")
    if comp:
        lines.append(f"- 得分: {comp.get('score', result.get(score_key, 0)):.0f}/100")
        if comp.get("reason"):
            lines.append(f"- 说明: {comp['reason']}")
        if comp.get("evidence"):
            lines.append(f"- 依据: {'; '.join(comp['evidence'][:3])}")
    else:
        lines.append(f"- 得分: {result.get(score_key, 0):.0f}/100")
        lines.append("- 数据缺失")
    lines.append("")
