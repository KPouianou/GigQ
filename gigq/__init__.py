"""
GigQ: A lightweight job queue system with SQLite backend.
"""

import logging

# Import and re-export the main classes from their respective modules
from .job import Job
from .job_queue import JobQueue
from .job_status import JobStatus
from .worker import Worker
from .workflow import Workflow
from .db_utils import close_connections
from .decorators import task

from .utils import setup_logging

# Library logging: do not configure handlers on import (see Python logging HOWTO).
# NullHandler + no propagation avoids leaking to the root logger's lastResort.
_lib_logger = logging.getLogger("gigq")
_lib_logger.addHandler(logging.NullHandler())
_lib_logger.propagate = False

# Get version from installed package
try:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("gigq")
    except PackageNotFoundError:
        # Package is not installed
        __version__ = "0.4.0"  # Default development version
except ImportError:
    # Fallback for Python < 3.8
    # Make importlib_metadata optional, only needed for Python < 3.8
    __version__ = "0.4.0"  # Default development version

# Define what gets imported with "from gigq import *"
__all__ = [
    "Job",
    "JobQueue",
    "JobStatus",
    "Worker",
    "Workflow",
    "close_connections",
    "setup_logging",
    "task",
]
