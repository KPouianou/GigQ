"""
GigQ: A lightweight job queue system with SQLite backend.
"""

# Import and re-export the main classes from their respective modules
from .job import Job
from .job_queue import JobQueue
from .job_status import JobStatus
from .worker import Worker
from .workflow import Workflow
from .db_utils import close_connections

# Initialize logging with default settings
from .utils import setup_logging

setup_logging()

# Get version from installed package
try:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("gigq")
    except PackageNotFoundError:
        # Package is not installed
        __version__ = "0.1.1"  # Default development version
except ImportError:
    # Fallback for Python < 3.8
    # Make importlib_metadata optional, only needed for Python < 3.8
    __version__ = "0.1.1"  # Default development version

# Define what gets imported with "from gigq import *"
__all__ = ["Job", "JobQueue", "JobStatus", "Worker", "Workflow", "close_connections"]
