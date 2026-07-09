"""V1.6.3 condition rule metadata tests."""
from __future__ import annotations

from src.conditions.condition_rules import PERMISSION_RULES


def test_permission_rules_document_safety_guards():
    assert "entry_requires_exit" in PERMISSION_RULES
    assert "focus_requires_invalidation" in PERMISSION_RULES
    assert "add_requires_risk" in PERMISSION_RULES
