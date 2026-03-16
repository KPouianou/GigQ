"""
Workflow class for GigQ.

This module contains the Workflow class which helps define and manage workflows
with dependent jobs.
"""

from typing import Any, Dict, List, Optional

from .job import Job
from .job_queue import JobQueue


class Workflow:
    """
    A utility class to help define workflows of dependent jobs.
    """

    def __init__(self, name: str):
        """
        Initialize a new workflow.

        Args:
            name: Name of the workflow.
        """
        self.name = name
        self.jobs = []
        self.job_map = {}

    def add_job(self, job: Job, depends_on: List[Job] = None) -> Job:
        """
        Add a job to the workflow, with optional dependencies.

        Args:
            job: The job to add.
            depends_on: List of jobs this job depends on.

        Returns:
            The job that was added.
        """
        if depends_on:
            job.dependencies = [j.id for j in depends_on]

        self.jobs.append(job)
        self.job_map[job.id] = job
        return job

    def add_task(
        self,
        decorated_fn: Any,
        params: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[Job]] = None,
    ) -> Job:
        """
        Add a @task-decorated function to the workflow.

        Args:
            decorated_fn: A function decorated with @task.
            params: Dict of keyword arguments to pass to the function.
            depends_on: List of jobs this task depends on.

        Returns:
            The Job that was created and added.

        Raises:
            TypeError: If decorated_fn is not a @task-decorated function.
        """
        from .decorators import TaskWrapper

        if not isinstance(decorated_fn, TaskWrapper):
            raise TypeError(
                "add_task() requires a @task-decorated function. "
                "Use add_job() for plain Job objects."
            )
        job = decorated_fn.to_job(**(params or {}))
        return self.add_job(job, depends_on=depends_on)

    def submit_all(self, queue: JobQueue) -> List[str]:
        """
        Submit all jobs in the workflow to a queue.

        Args:
            queue: The job queue to submit to.

        Returns:
            List of job IDs that were submitted.
        """
        job_ids = []
        for job in self.jobs:
            job_id = queue.submit(job)
            job_ids.append(job_id)
        return job_ids
