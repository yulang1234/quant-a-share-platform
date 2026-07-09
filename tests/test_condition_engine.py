"""V1.6.3 condition engine tests."""
from __future__ import annotations

from src.conditions.condition_engine import build_condition_set


def _m(state="attack"):
    return {"market_state": state}


def _s(cycle="warming"):
    return {"sentiment_cycle": cycle}


def _sec(status="confirmed_mainline", prob=85):
    return {"mainline_status": status, "mainline_probability": prob}


def _ldr(typ="leader_1", score=90):
    return {"leader_type": typ, "leader_score": score}


def _opp(score=75, risk_discount=1.0):
    return {"opportunity_score": score, "risk_discount": risk_discount}


def test_good_signals_entry_ok():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr(), _opp(80))
    assert not any(c.blocking for c in cs.entry)
    assert cs.permission in ("small_trial", "wait_entry", "allow_observe")


def test_bad_market_blocks_entry():
    cs = build_condition_set(_m("defense"), _s(), _sec(), _ldr(), _opp(80))
    assert any(c.blocking and "market" in c.name for c in cs.entry)


def test_retreat_blocks_entry():
    cs = build_condition_set(_m(), _s("retreat"), _sec(), _ldr(), _opp(80))
    assert any(c.blocking and "sentiment" in c.name for c in cs.entry)


def test_pseudo_leader_blocks_entry_and_cancel_watch():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr("pseudo_leader"), _opp(80))
    assert any(c.blocking and "leader" in c.name for c in cs.entry)
    assert any(c.status == "satisfied" for c in cs.cancel_watch)


def test_high_risk_chasing_blocks_add_position():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr("high_risk_chasing"), _opp(80))
    assert any(c.severity == "critical" for c in cs.risk)
    assert any(c.blocking for c in cs.add_position)


def test_low_opportunity_blocks_entry():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr(), _opp(25))
    assert any(c.blocking and "opportunity" in c.name for c in cs.entry)


def test_required_condition_groups_exist():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr(), _opp(80))
    assert len(cs.exit) >= 3
    assert len(cs.invalidation) >= 2
    assert cs.risk
    assert cs.observation


def test_permission_summary_present():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr(), _opp(80))
    data = cs.as_dict()
    assert data["permission_summary"]["permission"] == cs.permission


def test_no_forbidden_unconditional_output():
    cs = build_condition_set(_m(), _s(), _sec(), _ldr(), _opp(80))
    text = str(cs.as_dict())
    forbidden = ["立即买入", "立即卖出", "满仓", "重仓", "梭哈", "稳赚", "保证收益", "自动下单", "实盘执行"]
    for word in forbidden:
        assert word not in text


def test_permission_unknown_when_entry_blocked():
    cs = build_condition_set(_m("defense"), _s("retreat"), _sec("one_day_theme"), _ldr("pseudo_leader"), _opp(10))
    assert cs.permission in ("unknown", "cancel")
