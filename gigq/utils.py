"""
Utility functions for GigQ.

This module contains utility functions used across the GigQ package.
"""

import logging
from datetime import datetime
from typing import Optional

# Configure root logger
logger = logging.getLogger("gigq")


def setup_logging(level: int = logging.INFO) -> None:
    """
    Opt-in logging configuration for GigQ (stderr, standard format).

    Call this from an application entrypoint when you want GigQ's job/worker
    logs. Importing ``gigq`` does not configure handlers.
    """
    logger.setLevel(level)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def format_timestamp(timestamp: Optional[str]) -> str:
    """
    Format an ISO timestamp into a human-readable format.

    Args:
        timestamp: ISO format timestamp.

    Returns:
        Formatted timestamp string.
    """
    if not timestamp:
        return "-"
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp
