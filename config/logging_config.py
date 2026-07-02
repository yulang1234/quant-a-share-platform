"""
Logging configuration for the quant research platform.

Provides a consistent log format across all modules.
"""

import logging
import sys

from config.settings import LOG_LEVEL


_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = None) -> None:
    """Configure root logger with console handler.

    Parameters
    ----------
    level : str, optional
        Log level (DEBUG, INFO, WARNING, ERROR). Defaults to the value from
        settings / environment variable ``LOG_LEVEL``.
    """
    resolved_level = (level or LOG_LEVEL).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(resolved_level)
    # Avoid duplicate handlers when called multiple times
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers[0] = handler
