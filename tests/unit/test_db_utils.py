"""
Unit tests for the db_utils module in GigQ.
"""

import os
import tempfile
import threading
import unittest
import sqlite3
from gigq.db_utils import get_connection, close_connection, close_connections


class TestDBUtils(unittest.TestCase):
    """Tests for the db_utils module."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        """Clean up the temporary database."""
        # Close any open connections
        close_connections()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_get_connection(self):
        """Test getting a connection from thread-local storage."""
        # Get a connection
        conn = get_connection(self.db_path)

        # Check that it's a valid SQLite connection
        self.assertIsInstance(conn, sqlite3.Connection)

        # Check that row_factory is set correctly
        self.assertEqual(conn.row_factory, sqlite3.Row)

        # Get another connection (should be the same one)
        conn2 = get_connection(self.db_path)

        # Check that both connections are the same object
        self.assertIs(conn, conn2)

        # Close the connection
        close_connection(self.db_path)

    def test_multiple_databases(self):
        """Test that connections to different databases are managed separately."""
        # Create a second database
        fd2, db_path2 = tempfile.mkstemp()
        self.addCleanup(lambda: os.unlink(db_path2))
        self.addCleanup(lambda: os.close(fd2))

        # Get connections to both databases
        conn1 = get_connection(self.db_path)
        conn2 = get_connection(db_path2)

        # Should be different connections
        self.assertIsNot(conn1, conn2)

        # But getting the same database again should return the same connection
        conn1b = get_connection(self.db_path)
        self.assertIs(conn1, conn1b)

        # Close all connections
        close_connections()

    def test_thread_isolation(self):
        """Test that each thread gets its own connection."""
        # Connection in main thread
        main_conn = get_connection(self.db_path)

        # Dictionary to store connections from threads
        thread_connections = {}

        def thread_func():
            # Get connection in the thread
            thread_conn = get_connection(self.db_path)
            thread_id = threading.get_ident()
            thread_connections[thread_id] = thread_conn

            # Create a test table
            thread_conn.execute(
                f"CREATE TABLE IF NOT EXISTS thread_{thread_id} (id INTEGER)"
            )
            thread_conn.commit()

            # Close connection when done
            close_connection(self.db_path)

        # Create and run threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_func)
            threads.append(thread)
            thread.start()

        # Wait for threads to complete
        for thread in threads:
            thread.join()

        # Each thread should have its own connection
        # Different from the main thread's connection
        for thread_id, conn in thread_connections.items():
            self.assertIsNot(conn, main_conn)

        # And each thread's connection should be different
        connections = list(thread_connections.values())
        for i in range(len(connections)):
            for j in range(i + 1, len(connections)):
                self.assertIsNot(connections[i], connections[j])

        # Close main connection
        close_connection(self.db_path)
