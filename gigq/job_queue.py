"""
JobQueue class for GigQ.

This module contains the JobQueue class which manages the storage and retrieval of jobs
using SQLite as a backend.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .job import Job
from .job_status import JobStatus
from .db_utils import get_connection, close_connection

# Configure logging
logger = logging.getLogger("gigq.job_queue")


class JobQueue:
    """
    Manages a queue of jobs using SQLite as a backend.
    """

    def __init__(self, db_path: str, initialize: bool = True):
        """
        Initialize the job queue.

        Args:
            db_path: Path to the SQLite database file.
            initialize: Whether to initialize the database if it doesn't exist.
        """
        self.db_path = db_path
        if initialize:
            self._initialize_db()

    def _initialize_db(self):
        """Create the necessary database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Jobs table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            function_name TEXT NOT NULL,
            function_module TEXT NOT NULL,
            params TEXT,
            priority INTEGER DEFAULT 0,
            dependencies TEXT,
            max_attempts INTEGER DEFAULT 3,
            timeout INTEGER DEFAULT 300,
            description TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            result TEXT,
            error TEXT,
            started_at TEXT,
            completed_at TEXT,
            worker_id TEXT
        )
        """
        )

        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs (priority)"
        )

        # Job executions table (for history)
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS job_executions (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        )
        """
        )

        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a connection to the SQLite database with appropriate settings.

        The connection is cached in thread-local storage for reuse.

        Returns:
            A SQLite connection.
        """
        return get_connection(self.db_path)

    def submit(self, job: Job) -> str:
        """
        Submit a job to the queue.

        Args:
            job: The job to submit.

        Returns:
            The ID of the submitted job.
        """
        conn = self._get_connection()

        # Store function as module and name for later import
        function_module = job.function.__module__
        function_name = job.function.__name__

        now = datetime.now().isoformat()

        # Insert the job into the database
        with conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, name, function_name, function_module, params, priority,
                    dependencies, max_attempts, timeout, description, status,
                    created_at, updated_at, attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.name,
                    function_name,
                    function_module,
                    json.dumps(job.params),
                    job.priority,
                    json.dumps(job.dependencies),
                    job.max_attempts,
                    job.timeout,
                    job.description,
                    JobStatus.PENDING.value,
                    job.created_at,
                    now,
                    0,
                ),
            )

        logger.info(f"Job submitted: {job.id} ({job.name})")
        return job.id

    def cancel(self, job_id: str) -> bool:
        """
        Cancel a pending job.

        Args:
            job_id: The ID of the job to cancel.

        Returns:
            True if the job was cancelled, False if it couldn't be cancelled.
        """
        conn = self._get_connection()

        with conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (
                    JobStatus.CANCELLED.value,
                    datetime.now().isoformat(),
                    job_id,
                    JobStatus.PENDING.value,
                ),
            )

        if cursor.rowcount > 0:
            logger.info(f"Job cancelled: {job_id}")
            return True
        else:
            logger.warning(
                f"Could not cancel job {job_id}, it may be already running or completed"
            )
            return False

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the current status of a job.

        Args:
            job_id: The ID of the job to check.

        Returns:
            A dictionary containing the job's status and related information.
        """
        conn = self._get_connection()

        cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_data = cursor.fetchone()

        if not job_data:
            return {"exists": False}

        result = dict(job_data)

        # Deserialize JSON fields
        if result["params"]:
            result["params"] = json.loads(result["params"])
        if result["dependencies"]:
            result["dependencies"] = json.loads(result["dependencies"])
        if result["result"]:
            result["result"] = json.loads(result["result"])

        result["exists"] = True

        # Get execution history
        cursor = conn.execute(
            "SELECT * FROM job_executions WHERE job_id = ? ORDER BY started_at ASC",
            (job_id,),
        )
        executions = [dict(row) for row in cursor.fetchall()]
        for execution in executions:
            if execution["result"]:
                execution["result"] = json.loads(execution["result"])

        result["executions"] = executions

        return result

    def list_jobs(
        self, status: Optional[Union[JobStatus, str]] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs in the queue, optionally filtered by status.

        Args:
            status: Filter jobs by this status.
            limit: Maximum number of jobs to return.

        Returns:
            A list of job dictionaries.
        """
        conn = self._get_connection()

        if status:
            if isinstance(status, JobStatus):
                status = status.value
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            )

        results = []
        for row in cursor.fetchall():
            job_dict = dict(row)

            # Deserialize JSON fields
            if job_dict["params"]:
                job_dict["params"] = json.loads(job_dict["params"])
            if job_dict["dependencies"]:
                job_dict["dependencies"] = json.loads(job_dict["dependencies"])
            if job_dict["result"]:
                job_dict["result"] = json.loads(job_dict["result"])

            results.append(job_dict)

        return results

    def clear_completed(self, before_timestamp: Optional[str] = None) -> int:
        """
        Clear completed jobs from the queue.

        Args:
            before_timestamp: Only clear jobs completed before this timestamp.

        Returns:
            Number of jobs cleared.
        """
        conn = self._get_connection()

        with conn:
            if before_timestamp:
                cursor = conn.execute(
                    "DELETE FROM jobs WHERE status IN (?, ?) AND completed_at < ?",
                    (
                        JobStatus.COMPLETED.value,
                        JobStatus.CANCELLED.value,
                        before_timestamp,
                    ),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM jobs WHERE status IN (?, ?)",
                    (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value),
                )

            return cursor.rowcount

    def requeue_job(self, job_id: str) -> bool:
        """
        Requeue a failed job, resetting its attempts.

        Args:
            job_id: The ID of the job to requeue.

        Returns:
            True if the job was requeued, False if not.
        """
        conn = self._get_connection()

        with conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, attempts = 0, error = NULL, updated_at = ?
                WHERE id = ? AND status IN (?, ?, ?)
                """,
                (
                    JobStatus.PENDING.value,
                    datetime.now().isoformat(),
                    job_id,
                    JobStatus.FAILED.value,
                    JobStatus.TIMEOUT.value,
                    JobStatus.CANCELLED.value,
                ),
            )

            return cursor.rowcount > 0

    def close(self) -> None:
        """Close the database connection for this thread."""
        close_connection(self.db_path)
