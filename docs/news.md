# News and Release Notes

This page provides news, announcements, and detailed release notes for GigQ.

## GigQ 0.2.0 (March 24, 2025)

We're excited to announce the release of GigQ 0.2.0, which introduces thread-local SQLite connection management for improved performance.

### Performance Improvements

GigQ now uses thread-local storage to efficiently reuse SQLite connections within each thread. This approach:

- Reduces the overhead of repeatedly creating and closing connections
- Respects SQLite's threading model where connections can only be used in their creating thread
- Provides an estimated 5-15% performance improvement for applications with many database operations
- Reduces resource usage by minimizing the number of active connections

### New Features

#### Thread-Local Connection Management

- New `db_utils` module for database connection handling
- Thread-local storage for connection caching
- Each thread maintains its own set of connections

#### Connection Cleanup API

- New `close_connections()` function to clean up thread resources
- `JobQueue.close()` and `Worker.close()` methods to close specific connections

### API Changes

While the core API remains backward compatible, we've added a few new methods to help manage connections:

```python
# Close a specific JobQueue connection
queue = JobQueue("jobs.db")
# ... use queue ...
queue.close()

# Close a specific Worker connection
worker = Worker("jobs.db")
# ... use worker ...
worker.close()

# Close all connections in the current thread
from gigq import close_connections
close_connections()
```

### Upgrading from 0.1.x

This release is backward compatible with previous versions. To upgrade:

```bash
pip install --upgrade gigq
```

If you have long-running threads or processes that use GigQ, consider adding the new connection cleanup calls to properly manage resources:

```python
# At the end of your process or thread
from gigq import close_connections
close_connections()
```

## GigQ 0.1.1 (March 22, 2025)

This is a minor release with bug fixes and improved test coverage.

### Improvements

- Fixed project shields in README
- Implemented comprehensive test coverage

## GigQ 0.1.0 (March 15, 2025)

Initial release of GigQ.

### Features

- Core job queue functionality with SQLite backend
- Job definition with parameters, priorities, and dependencies
- Worker implementation for job processing
- Workflow support for dependent jobs
- Command-line interface for job and worker management
- Automatic retry and timeout handling
- GitHub Archive processing example
