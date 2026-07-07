from __future__ import annotations


FORBIDDEN = ("买入", "卖出", "加仓", "清仓", "满仓", "重仓", "梭哈", "目标价", "必涨", "稳赚", "保证收益", "推荐股票")


def test_markdown_contains_disclaimer() -> None:
    from src.report.daily_decision_report import render_daily_decision_markdown

    md = render_daily_decision_markdown({
        "trade_date": "2026-07-07",
        "overall_bias": "defensive",
        "market_state": "unknown",
        "sentiment_cycle": "unknown",
        "risk_level": "unknown",
        "data_quality_status": "unknown",
        "strong_sectors": [],
        "risk_warnings": [],
        "suggested_actions": ["数据不足，今日仅做观察"],
    })
    assert "本报告仅用于个人投研辅助和系统测试" in md
    assert "不构成任何投资建议" in md
    assert "## 建议动作" in md
    assert not any(w in md for w in FORBIDDEN)
