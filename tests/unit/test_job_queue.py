"""
Unit tests for the JobQueue class in GigQ.
"""

import os
import sqlite3
import tempfile
import unittest
import json
from gigq import Job, JobQueue, JobStatus


def example_job_function(value=0):
    """Example job function for testing."""
    return {"result": value * 2}


def failing_job_function():
    """Example job function that fails."""
    raise ValueError("This job is designed to fail")


class TestJobQueue(unittest.TestCase):
    """Tests for the JobQueue class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_submit_job(self):
        """Test that a job can be submitted to the queue."""
        job = Job(name="test_job", function=example_job_function, params={"value": 42})

        job_id = self.queue.submit(job)
        self.assertEqual(job_id, job.id)

        # Check that the job was stored correctly
        status = self.queue.get_status(job_id)
        self.assertTrue(status["exists"])
        self.assertEqual(status["name"], "test_job")
        self.assertEqual(status["status"], JobStatus.PENDING.value)

    def test_cancel_job(self):
        """Test that a pending job can be cancelled."""
        job = Job(name="test_job", function=example_job_function)

        job_id = self.queue.submit(job)
        self.assertTrue(self.queue.cancel(job_id))

        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.CANCELLED.value)

    def test_cannot_cancel_non_pending_job(self):
        """Test that only pending jobs can be cancelled."""
        # Create a job
        job = Job(name="test_job", function=example_job_function)
        job_id = self.queue.submit(job)

        # Mark it as running
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?", (JobStatus.RUNNING.value, job_id)
        )
        conn.commit()
        conn.close()

        # Try to cancel
        self.assertFalse(self.queue.cancel(job_id))

        # Check it's still running
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.RUNNING.value)

    def test_list_jobs(self):
        """Test that jobs can be listed from the queue."""
        # Submit some jobs
        jobs = []
        for i in range(5):
            job = Job(
                name=f"test_job_{i}", function=example_job_function, params={"value": i}
            )
            job_id = self.queue.submit(job)
            jobs.append(job_id)

        # List all jobs
        job_list = self.queue.list_jobs()
        self.assertEqual(len(job_list), 5)

        # Cancel one job
        self.queue.cancel(jobs[0])

        # List only pending jobs
        pending_jobs = self.queue.list_jobs(status=JobStatus.PENDING)
        self.assertEqual(len(pending_jobs), 4)

        # List only cancelled jobs
        cancelled_jobs = self.queue.list_jobs(status=JobStatus.CANCELLED)
        self.assertEqual(len(cancelled_jobs), 1)

    def test_requeue_job(self):
        """Test that a failed job can be requeued."""
        job = Job(name="failing_job", function=failing_job_function, max_attempts=1)

        job_id = self.queue.submit(job)

        # Mark job as failed
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE id = ?",
            (JobStatus.FAILED.value, "Test error", job_id),
        )
        conn.commit()
        conn.close()

        # Verify job is failed
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.FAILED.value)

        # Requeue the job
        self.assertTrue(self.queue.requeue_job(job_id))

        # Verify job is pending again
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 0)  # Attempts should be reset

    def test_clear_completed_jobs(self):
        """Test clearing completed jobs from the queue."""
        # Create and submit jobs
        for i in range(5):
            job = Job(name=f"job_{i}", function=example_job_function)
            self.queue.submit(job)

        # Mark some as completed and some as cancelled
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ? WHERE name IN (?, ?)",
            (JobStatus.COMPLETED.value, "job_0", "job_1"),
        )
        conn.execute(
            "UPDATE jobs SET status = ? WHERE name IN (?)",
            (JobStatus.CANCELLED.value, "job_2"),
        )
        conn.commit()
        conn.close()

        # Clear completed jobs
        count = self.queue.clear_completed()
        self.assertEqual(count, 3)  # 2 completed + 1 cancelled

        # Check remaining jobs
        jobs = self.queue.list_jobs()
        self.assertEqual(len(jobs), 2)  # 2 jobs should remain

    def test_stats_returns_counts_by_status(self):
        """Test that stats() returns correct counts by status and total."""
        # Submit jobs with default pending status
        pending_jobs = []
        for i in range(3):
            job = Job(
                name=f"pending_job_{i}",
                function=example_job_function,
            )
            job_id = self.queue.submit(job)
            pending_jobs.append(job_id)

        # Submit additional jobs that we'll mark as running, completed, and failed
        running_job = Job(name="running_job", function=example_job_function)
        completed_job = Job(name="completed_job", function=example_job_function)
        failed_job = Job(name="failed_job", function=failing_job_function)

        running_id = self.queue.submit(running_job)
        completed_id = self.queue.submit(completed_job)
        failed_id = self.queue.submit(failed_job)

        # Update statuses directly in the database
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (JobStatus.RUNNING.value, running_id),
        )
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (JobStatus.COMPLETED.value, completed_id),
        )
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (JobStatus.FAILED.value, failed_id),
        )
        conn.commit()
        conn.close()

        stats = self.queue.stats()

        self.assertEqual(stats["pending"], 3)
        self.assertEqual(stats["running"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["cancelled"], 0)
        self.assertEqual(stats["timeout"], 0)
        self.assertEqual(
            stats["total"], 3 + 1 + 1 + 1
        )  # Sum of all individual statuses

    def test_get_result_returns_none_for_pending_job(self):
        """get_result should return None when the job is not completed."""
        job = Job(
            name="pending_result_job",
            function=example_job_function,
            params={"value": 10},
        )
        job_id = self.queue.submit(job)

        result = self.queue.get_result(job_id)
        self.assertIsNone(result)

    def test_get_result_returns_deserialized_result_for_completed_job(self):
        """get_result should return the deserialized result for a completed job."""
        job = Job(
            name="completed_result_job",
            function=example_job_function,
            params={"value": 7},
        )
        job_id = self.queue.submit(job)

        # Mark job as completed and store a JSON result directly
        conn = sqlite3.connect(self.db_path)
        stored_result = {"answer": 42}
        conn.execute(
            "UPDATE jobs SET status = ?, result = ? WHERE id = ?",
            (JobStatus.COMPLETED.value, json.dumps(stored_result), job_id),
        )
        conn.commit()
        conn.close()

        result = self.queue.get_result(job_id)
        self.assertEqual(result, stored_result)

    def test_get_result_raises_for_missing_job(self):
        """get_result should raise KeyError for a non-existent job ID."""
        with self.assertRaises(KeyError):
            self.queue.get_result("non-existent-id")


if __name__ == "__main__":
    unittest.main()
