"""
Database utilities for GigQ.

This module provides thread-local SQLite connection management.
"""

import sqlite3
import threading
from typing import Optional

# Thread-local storage for SQLite connections
_thread_local = threading.local()


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    Get a SQLite connection for the current thread.

    If a connection already exists for this thread, it will be reused.
    Otherwise, a new connection will be created.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A SQLite connection with row_factory set to sqlite3.Row.
    """
    # Initialize a connections dict for this thread if it doesn't exist
    if not hasattr(_thread_local, "connections"):
        _thread_local.connections = {}

    # Get or create a connection for this database
    if db_path not in _thread_local.connections:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        _thread_local.connections[db_path] = conn

    return _thread_local.connections[db_path]


def close_connections() -> None:
    """
    Close all SQLite connections for the current thread.

    This should be called when a thread is finishing its work
    to clean up resources.
    """
    if hasattr(_thread_local, "connections"):
        for conn in _thread_local.connections.values():
            conn.close()
        _thread_local.connections.clear()


def close_connection(db_path: str) -> None:
    """
    Close the SQLite connection for the specified database path.

    Args:
        db_path: Path to the SQLite database file.
    """
    if hasattr(_thread_local, "connections") and db_path in _thread_local.connections:
        _thread_local.connections[db_path].close()
        del _thread_local.connections[db_path]
