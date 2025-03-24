"""
Worker class for GigQ.

This module contains the Worker class which processes jobs from the queue.
"""

import json
import logging
import signal
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from .job_status import JobStatus
from .db_utils import get_connection, close_connection

# Configure logging
logger = logging.getLogger("gigq.worker")


class Worker:
    """
    A worker that processes jobs from the queue.
    """

    def __init__(
        self, db_path: str, worker_id: Optional[str] = None, polling_interval: int = 5
    ):
        """
        Initialize a worker.

        Args:
            db_path: Path to the SQLite database file.
            worker_id: Unique identifier for this worker (auto-generated if not provided).
            polling_interval: How often to check for new jobs, in seconds.
        """
        self.db_path = db_path
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"
        self.polling_interval = polling_interval
        self.running = False
        self.current_job_id = None
        self.logger = logging.getLogger(f"gigq.worker.{self.worker_id}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a connection to the SQLite database with appropriate settings.

        The connection is cached in thread-local storage for reuse.

        Returns:
            A SQLite connection.
        """
        return get_connection(self.db_path)

    def _import_function(self, module_name: str, function_name: str) -> Callable:
        """
        Dynamically import a function.

        Args:
            module_name: The name of the module containing the function.
            function_name: The name of the function to import.

        Returns:
            The imported function.
        """
        import importlib

        module = importlib.import_module(module_name)
        return getattr(module, function_name)

    def _claim_job(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to claim a job from the queue.

        Returns:
            A job dictionary if a job was claimed, None otherwise.
        """
        conn = self._get_connection()

        try:
            # Ensure transaction isolation
            conn.execute("BEGIN EXCLUSIVE TRANSACTION")

            # First, check for ready jobs with no dependencies
            cursor = conn.execute(
                """
                SELECT j.* FROM jobs j
                WHERE j.status = ?
                AND (j.dependencies IS NULL OR j.dependencies = '[]')
                ORDER BY j.priority DESC, j.created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,),
            )

            job = cursor.fetchone()

            if not job:
                # Then look for jobs with dependencies and check if they're all completed
                cursor = conn.execute(
                    "SELECT id, dependencies FROM jobs WHERE status = ? AND dependencies IS NOT NULL AND dependencies != '[]'",
                    (JobStatus.PENDING.value,),
                )

                potential_jobs = cursor.fetchall()
                for potential_job in potential_jobs:
                    dependencies = json.loads(potential_job["dependencies"])
                    if not dependencies:
                        continue

                    # Check if all dependencies are completed
                    placeholders = ",".join(["?"] * len(dependencies))
                    query = f"SELECT COUNT(*) as count FROM jobs WHERE id IN ({placeholders}) AND status != ?"
                    cursor = conn.execute(
                        query, dependencies + [JobStatus.COMPLETED.value]
                    )
                    result = cursor.fetchone()

                    if result and result["count"] == 0:
                        # All dependencies satisfied, get the full job
                        cursor = conn.execute(
                            "SELECT * FROM jobs WHERE id = ?", (potential_job["id"],)
                        )
                        job = cursor.fetchone()
                        break

            if not job:
                conn.rollback()
                return None

            job_id = job["id"]
            now = datetime.now().isoformat()

            # Update the job status to running
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, worker_id = ?, started_at = ?, updated_at = ?, attempts = attempts + 1
                WHERE id = ?
                """,
                (JobStatus.RUNNING.value, self.worker_id, now, now, job_id),
            )

            # Record execution start
            execution_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO job_executions (id, job_id, worker_id, status, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (execution_id, job_id, self.worker_id, JobStatus.RUNNING.value, now),
            )

            # Commit the transaction
            conn.commit()

            # Get the updated job
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            job = cursor.fetchone()

            result = dict(job)

            # Deserialize JSON fields
            if result["params"]:
                result["params"] = json.loads(result["params"])
            if result["dependencies"]:
                result["dependencies"] = json.loads(result["dependencies"])

            result["execution_id"] = execution_id

            return result
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Database error when claiming job: {e}")
            return None

    def _complete_job(
        self,
        job_id: str,
        execution_id: str,
        status: JobStatus,
        result: Any = None,
        error: str = None,
    ):
        """
        Mark a job as completed or failed.

        Args:
            job_id: The ID of the job.
            execution_id: The ID of the execution.
            status: The final status of the job.
            result: The result of the job (if successful).
            error: Error message (if failed).
        """
        conn = self._get_connection()
        now = datetime.now().isoformat()
        result_json = json.dumps(result) if result is not None else None

        with conn:
            # Update the job
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, completed_at = ?, 
                    result = ?, error = ?, worker_id = NULL
                WHERE id = ?
                """,
                (status.value, now, now, result_json, error, job_id),
            )

            # Update the execution record
            conn.execute(
                """
                UPDATE job_executions
                SET status = ?, completed_at = ?, result = ?, error = ?
                WHERE id = ?
                """,
                (status.value, now, result_json, error, execution_id),
            )

    def _check_for_timeouts(self):
        """Check for jobs that have timed out and mark them accordingly."""
        conn = self._get_connection()

        with conn:
            cursor = conn.execute(
                """
                SELECT j.id, j.timeout, j.started_at, j.worker_id, j.attempts, j.max_attempts
                FROM jobs j
                WHERE j.status = ?
                """,
                (JobStatus.RUNNING.value,),
            )

            running_jobs = cursor.fetchall()
            now = datetime.now()

            for job in running_jobs:
                if not job["started_at"]:
                    continue

                started_at = datetime.fromisoformat(job["started_at"])
                timeout_seconds = job["timeout"] or 300  # Default 5 minutes

                if now - started_at > timedelta(seconds=timeout_seconds):
                    # Job has timed out
                    status = (
                        JobStatus.PENDING
                        if job["attempts"] < job["max_attempts"]
                        else JobStatus.TIMEOUT
                    )

                    self.logger.warning(
                        f"Job {job['id']} timed out after {timeout_seconds} seconds"
                    )

                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?, worker_id = NULL,
                            error = ?
                        WHERE id = ?
                        """,
                        (
                            status.value,
                            now.isoformat(),
                            f"Job timed out after {timeout_seconds} seconds",
                            job["id"],
                        ),
                    )

                    # Also update any execution records
                    conn.execute(
                        """
                        UPDATE job_executions
                        SET status = ?, completed_at = ?, error = ?
                        WHERE job_id = ? AND status = ?
                        """,
                        (
                            JobStatus.TIMEOUT.value,
                            now.isoformat(),
                            f"Job timed out after {timeout_seconds} seconds",
                            job["id"],
                            JobStatus.RUNNING.value,
                        ),
                    )

    def process_one(self) -> bool:
        """
        Process a single job from the queue.

        Returns:
            True if a job was processed, False if no job was available.
        """
        # Check for timed out jobs first
        self._check_for_timeouts()

        # Try to claim a job
        job = self._claim_job()
        if not job:
            return False

        job_id = job["id"]
        execution_id = job["execution_id"]
        self.current_job_id = job_id

        self.logger.info(f"Processing job {job_id} ({job['name']})")

        try:
            # Load the function
            func = self._import_function(job["function_module"], job["function_name"])

            # Execute the job
            start_time = time.time()
            result = func(**job["params"])
            execution_time = time.time() - start_time

            # Record success
            self.logger.info(
                f"Job {job_id} completed successfully in {execution_time:.2f}s"
            )
            self._complete_job(job_id, execution_id, JobStatus.COMPLETED, result=result)

        except Exception as e:
            # Record failure
            self.logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

            # Check if we need to retry
            if job["attempts"] < job["max_attempts"]:
                # We'll retry
                conn = self._get_connection()
                with conn:
                    now = datetime.now().isoformat()
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?, worker_id = NULL,
                            error = ?
                        WHERE id = ?
                        """,
                        (JobStatus.PENDING.value, now, str(e), job_id),
                    )

                    # Update the execution record
                    conn.execute(
                        """
                        UPDATE job_executions
                        SET status = ?, completed_at = ?, error = ?
                        WHERE id = ?
                        """,
                        (JobStatus.FAILED.value, now, str(e), execution_id),
                    )
            else:
                # Max retries reached
                self._complete_job(job_id, execution_id, JobStatus.FAILED, error=str(e))

        finally:
            self.current_job_id = None

        return True

    def start(self):
        """Start the worker process."""
        self.running = True
        self.logger.info(f"Worker {self.worker_id} starting")

        # Set up signal handlers
        def handle_signal(sig, frame):
            self.logger.info(f"Received signal {sig}, stopping worker")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self.running:
                # Process one job
                job_processed = self.process_one()

                # If no job was available, wait before checking again
                if not job_processed:
                    time.sleep(self.polling_interval)
        finally:
            self.logger.info(f"Worker {self.worker_id} stopped")
            close_connection(self.db_path)

    def stop(self):
        """Stop the worker process."""
        self.running = False
        self.logger.info(f"Worker {self.worker_id} stopping")

    def close(self):
        """Close the database connection used by this worker."""
        close_connection(self.db_path)
