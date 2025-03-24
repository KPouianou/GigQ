"""Base classes for integration tests."""

import unittest
import tempfile
import os
import time
import threading
from gigq import JobQueue, Worker
from gigq.db_utils import close_connections


class IntegrationTestBase(unittest.TestCase):
    """Base class for integration tests with proper setup and teardown."""

    def setUp(self):
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

        # Set up a worker in a separate thread for testing
        self.worker = Worker(self.db_path, polling_interval=0.1)
        self.worker_thread = None
        self.worker_running = False

    def start_worker(self):
        """Start a worker in a background thread."""
        self.worker_running = True

        def worker_thread_func():
            while self.worker_running:
                self.worker.process_one()
                time.sleep(0.1)

        self.worker_thread = threading.Thread(target=worker_thread_func)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def stop_worker(self):
        """Stop the background worker."""
        if self.worker_thread:
            self.worker_running = False
            self.worker_thread.join(timeout=2)

    def tearDown(self):
        """Clean up resources."""
        self.stop_worker()

        # Close connections for the main thread
        self.queue.close()
        close_connections()  # Ensure all thread-local connections are closed

        # Remove database file
        os.close(self.db_fd)
        os.unlink(self.db_path)
