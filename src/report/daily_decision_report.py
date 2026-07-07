"""V1.5.0 daily decision card Markdown renderer.

Read-only renderer for the minimal decision-card skeleton. It does not
fetch network data, write files, run backfill, or call any trading API.
"""
from __future__ import annotations

from typing import Any


DISCLAIMER = (
    "本报告仅用于个人投研辅助和系统测试，不构成任何投资建议，不构成买卖依据。"
)


def _val(value: Any, default: str = "unknown") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _bullets(items: list[Any] | tuple[Any, ...] | None, empty: str = "暂无数据") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {_val(x, '暂无数据')}" for x in items)


def render_daily_decision_markdown(card: Any) -> str:
    """Render a DailyDecisionCard or card-like dict into Markdown."""
    data = card.as_dict() if hasattr(card, "as_dict") else dict(card or {})
    sectors = data.get("strong_sectors") or []
    if sectors:
        sector_lines = []
        for s in sectors[:5]:
            sector_lines.append(
                "- "
                f"{_val(s.get('sector_name'), '未知板块')} | "
                f"rank={_val(s.get('rank'))} | "
                f"strength={_val(s.get('strength_score'))} | "
                f"change={_val(s.get('change_pct'))}"
            )
        sector_text = "\n".join(sector_lines)
    else:
        sector_text = "- 暂无强势板块数据"

    md = f"""# 今日决策卡

> {DISCLAIMER}

## 总览

- 交易日期: {_val(data.get("trade_date"))}
- 生成时间: {_val(data.get("generated_at"), "unknown")}
- 整体倾向: {_val(data.get("overall_bias"))}
- 市场状态: {_val(data.get("market_state"))}
- 情绪阶段: {_val(data.get("sentiment_cycle"))}
- 风险等级: {_val(data.get("risk_level"))}
- 数据质量: {_val(data.get("data_quality_status"))}

## 强势板块

{sector_text}

## 风险提示

{_bullets(data.get("risk_warnings"))}

## 建议动作

{_bullets(data.get("suggested_actions"))}

## 观察条件

{_bullets(data.get("observation_conditions"))}

## 失效条件

{_bullets(data.get("invalidation_conditions"))}

## 数据问题

{_bullets(data.get("issue_summary"))}

---

{DISCLAIMER}
"""
    return md
