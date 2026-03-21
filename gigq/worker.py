"""
Worker class for GigQ.

This module contains the Worker class which processes jobs from the queue.
"""

import inspect
import json
import logging
import signal
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .job_status import JobStatus
from .db_utils import get_connection, close_connection
from .job_queue import _normalize_pass_parent_results_db_value

# Configure logging
logger = logging.getLogger("gigq.worker")


class Worker:
    """
    A worker that processes jobs from the queue.

    Supports concurrent job processing via the ``concurrency`` parameter.
    When concurrency > 1, multiple threads each independently claim and
    execute jobs from the queue.
    """

    def __init__(
        self,
        db_path: str,
        worker_id: Optional[str] = None,
        polling_interval: int = 5,
        concurrency: int = 1,
    ):
        """
        Initialize a worker.

        Args:
            db_path: Path to the SQLite database file.
            worker_id: Unique identifier for this worker (auto-generated if not provided).
            polling_interval: How often to check for new jobs, in seconds.
            concurrency: Number of concurrent job-processing threads (must be >= 1).
        """
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")

        self.db_path = db_path
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"
        self.polling_interval = polling_interval
        self.concurrency = concurrency
        self.running = False
        self._thread_local = threading.local()
        self.logger = logging.getLogger(f"gigq.worker.{self.worker_id}")

    @property
    def _active_worker_id(self) -> str:
        """Return the thread-specific worker ID, falling back to the base ID."""
        return getattr(self._thread_local, "worker_id", self.worker_id)

    @property
    def _log(self) -> logging.Logger:
        """Return the thread-specific logger, falling back to the base logger."""
        return getattr(self._thread_local, "logger", self.logger)

    @property
    def current_job_id(self) -> Optional[str]:
        """The ID of the job currently being processed by this thread."""
        return getattr(self._thread_local, "current_job_id", None)

    @current_job_id.setter
    def current_job_id(self, value: Optional[str]):
        self._thread_local.current_job_id = value

    def _setup_thread_state(self, thread_index: int = 0):
        """
        Initialize per-thread state for a worker loop thread.

        Args:
            thread_index: Index of this thread (0-based). When concurrency == 1,
                          the worker ID is not suffixed.
        """
        if self.concurrency > 1:
            thread_worker_id = f"{self.worker_id}-{thread_index}"
        else:
            thread_worker_id = self.worker_id

        self._thread_local.worker_id = thread_worker_id
        self._thread_local.logger = logging.getLogger(f"gigq.worker.{thread_worker_id}")
        self._thread_local.current_job_id = None

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a connection to the SQLite database with appropriate settings.

        The connection is cached in thread-local storage for reuse.

        Returns:
            A SQLite connection.
        """
        return get_connection(self.db_path)

    @staticmethod
    def _function_accepts_parent_results(func: Callable) -> bool:
        """True if ``func`` can receive an injected ``parent_results`` argument."""
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            return False
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                return True
        return "parent_results" in sig.parameters

    def _should_inject_parent_results(
        self, job: Dict[str, Any], func: Callable
    ) -> bool:
        dependencies: List[str] = job.get("dependencies") or []
        if not dependencies:
            return False
        mode = job.get("pass_parent_results")
        if mode is False:
            return False
        if mode is True:
            return True
        return self._function_accepts_parent_results(func)

    def _load_parent_results(
        self, conn: sqlite3.Connection, parent_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Build an ordered dict of parent job ID -> deserialized result.

        Keys follow the order of ``parent_ids`` (dependency order from the job row).
        """
        if not parent_ids:
            return {}
        placeholders = ",".join("?" * len(parent_ids))
        cursor = conn.execute(
            f"SELECT id, result FROM jobs WHERE id IN ({placeholders})",
            parent_ids,
        )
        by_id = {row["id"]: row["result"] for row in cursor.fetchall()}
        out: Dict[str, Any] = {}
        for pid in parent_ids:
            raw = by_id.get(pid)
            if raw is None:
                out[pid] = None
            else:
                out[pid] = json.loads(raw)
        return out

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
        active_worker_id = self._active_worker_id

        try:
            # Ensure transaction isolation
            conn.execute("BEGIN EXCLUSIVE TRANSACTION")

            now_iso = datetime.now().isoformat()

            # First, check for ready jobs with no dependencies
            cursor = conn.execute(
                """
                SELECT j.* FROM jobs j
                WHERE j.status = ?
                AND (j.dependencies IS NULL OR j.dependencies = '[]')
                AND (j.retry_after IS NULL OR j.retry_after <= ?)
                ORDER BY j.priority DESC, j.created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value, now_iso),
            )

            job = cursor.fetchone()

            if not job:
                # Then look for jobs with dependencies and check if they're all completed
                cursor = conn.execute(
                    "SELECT id, dependencies FROM jobs WHERE status = ? AND dependencies IS NOT NULL AND dependencies != '[]' AND (retry_after IS NULL OR retry_after <= ?)",
                    (JobStatus.PENDING.value, now_iso),
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
                (JobStatus.RUNNING.value, active_worker_id, now, now, job_id),
            )

            # Record execution start
            execution_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO job_executions (id, job_id, worker_id, status, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (execution_id, job_id, active_worker_id, JobStatus.RUNNING.value, now),
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

            if "pass_parent_results" in result:
                result["pass_parent_results"] = _normalize_pass_parent_results_db_value(
                    result["pass_parent_results"]
                )
            else:
                result["pass_parent_results"] = None

            result["execution_id"] = execution_id

            return result
        except sqlite3.Error as e:
            conn.rollback()
            self._log.error(f"Database error when claiming job: {e}")
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
                SELECT j.id, j.timeout, j.started_at, j.worker_id, j.attempts, j.max_attempts, j.retry_delay
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
                    will_retry = job["attempts"] < job["max_attempts"]
                    status = JobStatus.PENDING if will_retry else JobStatus.TIMEOUT

                    retry_after = None
                    if will_retry:
                        retry_delay = job["retry_delay"] or 0
                        if retry_delay > 0:
                            retry_after = (
                                now + timedelta(seconds=retry_delay)
                            ).isoformat()

                    self._log.warning(
                        f"Job {job['id']} timed out after {timeout_seconds} seconds"
                    )

                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?, worker_id = NULL,
                            error = ?, retry_after = ?
                        WHERE id = ?
                        """,
                        (
                            status.value,
                            now.isoformat(),
                            f"Job timed out after {timeout_seconds} seconds",
                            retry_after,
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

        self._log.info(f"Processing job {job_id} ({job['name']})")

        try:
            # Load the function
            func = self._import_function(job["function_module"], job["function_name"])

            params = dict(job["params"])
            if self._should_inject_parent_results(job, func):
                conn = self._get_connection()
                params["parent_results"] = self._load_parent_results(
                    conn, job["dependencies"]
                )

            # Execute the job
            start_time = time.time()
            result = func(**params)
            execution_time = time.time() - start_time

            # Record success
            self._log.info(
                f"Job {job_id} completed successfully in {execution_time:.2f}s"
            )
            self._complete_job(job_id, execution_id, JobStatus.COMPLETED, result=result)

        except Exception as e:
            # Record failure
            self._log.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

            # Check if we need to retry
            if job["attempts"] < job["max_attempts"]:
                # We'll retry
                conn = self._get_connection()
                with conn:
                    now_dt = datetime.now()
                    now = now_dt.isoformat()
                    retry_delay = job.get("retry_delay") or 0
                    retry_after = None
                    if retry_delay > 0:
                        retry_after = (
                            now_dt + timedelta(seconds=retry_delay)
                        ).isoformat()
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?, worker_id = NULL,
                            error = ?, retry_after = ?
                        WHERE id = ?
                        """,
                        (JobStatus.PENDING.value, now, str(e), retry_after, job_id),
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

    def _worker_loop(self, thread_index: int = 0):
        """
        Run the job-processing loop for a single worker thread.

        Args:
            thread_index: Index of this thread (0-based).
        """
        self._setup_thread_state(thread_index)
        thread_log = self._log
        thread_log.info(f"Worker thread {self._active_worker_id} starting")

        try:
            while self.running:
                job_processed = self.process_one()
                if not job_processed:
                    time.sleep(self.polling_interval)
        except Exception:
            thread_log.error("Worker thread crashed", exc_info=True)
        finally:
            thread_log.info(f"Worker thread {self._active_worker_id} stopped")
            close_connection(self.db_path)

    def start(self):
        """Start the worker process."""
        self.running = True
        self.logger.info(f"Worker {self.worker_id} starting")

        # Set up signal handlers (only possible from the main thread)
        def handle_signal(sig, frame):
            self.logger.info(f"Received signal {sig}, stopping worker")
            self.running = False

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)

        try:
            if self.concurrency == 1:
                self._worker_loop(0)
            else:
                self.logger.info(
                    f"Starting {self.concurrency} concurrent worker threads"
                )
                with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                    futures = [
                        executor.submit(self._worker_loop, i)
                        for i in range(self.concurrency)
                    ]
                    # shutdown(wait=True) is implicit via the context manager;
                    # threads wind down after self.running is set to False
        finally:
            self.logger.info(f"Worker {self.worker_id} stopped")

    def stop(self):
        """Stop the worker process."""
        self.running = False
        self.logger.info(f"Worker {self.worker_id} stopping")

    def close(self):
        """Close the database connection used by this worker."""
        close_connection(self.db_path)
