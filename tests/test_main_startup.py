"""
Startup-error handling tests for ``main.py``.

Covers the V0.4 Codex review P0-1 requirement: ``python main.py`` must
not crash with a raw traceback when the DuckDB file is locked by another
process, and must instead print an actionable ASCII message and exit
non-zero.  Also covers the P0-3 requirement that the version banner text
no longer mentions ``V0.3 scope complete`` and does mention ``V0.4``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# =====================================================================
#  P0-1 — handle_startup_error()
# =====================================================================

class TestHandleStartupError:
    """The startup-error helper must return 1 and never raise."""

    def _import_main(self):
        """Import (or reload) main.py in isolation.

        We avoid using the real DuckDB path so the import itself never
        touches the database.  ``main`` only opens the DB inside
        ``main()``, not at import time, so a plain reload is safe.
        """
        import main as main_mod
        importlib.reload(main_mod)
        return main_mod

    def test_locked_returns_1_and_does_not_raise(self, capsys) -> None:
        """A DuckDB lock-like exception returns 1 without raising."""
        main_mod = self._import_main()
        db_path = Path("/tmp/quant_a_share.duckdb")

        rc = main_mod.handle_startup_error(
            Exception(
                "Cannot open file '/tmp/quant_a_share.duckdb': "
                "another process is using this file"
            ),
            db_path,
        )

        assert rc == 1
        out = capsys.readouterr().out
        # Friendly messages -- all must be present, all ASCII.
        assert "[ERROR] DuckDB database is currently locked by another process." in out
        assert "[INFO] Please close other Python, Streamlit, or data update" in out
        assert "processes and try again." in out
        assert str(db_path) in out
        # No traceback leaks into stdout
        assert "Traceback" not in out

    def test_other_exception_returns_1(self, capsys) -> None:
        """Non-lock errors still exit 1 with a short message."""
        main_mod = self._import_main()
        db_path = Path("/tmp/quant_a_share.duckdb")

        rc = main_mod.handle_startup_error(
            RuntimeError("something else broke"),
            db_path,
        )

        assert rc == 1
        out = capsys.readouterr().out
        assert "[ERROR] Startup failed: RuntimeError: something else broke" in out
        assert str(db_path) in out
        assert "Traceback" not in out

    def test_output_is_ascii_safe(self, capsys) -> None:
        """All printed output must encode to ASCII (Codex requirement)."""
        main_mod = self._import_main()
        main_mod.handle_startup_error(
            Exception("Cannot open file 'x.duckdb': another process is using this file"),
            Path("/tmp/x.duckdb"),
        )
        out = capsys.readouterr().out
        # Should not raise — every printed char is ASCII.
        out.encode("ascii")

    def test_lock_signals_match_variants(self) -> None:
        """All three documented lock-signal phrasings are detected."""
        main_mod = self._import_main()
        db_path = Path("/tmp/x.duckdb")
        variants = [
            "Cannot open file 'x.duckdb'",
            "another process is using this file",
            "being used by another process",
        ]
        for v in variants:
            # Indirect verification: the lock path prints the friendly
            # message rather than the generic "Startup failed" fallback.
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main_mod.handle_startup_error(Exception(v), db_path)
            assert rc == 1
            assert "locked by another process" in buf.getvalue(), (
                f"variant not recognised as a lock signal: {v!r}"
            )


# =====================================================================
#  P0-1 — main() returns int and increments cleanly on startup error
# =====================================================================

class TestMainSignature:
    def test_main_returns_int_on_success(self) -> None:
        """``main`` must be annotated as returning ``int``.

        We assert the signature rather than running ``main()`` (which
        would hit the real DuckDB and could collide with a concurrent
        Streamlit / test process).  The contract is: 0 on success, 1 on
        startup failure.
        """
        import inspect
        import main as main_mod
        importlib.reload(main_mod)
        sig = inspect.signature(main_mod.main)
        assert sig.return_annotation is int or sig.return_annotation == "int"

    def test_main_returns_nonzero_on_db_init_failure(
        self, monkeypatch, capsys, tmp_path
    ) -> None:
        """When ``init_database`` raises, ``main`` returns 1 gracefully.

        We monkey-patch ``init_database`` to raise a lock-style error so
        ``main()`` exercises the friendly-failure path end-to-end
        without touching the real DuckDB file.
        """
        import main as main_mod
        importlib.reload(main_mod)

        def _fail(*_a, **_k):
            raise Exception(
                "Cannot open file 'x.duckdb': "
                "another process is using this file"
            )

        monkeypatch.setattr(main_mod, "init_database", _fail)
        # Ensure ensure_dirs is a no-op so the test never writes.
        monkeypatch.setattr(main_mod, "ensure_dirs", lambda: None)

        rc = main_mod.main()

        assert rc == 1
        out = capsys.readouterr().out
        assert "[ERROR] DuckDB database is currently locked" in out
        assert "Traceback" not in out


# =====================================================================
#  P0-3 — version banner text
# =====================================================================

class TestVersionText:
    MAIN_PATH = PROJECT_ROOT / "main.py"

    def _src(self) -> str:
        return self.MAIN_PATH.read_text(encoding="utf-8")

    def test_no_v03_scope_complete(self) -> None:
        """The misleading V0.3 conclusion line must be gone."""
        src = self._src()
        assert "V0.3 scope complete" not in src, (
            "main.py still prints 'V0.3 scope complete' — update version text"
        )
        assert "historical data initialisation)." not in src

    def test_mentions_v14(self) -> None:
        src = self._src()
        assert "V1.4" in src

    def test_v14_scope_lines_present(self) -> None:
        src = self._src()
        assert "[INFO] V1.4 scope: streamlit visualization upgrade." in src

    def test_main_print_strings_are_ascii(self) -> None:
        """Every constant passed to print() in main.py is ASCII-safe."""
        import ast

        tree = ast.parse(self._src(), filename=str(self.MAIN_PATH))
        problems = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Name) and func.id == "print"):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    try:
                        arg.value.encode("ascii")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        problems.append(f"L{arg.lineno}: {arg.value[:60]!r}")
        assert not problems, f"non-ASCII print() args: {problems}"