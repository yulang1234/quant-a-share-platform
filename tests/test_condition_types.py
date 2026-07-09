"""V1.6.3 condition type tests."""
from __future__ import annotations

from src.conditions.condition_rules import REQUIRED_CONDITION_GROUPS
from src.conditions.condition_types import ConditionItem, ConditionSet


def test_condition_item_as_dict():
    item = ConditionItem("entry", "market", "satisfied")
    assert item.as_dict()["ctype"] == "entry"


def test_condition_set_has_permission_summary():
    data = ConditionSet(permission="allow_observe", permission_reason="reason").as_dict()
    assert data["permission_summary"]["permission"] == "allow_observe"


def test_required_groups_complete():
    assert set(REQUIRED_CONDITION_GROUPS) == {
        "entry",
        "add_position",
        "reduce",
        "exit",
        "cancel_watch",
        "invalidation",
        "risk",
        "observation",
    }
