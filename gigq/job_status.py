"""
JobStatus class for GigQ.

This module contains the JobStatus enum which represents the possible states of a job.
"""

from enum import Enum


class JobStatus(Enum):
    """Enum representing the possible states of a job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
