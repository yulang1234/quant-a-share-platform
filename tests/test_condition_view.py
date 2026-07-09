"""V1.6.3 condition view data helpers tests."""
from __future__ import annotations

from ui.components.condition_view import condition_csv_bytes, condition_markdown_bytes, conditions_to_df


def _result():
    return {
        "permission": "allow_observe",
        "permission_reason": "reason",
        "entry_conditions": [
            {
                "name": "market",
                "status": "satisfied",
                "severity": "low",
                "blocking": False,
                "reason": "ok",
            }
        ],
    }


def test_conditions_to_df_handles_empty():
    assert conditions_to_df(None).empty


def test_conditions_to_df_exports_rows():
    df = conditions_to_df(_result())
    assert list(df["name"]) == ["market"]


def test_export_bytes():
    assert condition_csv_bytes(_result())
    assert condition_markdown_bytes(_result()).startswith(b"# Condition Engine Report")
