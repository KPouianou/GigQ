# Database Utilities

This page documents the database utilities in GigQ, focusing on the thread-local connection management system that optimizes SQLite database access.

## Overview

GigQ uses SQLite as its backend storage. To improve performance while respecting SQLite's threading model, GigQ implements a thread-local connection management system that:

1. Creates a separate connection for each thread
2. Reuses connections within each thread
3. Properly closes connections when threads are done

## Thread-Local Connection Management

SQLite connections have an important limitation: they can only be used in the thread where they were created. GigQ respects this constraint while optimizing performance by using thread-local storage to cache connections.

### Key Functions

These functions are provided by the `db_utils` module but are also accessible through the main GigQ package.

#### get_connection(db_path)

Gets a connection for the current thread, reusing an existing connection if available:

```python
from gigq.db_utils import get_connection

# Get a connection (will be reused in this thread)
conn = get_connection("jobs.db")
```

#### close_connection(db_path)

Closes a specific connection for the current thread:

```python
from gigq.db_utils import close_connection

# Close the connection to a specific database
close_connection("jobs.db")
```

#### close_connections()

Closes all connections for the current thread:

```python
from gigq import close_connections

# Close all connections for this thread
close_connections()
```

## When to Call close_connections()

You should call `close_connections()` in these scenarios:

1. **At the end of thread execution**: If you're creating your own threads that use GigQ.
2. **When shutting down your application**: To ensure clean resource release.
3. **After processing a batch of jobs**: If you're running in a long-lived process and want to free resources.

Example usage in a thread:

```python
import threading
from gigq import JobQueue, close_connections

def worker_thread():
    queue = JobQueue("jobs.db")

    # Process jobs...

    # Clean up before thread exits
    queue.close()  # This closes the specific connection used by the queue
    close_connections()  # This ensures all thread-local connections are closed

thread = threading.Thread(target=worker_thread)
thread.start()
thread.join()
```

## Performance Implications

The thread-local connection approach offers these performance benefits:

- **Reduced Connection Overhead**: Opening SQLite connections has overhead; reusing them improves performance.
- **Typical Improvement**: 5-15% overall performance improvement for applications with many database operations.
- **Resource Efficiency**: Fewer file handles used, which can prevent hitting system limits in high-load scenarios.

## Implementation Details

Under the hood, GigQ uses Python's `threading.local()` to create thread-specific storage that isolates connections between threads:

```python
# Thread-local storage
_thread_local = threading.local()

# Each thread gets its own dictionary of connections
if not hasattr(_thread_local, 'connections'):
    _thread_local.connections = {}
```

This ensures that:

1. Each thread only sees its own connections
2. Connections are automatically cleaned up when threads terminate
3. No complex synchronization is needed between threads

## Best Practices

1. **Call close_connections() when done**: Especially in long-running processes or custom threads.
2. **Use JobQueue.close()**: This is a convenience method that closes the queue's specific connection.
3. **One connection per thread**: For best performance, maintain one JobQueue instance per thread.
4. **Monitor resource usage**: Even with thread-local connections, long-running processes should monitor SQLite resource usage.

## Thread Safety Considerations

GigQ's thread-local connection approach ensures:

- Connections are only used in the thread that created them (respecting SQLite's constraints)
- No connection sharing between threads, eliminating the need for complex synchronization
- Each thread properly manages its own resources

This approach strikes a balance between performance and thread safety while keeping the implementation simple and robust.

## Next Steps

Now that you understand GigQ's database utilities, you might want to explore:

- [Performance Optimization](performance.md) - Additional performance tips
- [Concurrency](concurrency.md) - More about GigQ's concurrency model
- [SQLite Schema](sqlite-schema.md) - Details about the database schema
