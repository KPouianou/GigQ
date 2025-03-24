"""
GigQ: A lightweight job queue system with SQLite backend
"""

# Import directly from gigq package instead of relative import
from gigq import Job, JobQueue, Worker, Workflow, JobStatus

# Get version from installed package
try:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("gigq")
    except PackageNotFoundError:
        # Package is not installed
        __version__ = "0.2.0"  # Default development version
except ImportError:
    # Fallback for Python < 3.8
    # Make importlib_metadata optional, only needed for Python < 3.8
    __version__ = "0.2.0"  # Default development version

__all__ = ["Job", "JobQueue", "Worker", "Workflow", "JobStatus"]
