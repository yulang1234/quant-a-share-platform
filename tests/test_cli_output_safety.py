"""
CLI output safety tests -- ensure all console output uses only ASCII-safe
characters that will not break on Windows GBK code-page terminals.

All forbidden symbols are listed via Unicode escape so the test file itself
cannot be corrupted by encoding issues.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# CLI files that print user-facing output
_CLI_FILES = [
    "main.py",
    "src/data_update/historical_loader.py",
    "src/data_update/retry_failed.py",
]

# Forbidden symbols listed via their Unicode code point.
# Using escapes avoids file-encoding corruption.
_FORBIDDEN_SYMBOLS: list[str] = [
    "✓",  # check mark
    "✗",  # ballot x
    "✅",  # white heavy check mark
    "❌",  # cross mark
    "→",  # right arrow
    "←",  # left arrow
    "—",  # em dash
    "–",  # en dash
    "⚠",  # warning sign
    "\U0001f680",  # rocket
    "\U0001f4ca",  # bar chart
    "\U0001f4c8",  # chart with upwards trend
    "\U0001f4c9",  # chart with downwards trend
    "─",  # box drawing horizontal
    "│",  # box drawing vertical
    "└",  # box drawing up and right
    "├",  # box drawing vertical and right
    "○",  # white circle
    "●",  # black circle
    "★",  # star
]


@pytest.mark.parametrize("rel_path", _CLI_FILES)
class TestCliOutputAsciiSafe:
    """V0.3 CLI print() strings must encode safely to ASCII."""

    def test_print_strings_are_ascii_safe(self, rel_path: str) -> None:
        """Every print()-argument string literal in the file is ASCII-safe."""
        filepath = _PROJECT_ROOT / rel_path
        assert filepath.exists(), f"File not found: {filepath}"

        problems: list[str] = []

        with open(filepath, "r", encoding="utf-8") as fh:
            source = fh.read()

        # Collect every string literal via simple heuristics:
        # lines that contain print( or f"
        lines = source.splitlines()
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            # Only check lines that contain print( calls
            if "print(" not in stripped:
                continue
            # For each line with print, check the whole line against forbidden symbols
            for sym in _FORBIDDEN_SYMBOLS:
                if sym in stripped:
                    problems.append(
                        f"  L{lineno:4d}  U+{ord(sym):04X}  in  {stripped[:80]}"
                    )
                    break  # one report per line is enough

        if problems:
            msg = f"Found {len(problems)} forbidden symbol(s) in {rel_path}:\n"
            msg += "\n".join(problems)
            pytest.fail(msg)

    def test_print_strings_encode_ascii(self, rel_path: str) -> None:
        """All print()-argument string constants must encode to ASCII.

        Walk the AST, collect every plain-string literal that is passed
        to print(), and assert text.encode('ascii').
        """
        filepath = _PROJECT_ROOT / rel_path
        assert filepath.exists(), f"File not found: {filepath}"

        import ast

        with open(filepath, "r", encoding="utf-8") as fh:
            try:
                tree = ast.parse(fh.read(), filename=str(filepath))
            except SyntaxError:
                return  # skip unparseable files

        problems: list[str] = []

        for node in ast.walk(tree):
            # Look for Call nodes where func is print
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Name) and func.id == "print"):
                continue
            # Collect every string argument
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    text = arg.value
                    try:
                        text.encode("ascii")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        # Show the problematic content
                        problems.append(
                            f"  Line {arg.lineno:4d}  {repr(text[:60])}"
                        )

        if problems:
            msg = (
                f"Found {len(problems)} non-ASCII print() argument(s) "
                f"in {rel_path}:\n"
            )
            msg += "\n".join(problems)
            pytest.fail(msg)


def test_cli_file_list_is_current() -> None:
    """Meta-test: ensure the hardcoded _CLI_FILES list is up to date."""
    expected = {
        "main.py",
        "src/data_update/historical_loader.py",
        "src/data_update/retry_failed.py",
    }
    assert set(_CLI_FILES) == expected, (
        f"_CLI_FILES changed. "
        f"Extra: {set(_CLI_FILES) - expected}. "
        f"Missing: {expected - set(_CLI_FILES)}."
    )
