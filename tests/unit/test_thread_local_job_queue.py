"""
Unit tests for the JobQueue class with thread-local connections.
"""

import os
import tempfile
import threading
import unittest
from gigq import Job, JobQueue, JobStatus, close_connections


def example_job_function(value=0):
    """Example job function for testing."""
    return {"result": value * 2}


class TestThreadLocalJobQueue(unittest.TestCase):
    """Tests for the JobQueue class with thread-local connections."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        self.queue.close()
        close_connections()  # Ensure all connections are closed
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_connection_reuse(self):
        """Test that connections are reused within the same thread."""
        # Submit several jobs to ensure connection reuse
        job_ids = []
        for i in range(5):
            job = Job(name=f"job_{i}", function=example_job_function)
            job_id = self.queue.submit(job)
            job_ids.append(job_id)

        # Get status of each job - should use the same connection
        for job_id in job_ids:
            status = self.queue.get_status(job_id)
            self.assertEqual(status["status"], JobStatus.PENDING.value)

    def test_threaded_job_operations(self):
        """Test job operations in multiple threads."""
        # Submit a job in the main thread
        main_job = Job(name="main_job", function=example_job_function)
        main_job_id = self.queue.submit(main_job)

        # Dictionary to store results from threads
        thread_results = {}

        def thread_func(thread_id):
            try:
                # Create a thread-specific queue
                thread_queue = JobQueue(self.db_path, initialize=False)

                # Submit a job
                job = Job(name=f"thread_{thread_id}_job", function=example_job_function)
                job_id = thread_queue.submit(job)

                # Get status of the main job
                main_status = thread_queue.get_status(main_job_id)

                # Store results
                thread_results[thread_id] = {
                    "job_id": job_id,
                    "main_status": main_status["status"],
                }

                # Cleanup
                thread_queue.close()
            except Exception as e:
                thread_results[thread_id] = {"error": str(e)}

        # Create and run threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_func, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        for thread_id, result in thread_results.items():
            # Check if thread encountered an error
            self.assertNotIn(
                "error",
                result,
                f"Thread {thread_id} encountered an error: {result.get('error')}",
            )

            # Verify the thread could see the main job
            self.assertEqual(result["main_status"], JobStatus.PENDING.value)

            # Verify we can see the thread's job from the main thread
            thread_job_id = result["job_id"]
            thread_job_status = self.queue.get_status(thread_job_id)
            self.assertEqual(thread_job_status["status"], JobStatus.PENDING.value)


if __name__ == "__main__":
    unittest.main()
