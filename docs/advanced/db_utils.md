# Database Utilities

This page documents the database utilities in GigQ, focusing on the thread-local connection management system that optimizes SQLite database access.

## Overview

GigQ uses SQLite as its backend storage. To improve performance while respecting SQLite's threading model, GigQ 0.2.0 introduces a thread-local connection management system that:

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

# Initialize thread's connection dictionary if needed
if not hasattr(_thread_local, 'connections'):
    _thread_local.connections = {}

# Get or create connection for this database
if db_path not in _thread_local.connections:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    _thread_local.connections[db_path] = conn
```

This ensures that:

1. Each thread only sees its own connections
2. Connections are automatically cleaned up when threads terminate
3. No complex synchronization is needed between threads

## Multi-Threaded Worker Example

Here's a complete example of running multiple worker threads with proper connection management:

```python
import threading
import signal
import time
from gigq import Worker, JobQueue, close_connections

def worker_thread(db_path, worker_id, stop_event):
    """Worker function to run in a separate thread."""
    worker = Worker(db_path, worker_id=worker_id, polling_interval=1)
    queue = JobQueue(db_path, initialize=False)

    print(f"Worker {worker_id} started")

    try:
        # Process jobs until stop_event is set
        while not stop_event.is_set():
            processed = worker.process_one()
            if not processed:
                # No job available, sleep briefly
                time.sleep(1)

            # Periodically check for jobs that might be stuck
            if worker_id == "worker-1" and random.random() < 0.05:  # 5% chance
                timed_out = worker._check_for_timeouts()
                if timed_out:
                    print(f"Worker {worker_id} detected {timed_out} timed out jobs")

    except Exception as e:
        print(f"Worker {worker_id} error: {str(e)}")
    finally:
        # Always clean up connections
        worker.close()
        queue.close()
        close_connections()
        print(f"Worker {worker_id} stopped")

def run_worker_pool(db_path, num_workers=4):
    """Run a pool of worker threads with proper shutdown handling."""
    stop_event = threading.Event()
    threads = []

    # Start worker threads
    for i in range(num_workers):
        worker_id = f"worker-{i+1}"
        thread = threading.Thread(
            target=worker_thread,
            args=(db_path, worker_id, stop_event)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)

    print(f"Started {num_workers} worker threads")

    # Set up signal handling for graceful shutdown
    def handle_signal(sig, frame):
        print(f"Received signal {sig}, shutting down workers...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        # Keep the main thread alive until interrupted
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        # Wait for all threads to complete
        print("Waiting for worker threads to stop...")
        for thread in threads:
            thread.join(timeout=5)
        print("All worker threads stopped")

        # Clean up main thread connections
        close_connections()

# Usage:
# run_worker_pool("jobs.db", num_workers=4)
```

## Best Practices

1. **Call close_connections() when done**: Especially in long-running processes or custom threads.
2. **Use JobQueue.close()**: This is a convenience method that closes the queue's specific connection.
3. **One connection per thread**: For best performance, maintain one JobQueue instance per thread.
4. **Monitor resource usage**: Even with thread-local connections, long-running processes should monitor SQLite resource usage.
5. **Use try/finally blocks**: Always clean up connections even when exceptions occur.
6. **Consider process isolation**: For extreme scalability, run workers in separate processes rather than threads.

## Thread Safety Considerations

GigQ's thread-local connection approach ensures:

- Connections are only used in the thread that created them (respecting SQLite's constraints)
- No connection sharing between threads, eliminating the need for complex synchronization
- Each thread properly manages its own resources

This approach strikes a balance between performance and thread safety while keeping the implementation simple and robust.

## Common Patterns

### Web Server Pattern

For web applications that submit jobs:

```python
from flask import Flask, g
from gigq import JobQueue, close_connections

app = Flask(__name__)

def get_queue():
    """Get or create a thread-local queue."""
    if not hasattr(g, 'job_queue'):
        g.job_queue = JobQueue("jobs.db")
    return g.job_queue

@app.teardown_appcontext
def close_queue(e=None):
    """Close the queue when the request ends."""
    queue = g.pop('job_queue', None)
    if queue is not None:
        queue.close()
    close_connections()

@app.route('/submit')
def submit_job():
    queue = get_queue()
    # Submit job...
    return "Job submitted"
```

### Scheduled Task Pattern

For periodic tasks that use GigQ:

```python
import schedule
import time
from gigq import JobQueue, close_connections

def daily_task():
    queue = JobQueue("jobs.db")
    try:
        # Submit daily jobs...
        print("Daily task complete")
    finally:
        queue.close()
        close_connections()

# Schedule the task
schedule.every().day.at("01:00").do(daily_task)

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

## SQLite Connection Optimization

In addition to connection reuse, GigQ configures SQLite for optimal performance:

1. **Timeout Configuration**: Connections are configured with a 30-second timeout to avoid indefinite blocking
2. **Row Factory**: Connections use `sqlite3.Row` as the row factory for convenient dictionary-like access
3. **Future Improvements**: Future versions may include additional optimizations like WAL mode or custom pragmas

## Troubleshooting

### Common Issues

1. **Database is locked**: This usually means too many concurrent operations are attempting to modify the database.

   - **Solution**: Reduce the number of concurrent workers or increase the connection timeout.

2. **Too many open files**: Operating systems limit the number of open file handles.

   - **Solution**: Ensure you're properly calling `close_connections()` in long-running applications.

3. **Memory leaks**: If connections aren't properly closed in long-running applications.
   - **Solution**: Use `try/finally` blocks to ensure proper cleanup.

## Next Steps

Now that you understand GigQ's database utilities, you might want to explore:

- [Performance Optimization](performance.md) - Additional performance tips
- [Concurrency](concurrency.md) - More about GigQ's concurrency model
- [SQLite Schema](sqlite-schema.md) - Details about the database schema
