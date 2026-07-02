"""
Logger utility — get a named logger with the project's default configuration.

Usage::

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("…")
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for the given module name.

    Parameters
    ----------
    name : str
        Usually ``__name__`` from the calling module.

    Returns
    -------
    logging.Logger
    """
    return logging.getLogger(name)
