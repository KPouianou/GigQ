"""
Job class for GigQ.

This module contains the Job class which represents a unit of work to be executed.
"""

import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class Job:
    """
    Represents a job to be executed by the queue system.
    """

    def __init__(
        self,
        name: str,
        function: Callable,
        params: Dict[str, Any] = None,
        priority: int = 0,
        dependencies: List[str] = None,
        max_attempts: int = 3,
        timeout: int = 300,
        description: str = "",
        pass_parent_results: Optional[bool] = None,
    ):
        """
        Initialize a new job.

        Args:
            name: A name for the job.
            function: The function to execute.
            params: Parameters to pass to the function.
            priority: Job priority (higher numbers executed first).
            dependencies: List of job IDs that must complete before this job runs.
            max_attempts: Maximum number of execution attempts.
            timeout: Maximum runtime in seconds before the job is considered hung.
            description: Optional description of the job.
            pass_parent_results: Whether to inject ``parent_results`` when this job
                has dependencies. ``None`` (default) means auto: inject only if the
                function accepts a ``parent_results`` parameter or ``**kwargs``.
                ``True`` always injects (when there are dependencies); ``False`` never
                injects. Injected values are a dict mapping each parent job ID to
                that job's deserialized result from the database.
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.function = function
        self.params = params or {}
        self.priority = priority
        self.dependencies = dependencies or []
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.description = description
        self.pass_parent_results = pass_parent_results
        self.created_at = datetime.now().isoformat()
