"""Rule metadata for V1.6.3 condition engine."""
from __future__ import annotations

REQUIRED_CONDITION_GROUPS = (
    "entry",
    "add_position",
    "reduce",
    "exit",
    "cancel_watch",
    "invalidation",
    "risk",
    "observation",
)

PERMISSION_RULES = {
    "entry_requires_exit": "entry permission requires explicit exit guards",
    "focus_requires_invalidation": "focus observation requires invalidation guards",
    "add_requires_risk": "add-position permission requires explicit risk guards",
}
