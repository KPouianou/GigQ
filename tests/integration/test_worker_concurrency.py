"""Tests for single-worker multi-thread concurrency (--concurrency N)."""

import os
import sqlite3
import tempfile
import threading
import time
import unittest

from gigq import Job, JobQueue, JobStatus, Worker
from gigq.db_utils import close_connections
from tests.job_functions import timed_job, work_counter_job, retry_job


class WorkerConcurrencyTestBase(unittest.TestCase):
    """Base class with setup/teardown for concurrency tests."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.queue = JobQueue(self.db_path)

        self.tracker_fd, self.tracker_db = tempfile.mkstemp(suffix=".db")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.queue.close()
        close_connections()
        os.close(self.db_fd)
        os.unlink(self.db_path)
        for suffix in ("-wal", "-shm"):
            sidecar = self.db_path + suffix
            if os.path.exists(sidecar):
                os.unlink(sidecar)

        os.close(self.tracker_fd)
        if os.path.exists(self.tracker_db):
            os.unlink(self.tracker_db)
        for suffix in ("-wal", "-shm"):
            sidecar = self.tracker_db + suffix
            if os.path.exists(sidecar):
                os.unlink(sidecar)


class TestParallelExecution(WorkerConcurrencyTestBase):
    """Verify that concurrency=N actually runs jobs in parallel."""

    def test_jobs_overlap_in_time(self):
        concurrency = 4
        num_jobs = 4
        sleep_duration = 0.5

        for i in range(num_jobs):
            job = Job(
                name=f"timed_{i}",
                function=timed_job,
                params={
                    "job_id": f"timed_{i}",
                    "tracker_db": self.tracker_db,
                    "duration": sleep_duration,
                },
            )
            self.queue.submit(job)

        worker = Worker(
            self.db_path,
            polling_interval=0.1,
            concurrency=concurrency,
        )

        def run_worker():
            worker.start()

        t = threading.Thread(target=run_worker)
        t.daemon = True
        t.start()

        deadline = time.time() + 10
        while time.time() < deadline:
            stats = self.queue.stats()
            if stats.get("completed", 0) == num_jobs:
                break
            time.sleep(0.1)

        worker.stop()
        t.join(timeout=5)

        # Verify all jobs completed
        stats = self.queue.stats()
        self.assertEqual(stats.get("completed", 0), num_jobs)

        # Check for time overlap: at least two jobs must have overlapping
        # [start_time, end_time] ranges, proving concurrent execution.
        conn = sqlite3.connect(self.tracker_db)
        rows = conn.execute(
            "SELECT job_id, start_time, end_time FROM timing ORDER BY start_time"
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), num_jobs)

        overlap_found = False
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                # Two intervals overlap if one starts before the other ends
                if rows[i][1] < rows[j][2] and rows[j][1] < rows[i][2]:
                    overlap_found = True
                    break
            if overlap_found:
                break

        self.assertTrue(
            overlap_found,
            f"No overlapping execution times found among {len(rows)} jobs — "
            f"jobs may have run sequentially instead of concurrently",
        )


class TestNoDoubleClaims(WorkerConcurrencyTestBase):
    """Verify each job is processed exactly once with concurrent threads."""

    def test_no_duplicate_processing(self):
        num_jobs = 12
        concurrency = 4

        # Set up counter DB
        conn = sqlite3.connect(self.tracker_db)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS counter (job_id TEXT PRIMARY KEY, count INTEGER)"
        )
        conn.commit()
        conn.close()

        for i in range(num_jobs):
            job = Job(
                name=f"counter_{i}",
                function=work_counter_job,
                params={"job_id": f"counter_{i}", "counter_db": self.tracker_db},
            )
            self.queue.submit(job)

        worker = Worker(
            self.db_path,
            polling_interval=0.1,
            concurrency=concurrency,
        )

        def run_worker():
            worker.start()

        t = threading.Thread(target=run_worker)
        t.daemon = True
        t.start()

        deadline = time.time() + 15
        while time.time() < deadline:
            stats = self.queue.stats()
            if stats.get("completed", 0) == num_jobs:
                break
            time.sleep(0.1)

        worker.stop()
        t.join(timeout=5)

        # Verify exactly num_jobs were processed
        conn = sqlite3.connect(self.tracker_db)
        cursor = conn.execute("SELECT COUNT(*) FROM counter")
        processed_count = cursor.fetchone()[0]

        # Verify no job was processed more than once
        cursor = conn.execute("SELECT job_id, count FROM counter WHERE count > 1")
        duplicates = cursor.fetchall()
        conn.close()

        self.assertEqual(processed_count, num_jobs)
        self.assertEqual(
            len(duplicates), 0, f"Jobs processed more than once: {duplicates}"
        )


class TestGracefulShutdown(WorkerConcurrencyTestBase):
    """Verify in-flight jobs complete but no new jobs are claimed after stop."""

    def test_shutdown_completes_inflight_jobs(self):
        num_jobs = 8
        concurrency = 4
        sleep_duration = 0.8

        for i in range(num_jobs):
            job = Job(
                name=f"shutdown_{i}",
                function=timed_job,
                params={
                    "job_id": f"shutdown_{i}",
                    "tracker_db": self.tracker_db,
                    "duration": sleep_duration,
                },
            )
            self.queue.submit(job)

        worker = Worker(
            self.db_path,
            polling_interval=0.1,
            concurrency=concurrency,
        )

        def run_worker():
            worker.start()

        t = threading.Thread(target=run_worker)
        t.daemon = True
        t.start()

        # Wait until some jobs are running
        deadline = time.time() + 10
        while time.time() < deadline:
            running = self.queue.list_jobs(status=JobStatus.RUNNING)
            if len(running) >= 2:
                break
            time.sleep(0.05)

        # Stop the worker — in-flight jobs should finish, no new claims
        worker.stop()
        t.join(timeout=10)

        stats = self.queue.stats()
        completed = stats.get("completed", 0)
        pending = stats.get("pending", 0)

        # At least some jobs should have completed (the in-flight batch)
        self.assertGreater(completed, 0, "No jobs completed before shutdown")

        # Not all jobs should have been processed (we stopped early)
        self.assertGreater(
            pending, 0, "All jobs were processed — shutdown didn't stop new claims"
        )

        # The sum should account for all jobs
        self.assertEqual(completed + pending, num_jobs)


class TestRetryUnderConcurrency(WorkerConcurrencyTestBase):
    """Verify that the fail-requeue-reclaim retry path is race-free."""

    def test_retry_jobs_complete_under_concurrency(self):
        num_jobs = 6
        concurrency = 3

        # Set up state DB for retry tracking
        state_fd, state_db = tempfile.mkstemp(suffix=".db")
        self.addCleanup(
            lambda: os.unlink(state_db) if os.path.exists(state_db) else None
        )
        self.addCleanup(lambda: os.close(state_fd))

        for i in range(num_jobs):
            job = Job(
                name=f"retry_{i}",
                function=retry_job,
                params={
                    "job_id": f"retry_{i}",
                    "fail_times": 1,
                    "state_db": state_db,
                },
                max_attempts=3,
            )
            self.queue.submit(job)

        worker = Worker(
            self.db_path,
            polling_interval=0.1,
            concurrency=concurrency,
        )

        def run_worker():
            worker.start()

        t = threading.Thread(target=run_worker)
        t.daemon = True
        t.start()

        deadline = time.time() + 15
        while time.time() < deadline:
            stats = self.queue.stats()
            if stats.get("completed", 0) == num_jobs:
                break
            time.sleep(0.1)

        worker.stop()
        t.join(timeout=5)

        # All jobs should eventually complete (each fails once, then succeeds)
        for i in range(num_jobs):
            jobs = self.queue.list_jobs()
            for j in jobs:
                if j["name"] == f"retry_{i}":
                    status = self.queue.get_status(j["id"])
                    self.assertEqual(
                        status["status"],
                        JobStatus.COMPLETED.value,
                        f"Job retry_{i} did not complete: {status['status']}",
                    )
                    self.assertEqual(
                        status["attempts"],
                        2,
                        f"Job retry_{i} should have taken 2 attempts",
                    )


class TestInputValidation(WorkerConcurrencyTestBase):
    """Verify that invalid concurrency values are rejected."""

    def test_concurrency_zero_raises(self):
        with self.assertRaises(ValueError):
            Worker(self.db_path, concurrency=0)

    def test_concurrency_negative_raises(self):
        with self.assertRaises(ValueError):
            Worker(self.db_path, concurrency=-1)

    def test_concurrency_one_is_valid(self):
        worker = Worker(self.db_path, concurrency=1)
        self.assertEqual(worker.concurrency, 1)

    def test_concurrency_high_is_valid(self):
        worker = Worker(self.db_path, concurrency=16)
        self.assertEqual(worker.concurrency, 16)
