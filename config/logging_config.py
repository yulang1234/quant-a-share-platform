"""
Logging configuration for the quant research platform.

Provides a consistent log format across all modules with dual output:
- Console (stderr-free, stream to stdout)
- Rotating file — ``logs/test.log`` in test mode, ``logs/app.log`` otherwise.

Test mode is detected via ``PYTEST_CURRENT_TEST`` or ``APP_ENV=test``.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOG_LEVEL, get_project_root

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 5


def _is_test_env() -> bool:
    """Return True when running under pytest or APP_ENV=test."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    if os.getenv("APP_ENV", "").lower() == "test":
        return True
    return False


def _get_log_file_name() -> str:
    return "test.log" if _is_test_env() else "app.log"


def _get_log_dir() -> Path:
    log_dir = get_project_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _create_file_handler() -> RotatingFileHandler:
    log_path = _get_log_dir() / _get_log_file_name()
    handler = RotatingFileHandler(
        str(log_path),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def setup_logging(level: str = None) -> None:
    """Configure root logger with console + file handlers.

    Test runs write to ``logs/test.log``; production runs write to
    ``logs/app.log``.  Safe to call multiple times.
    """
    resolved_level = (level or LOG_LEVEL).upper()
    root = logging.getLogger()
    root.setLevel(resolved_level)

    _replace_or_add_handler(
        root,
        lambda h: isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler),
        lambda: _make_console_handler(),
    )
    _replace_or_add_handler(
        root,
        lambda h: isinstance(h, RotatingFileHandler),
        _create_file_handler,
    )


def _make_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def _replace_or_add_handler(root, match_fn, factory) -> None:
    for i, h in enumerate(root.handlers):
        if match_fn(h):
            root.handlers[i] = factory()
            return
    root.addHandler(factory())
