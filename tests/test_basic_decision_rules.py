from __future__ import annotations


FORBIDDEN = ("买入", "卖出", "加仓", "清仓", "满仓", "重仓", "梭哈", "目标价", "必涨", "稳赚", "保证收益", "推荐股票")


def test_unknown_inputs_are_defensive() -> None:
    from src.rules.basic_decision_rules import decide_overall_bias

    assert decide_overall_bias("unknown", "unknown", 0, "unknown") == "defensive"


def test_bad_quality_not_aggressive() -> None:
    from src.rules.basic_decision_rules import decide_overall_bias

    assert decide_overall_bias("strong", "rising", 3, "risky") != "aggressive"


def test_suggested_actions_no_forbidden_words() -> None:
    from src.rules.basic_decision_rules import build_suggested_actions

    actions = build_suggested_actions("unknown", "unknown", 0, "unknown")
    text = "\n".join(actions)
    assert not any(w in text for w in FORBIDDEN)
