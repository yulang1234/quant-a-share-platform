"""
Encoding integrity tests -- verify that key project files are valid UTF-8,
contain no garbled characters, and have correct structure.

All checks use byte-level assertions to avoid terminal display issues.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# =====================================================================
#  core_500.csv integrity
# =====================================================================

class TestCsvIntegrity:
    CSV_PATH = _PROJECT_ROOT / "data" / "stock_pool" / "core_500.csv"

    def test_file_exists(self) -> None:
        assert self.CSV_PATH.exists(), f"CSV not found: {self.CSV_PATH}"

    def test_all_rows_have_9_columns(self) -> None:
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert len(header) == 9, f"Header has {len(header)} columns, expected 9"
            for i, row in enumerate(reader, 2):
                assert len(row) == 9, \
                    f"Row {i} has {len(row)} columns: {row}"

    def test_header_names(self) -> None:
        expected = [
            "stock_code", "stock_name", "market", "exchange", "pool_name",
            "source", "is_active", "is_blacklisted", "note",
        ]
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == expected, f"Header mismatch: {header}"

    def test_stock_code_is_6_digits(self) -> None:
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for i, row in enumerate(reader, 2):
                code = row[0]
                assert len(code) == 6 and code.isdigit(), \
                    f"Row {i} invalid stock_code: {repr(code)}"

    def test_market_is_a_gu(self) -> None:
        """Verify market field contains the two-byte UTF-8 for 'A股'."""
        # A股 in UTF-8: A (0x41) + 股 (E8 82 A1)
        with open(self.CSV_PATH, "rb") as f:
            raw = f.read()
        # Find a data row and check market field
        lines = raw.split(b"\n")
        for i, line in enumerate(lines[1:], 2):
            if not line.strip():
                continue
            parts = line.split(b",")
            if len(parts) >= 3:
                market = parts[2]
                assert market == b"A\xe8\x82\xa1", \
                    f"Row {i} market field is {market!r}, expected UTF-8 'A股'"

    def test_exchange_is_valid_sh_sz_bj(self) -> None:
        """Exchanges cover Shanghai (SH), Shenzhen (SZ), and Beijing (BJ).

        The Beijing Stock Exchange (BSE) hosts stocks whose codes start
        with ``8`` or ``4``; these are part of the curated core_500 pool.
        """
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for i, row in enumerate(reader, 2):
                exch = row[3]
                assert exch in ("SH", "SZ", "BJ"), \
                    f"Row {i} invalid exchange: {repr(exch)}"

    def test_pool_name_is_core_500(self) -> None:
        with open(self.CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for i, row in enumerate(reader, 2):
                assert row[4] == "core_500", \
                    f"Row {i} pool_name: {repr(row[4])}"


# =====================================================================
#  Python source encoding integrity
# =====================================================================

_SOURCE_FILES = [
    "src/data_source/akshare_client.py",
    "main.py",
    "ui/streamlit_app.py",
    "src/universe/stock_pool.py",
    "README.md",
    "docs/roadmap.md",
]

# Characters that indicate GBK/Windows-1252 -> UTF-8 mojibake or corrupted encoding
_GARBLED_FRAGMENTS = [
    "杩", "绋", "鐐", "闂",          # common GBK/Windows-1252 mojibake fragments
    "鑲", "鏃", "鈥", "鉁", "锛", "涓",  # reported garbled Chinese fragments
    "æ", "Ã",                       # Latin mojibake fragments
]


class TestSourceEncoding:
    @pytest.mark.parametrize("rel_path", _SOURCE_FILES)
    def test_file_is_valid_utf8(self, rel_path: str) -> None:
        filepath = _PROJECT_ROOT / rel_path
        assert filepath.exists(), f"File not found: {filepath}"
        with open(filepath, "rb") as f:
            raw = f.read()
        # Check that the file decodes cleanly
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as e:
            pytest.fail(f"{rel_path} is not valid UTF-8: {e}")

    @pytest.mark.parametrize("rel_path", _SOURCE_FILES)
    def test_no_garbled_fragments(self, rel_path: str) -> None:
        filepath = _PROJECT_ROOT / rel_path
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        for fragment in _GARBLED_FRAGMENTS:
            if fragment in text:
                pytest.fail(
                    f"{rel_path} contains garbled fragment "
                    f"{repr(fragment)}"
                )


# =====================================================================
#  akshare_client.py specific: COLUMN_MAP must have correct Chinese keys
# =====================================================================

class TestAkshareColumnMap:
    CLIENT_PATH = _PROJECT_ROOT / "src" / "data_source" / "akshare_client.py"

    def _read_file(self) -> str:
        with open(self.CLIENT_PATH, "r", encoding="utf-8") as f:
            return f.read()

    @pytest.mark.parametrize(
        "expected_char",
        [
            "日期",
            "股票代码",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "振幅",
            "涨跌幅",
            "涨跌额",
            "换手率",
        ],
    )
    def test_column_map_has_chinese_key(self, expected_char: str) -> None:
        text = self._read_file()
        assert expected_char in text, (
            f"COLUMN_MAP missing key {repr(expected_char)}"
        )

    @pytest.mark.parametrize(
        "bad_char",
        [
            "鏃",  # garbled from 日
            "鑲",  # garbled from 股
            "鈥",  # garbled em dash
            "鉁",  # garbled
        ],
    )
    def test_column_map_no_garbled_chars(self, bad_char: str) -> None:
        text = self._read_file()
        if bad_char in text:
            pytest.fail(
                f"COLUMN_MAP contains garbled char {repr(bad_char)}"
            )


# =====================================================================
#  main.py output safety check
# =====================================================================

class TestMainAsciiSafety:
    MAIN_PATH = _PROJECT_ROOT / "main.py"

    def test_all_print_arguments_are_ascii(self) -> None:
        """Every string passed to print() in main.py must be ASCII-safe."""
        import ast

        with open(self.MAIN_PATH, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename="main.py")

        problems: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    try:
                        arg.value.encode("ascii")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        problems.append(
                            f"  L{arg.lineno}: {repr(arg.value[:60])}"
                        )

        if problems:
            pytest.fail(
                f"main.py has {len(problems)} non-ASCII print() arg(s):\n"
                + "\n".join(problems)
            )
