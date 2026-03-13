"""Tests for CLI integration."""

import os
import sys
import re
import tempfile
import unittest
from io import StringIO
from gigq.cli import main


class TestCLIIntegration(unittest.TestCase):
    """Test CLI integration with the job queue."""

    def setUp(self):
        # Create a temporary database file
        _, self.db_path = tempfile.mkstemp()

        # Create a module with a test function
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

        # Save original stdout
        self.original_stdout = sys.stdout

    def tearDown(self):
        # Clean up
        os.unlink(self.db_path)
        if os.path.exists(self.module_path):
            os.unlink(self.module_path)

        # Remove the temp directory from Python path
        if tempfile.gettempdir() in sys.path:
            sys.path.remove(tempfile.gettempdir())

        # Restore stdout
        sys.stdout = self.original_stdout

    def test_cli_submit_and_process(self):
        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Use CLI to submit a job
        sys.argv = [
            "gigq",
            "--db",
            self.db_path,
            "submit",
            "gigq_test_module.test_function",
            "--name",
            "cli_test_job",
            "--param",
            "value=42",
        ]
        main()

        # Get the job ID from the output
        output = captured_output.getvalue()
        match = re.search(r"Job submitted: ([a-f0-9-]+)", output)
        self.assertIsNotNone(match)
        job_id = match.group(1)

        # Reset stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Use CLI to start a worker for one job
        sys.argv = ["gigq", "--db", self.db_path, "worker", "--once"]
        main()

        # Reset stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        # Use CLI to check job status
        sys.argv = ["gigq", "--db", self.db_path, "status", job_id, "--show-result"]
        main()

        # Check the output contains the result
        output = captured_output.getvalue()
        self.assertIn("completed", output.lower())
        self.assertIn("result: 84", output)  # 42 * 2

    def test_cli_stats(self):
        """End-to-end test for the stats command."""
        # First, submit a job so the database is not empty
        captured_output = StringIO()
        sys.stdout = captured_output

        sys.argv = [
            "gigq",
            "--db",
            self.db_path,
            "submit",
            "gigq_test_module.test_function",
            "--name",
            "stats_test_job",
            "--param",
            "value=5",
        ]
        main()

        # Now call the stats command
        captured_output = StringIO()
        sys.stdout = captured_output

        sys.argv = ["gigq", "--db", self.db_path, "stats"]
        main()

        # Restore stdout
        sys.stdout = self.original_stdout

        output = captured_output.getvalue()
        # We don't assert exact numbers, just that the table structure and key labels exist
        self.assertIn("Status", output)
        self.assertIn("Count", output)
        self.assertIn("pending", output)
        self.assertIn("total", output)
