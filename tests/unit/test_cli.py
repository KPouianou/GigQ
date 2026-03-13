"""
Unit tests for the CLI module in GigQ.
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

from gigq import Job, JobQueue, JobStatus
from gigq.cli import (
    cmd_list,
    cmd_status,
    cmd_submit,
    cmd_cancel,
    cmd_requeue,
    cmd_clear,
    cmd_stats,
)


def example_function(value=1):
    """Example function for testing."""
    return {"result": value * 2}


class TestCLI(unittest.TestCase):
    """Tests for the CLI module."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

        # Add some test jobs
        for i in range(3):
            job = Job(
                name=f"test_job_{i}", function=example_function, params={"value": i}
            )
            self.queue.submit(job)

        # Create a module with a test function for imports
        self.module_content = """
def test_function(value):
    return {"result": value * 2}
"""
        self.module_path = os.path.join(tempfile.gettempdir(), "gigq_test_module.py")
        with open(self.module_path, "w") as f:
            f.write(self.module_content)

        # Add the temp directory to Python path
        if tempfile.gettempdir() not in sys.path:
            sys.path.append(tempfile.gettempdir())

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

        # Clean up the test module
        if os.path.exists(self.module_path):
            os.unlink(self.module_path)

        # Remove the temp directory from Python path
        if tempfile.gettempdir() in sys.path:
            sys.path.remove(tempfile.gettempdir())

    def test_cmd_list(self):
        """Test the list command."""
        # Redirect stdout to capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.status = None
        args.limit = 100

        # Run the list command
        cmd_list(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check that the output contains the job names
        output = captured_output.getvalue()
        for i in range(3):
            self.assertIn(f"test_job_{i}", output)

    def test_cmd_status(self):
        """Test the status command."""
        # Submit a job to get a known job ID
        job = Job(
            name="status_test_job", function=example_function, params={"value": 42}
        )
        job_id = self.queue.submit(job)

        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.job_id = job_id
        args.show_params = True
        args.show_result = False
        args.show_executions = False

        # Run the status command
        cmd_status(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("status_test_job", output)
        self.assertIn("pending", output.lower())
        self.assertIn("Parameters:", output)
        self.assertIn("value: 42", output)

    def test_cmd_status_job_not_found(self):
        """Test the status command with a non-existent job ID."""
        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.job_id = "non-existent-id"
        args.show_params = False
        args.show_result = False
        args.show_executions = False

        # Run the status command - should return exit code 1
        result = cmd_status(args)

        # Check the return value
        self.assertEqual(result, 1)  # Expect return code 1 for not found

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("not found", output)

    def test_cmd_submit(self):
        """Test the submit command."""
        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.function = "gigq_test_module.test_function"
        args.name = "submit_test_job"
        args.param = ["value=84"]
        args.priority = 10
        args.max_attempts = 2
        args.timeout = 120
        args.description = "Test job description"

        # Run the submit command
        cmd_submit(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("Job submitted:", output)

        # Get the job ID from the output
        import re

        match = re.search(r"Job submitted: ([a-z0-9-]+)", output)
        self.assertIsNotNone(match)
        job_id = match.group(1)

        # Verify the job is in the queue with correct properties
        status = self.queue.get_status(job_id)
        self.assertTrue(status["exists"])
        self.assertEqual(status["name"], "submit_test_job")
        self.assertEqual(status["params"]["value"], 84)
        self.assertEqual(status["priority"], 10)
        self.assertEqual(status["max_attempts"], 2)
        self.assertEqual(status["timeout"], 120)
        self.assertEqual(status["description"], "Test job description")

    def test_cmd_cancel(self):
        """Test the cancel command."""
        # Submit a job to cancel
        job = Job(name="cancel_test_job", function=example_function)
        job_id = self.queue.submit(job)

        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.job_id = job_id

        # Run the cancel command
        cmd_cancel(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("cancelled", output)

        # Verify the job is cancelled
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.CANCELLED.value)

    def test_cmd_requeue(self):
        """Test the requeue command."""
        # Submit a job and mark it as failed
        job = Job(name="requeue_test_job", function=example_function)
        job_id = self.queue.submit(job)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE id = ?",
            (JobStatus.FAILED.value, "Test error", job_id),
        )
        conn.commit()
        conn.close()

        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.job_id = job_id

        # Run the requeue command
        cmd_requeue(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("requeued", output)

        # Verify the job is requeued
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 0)

    def test_cmd_clear(self):
        """Test the clear command."""
        # Submit jobs and mark some as completed
        job1 = Job(name="clear_test_job1", function=example_function)
        job2 = Job(name="clear_test_job2", function=example_function)
        job_id1 = self.queue.submit(job1)
        job_id2 = self.queue.submit(job2)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (JobStatus.COMPLETED.value, job_id1),
        )
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (JobStatus.CANCELLED.value, job_id2),
        )
        conn.commit()
        conn.close()

        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path
        args.before = None

        # Run the clear command
        cmd_clear(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Check the output
        output = captured_output.getvalue()
        self.assertIn("Cleared", output)

        # Verify the jobs are cleared
        all_jobs = self.queue.list_jobs()
        self.assertEqual(len(all_jobs), 3)  # Only the 3 original test jobs remain

    def test_cmd_stats(self):
        """Test the stats command."""
        # Submit additional jobs and update their statuses to create variety
        pending_job = Job(name="stats_pending", function=example_function)
        running_job = Job(name="stats_running", function=example_function)
        completed_job = Job(name="stats_completed", function=example_function)
        failed_job = Job(name="stats_failed", function=example_function)

        pending_id = self.queue.submit(pending_job)
        running_id = self.queue.submit(running_job)
        completed_id = self.queue.submit(completed_job)
        failed_id = self.queue.submit(failed_job)

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

        # Redirect stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Create mock args
        args = MagicMock()
        args.db = self.db_path

        # Run the stats command
        cmd_stats(args)

        # Reset stdout
        sys.stdout = sys.__stdout__

        output = captured_output.getvalue()

        # Basic sanity checks: headers and known statuses should be present
        self.assertIn("Status", output)
        self.assertIn("Count", output)
        for status in [s.value for s in JobStatus]:
            self.assertIn(status, output)
        self.assertIn("total", output)


if __name__ == "__main__":
    unittest.main()
