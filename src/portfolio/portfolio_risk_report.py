"""V1.7.3 portfolio risk Markdown report generation."""

from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "本报告仅用于本地组合风险分析、个人投研辅助和系统测试，"
    "不构成投资建议，不构成买卖依据，不会自动执行任何交易。"
    "所有风险处理均须由用户人工确认。\n\n"
    "组合收益和回撤基于当前仓位权重近似计算，不代表真实历史仓位变化。"
)

LEVEL_CN = {"low": "低风险", "medium": "中等风险", "high": "高风险", "critical": "严重风险", "unknown": "暂无判断"}
PERM_CN = {"normal": "正常", "watch": "观察", "freeze_new_positions": "暂停新增持仓",
           "freeze_additions": "暂停扩大仓位", "reduce_exposure_conditionally": "建议降低风险暴露",
           "manual_review": "需人工复核", "unknown": "暂无判断"}


def build_portfolio_risk_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 组合风险控制报告")
    lines.append("")
    lines.append(f"**组合**: {result.get('portfolio_name', '')} | **类型**: {'模拟' if result.get('is_simulated') else '真实'} | **日期**: {result.get('trade_date', '')}")
    lines.append("")

    # 1-2. Overview
    lines.append("## 1. 风险总览")
    lines.append("")
    lines.append(f"- 风险评分: **{result.get('portfolio_risk_score', 0):.0f}/100**")
    lines.append(f"- 风险等级: **{LEVEL_CN.get(result.get('portfolio_risk_level', ''), result.get('portfolio_risk_level', ''))}**")
    lines.append(f"- 组合权限: **{PERM_CN.get(result.get('portfolio_permission', ''), result.get('portfolio_permission', ''))}**")
    lines.append(f"- 数据覆盖率: {result.get('data_coverage_ratio', 0):.0%}")
    lines.append("")

    # 3. Position overview
    lines.append("## 2. 总仓位与现金比例")
    lines.append("")
    lines.append(f"- 持仓数量: {result.get('position_count', 0)}")
    lines.append(f"- 总仓位: {result.get('total_position_pct', 0):.1f}%")
    cash = result.get("cash_pct")
    lines.append(f"- 现金比例: {cash:.1f}%" if cash is not None else "- 现金比例: 无法计算")
    lines.append("")

    # 4. Single position
    lines.append("## 3. 单股集中度")
    lines.append("")
    lines.append(f"- 最大单股仓位: {result.get('max_single_position_code', '')} {result.get('max_single_position_pct', 0):.1f}%")
    lines.append(f"- Top3集中度: {result.get('top3_position_pct', 0):.1f}%")
    for dim in result.get("risk_dimensions", []):
        if dim.get("name") == "single_position":
            lines.append(f"- 风险分: {dim.get('risk_score', 0):.0f} ({dim.get('risk_level', '')})")
    lines.append("")

    # 5. Sector
    lines.append("## 4. 板块与题材集中度")
    lines.append("")
    lines.append(f"- 最大板块: {result.get('max_sector_name', '')} ({result.get('max_sector_position_pct', 0):.1f}%)")
    lines.append(f"- 板块数量: {result.get('sector_count', 0)}")
    for se in result.get("sector_exposures", [])[:5]:
        lines.append(f"  - {se.get('sector_name', '')}: {se.get('total_position_pct', 0):.1f}% ({se.get('position_count', 0)}只)")
    lines.append("")

    # 6. Market exposure
    lines.append("## 5. 市场环境适配")
    lines.append("")
    lines.append(f"- 市场状态: {result.get('market_state', '')}")
    lines.append(f"- 情绪周期: {result.get('sentiment_cycle', '')}")
    for dim in result.get("risk_dimensions", []):
        if dim.get("name") == "market_exposure":
            lines.append(f"- 适配风险: {dim.get('risk_score', 0):.0f} ({dim.get('reason', '')})")
    lines.append("")

    # 7. Correlation
    lines.append("## 6. 持仓相关性")
    lines.append("")
    avg = result.get("average_pairwise_correlation")
    lines.append(f"- 平均相关性: {avg:.2f}" if avg is not None else "- 平均相关性: 暂无数据")
    lines.append(f"- 高相关对数: {result.get('high_correlation_pair_count', 0)}")
    for cp in result.get("correlation_pairs", [])[:5]:
        lines.append(f"  - {cp.get('stock_a', '')} ↔ {cp.get('stock_b', '')}: {cp.get('correlation', 0):.3f}")
    lines.append("")

    # 8. Drawdown
    lines.append("## 7. 组合回撤")
    lines.append("")
    dd20 = result.get("portfolio_drawdown_20d")
    dd60 = result.get("portfolio_drawdown_60d")
    lines.append(f"- 20日最大回撤: {dd20:.1f}%" if dd20 is not None else "- 20日最大回撤: 暂无数据")
    lines.append(f"- 60日最大回撤: {dd60:.1f}%" if dd60 is not None else "- 60日最大回撤: 暂无数据")
    lines.append("")

    # 9. Consecutive loss
    lines.append("## 8. 连续亏损")
    lines.append("")
    lines.append(f"- 连续亏损天数: {result.get('consecutive_loss_days', 0)}")
    lines.append("")

    # 10. Diagnosis
    lines.append("## 9. 持仓体检聚合")
    lines.append("")
    lines.append(f"- 危险持仓: {result.get('dangerous_position_count', 0)}")
    lines.append(f"- 谨慎持仓: {result.get('cautious_position_count', 0)}")
    lines.append(f"- 未知持仓: {result.get('unknown_position_count', 0)}")
    lines.append("")

    # 11-14. Risks & conditions
    lines.append("## 10. 风险提示")
    for f in result.get("risk_flags", []):
        lines.append(f"- ⚠ {f}")

    lines.append("")
    lines.append("## 11. 建议")
    for r in result.get("recommendations", []):
        lines.append(f"- {r}")

    lines.append("")
    lines.append("## 12. 观察条件")
    for o in result.get("observation_conditions", []):
        lines.append(f"- {o}")

    lines.append("")
    lines.append("## 13. 风险解除条件")
    for r in result.get("risk_release_conditions", []):
        lines.append(f"- {r}")

    lines.append("")
    lines.append("## 14. 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    return "\n".join(lines)


def build_all_portfolios_risk_markdown(results: list[dict[str, Any]], summary: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    lines.append("# 全组合风险控制报告")
    lines.append("")
    if summary:
        lines.append(f"- 成功: {summary.get('success_count', 0)} | 失败: {summary.get('failed_count', 0)}")
    for r in results:
        name = r.get("portfolio_name", "?")
        sim = "模拟" if r.get("is_simulated") else "真实"
        score = r.get("portfolio_risk_score", 0)
        level = LEVEL_CN.get(r.get("portfolio_risk_level", ""), "")
        lines.append(f"- [{name}] {sim} | 风险={score:.0f} | {level}")
    lines.append("")
    lines.append("## 免责声明")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
