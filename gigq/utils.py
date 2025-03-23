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
    Set up logging for GigQ.

    Args:
        level: The logging level to use.
    """
    logger.setLevel(level)
    # Only add a handler if one doesn't exist already
    if not logger.handlers:
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
