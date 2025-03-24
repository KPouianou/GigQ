# Performance Optimization

This page provides guidance on optimizing GigQ's performance for various workloads and scenarios.

## Understanding GigQ's Performance Characteristics

GigQ is designed to be lightweight while providing reliable job processing. Its performance is influenced by several factors:

1. **SQLite Database Performance**: GigQ uses SQLite as its backend, which has specific performance characteristics
2. **Worker Configuration**: How workers are configured affects throughput and resource usage
3. **Job Characteristics**: The nature of the jobs being processed impacts overall system performance
4. **System Resources**: Available CPU, memory, and disk I/O affect how many jobs can be processed concurrently

## SQLite Database Optimization

### Database Location

The location of your SQLite database file significantly impacts performance:

| Location                     | Performance  | Reliability           | Use Case                            |
| ---------------------------- | ------------ | --------------------- | ----------------------------------- |
| Local SSD                    | Excellent    | Excellent             | Production                          |
| Local HDD                    | Good         | Good                  | Development                         |
| Network File System (NFS)    | Poor to Fair | Fair                  | Distributed setups (use cautiously) |
| Memory (`:memory:` or tmpfs) | Excellent    | Poor (no persistence) | Ephemeral workloads                 |

For best performance, keep your database file on local SSD storage.

### Connection Pooling

GigQ uses thread-local storage to efficiently reuse SQLite connections within each thread. This approach respects SQLite's threading model (where connections can only be used in the thread that created them) while improving performance.

```python
import sqlite3
import threading

# Thread-local storage for connections
_thread_local = threading.local()

def get_connection(db_path):
    """Get a connection from thread-local storage or create a new one."""
    # Initialize connections dict for this thread if needed
    if not hasattr(_thread_local, 'connections'):
        _thread_local.connections = {}

    # Get or create connection for this database
    if db_path not in _thread_local.connections:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        _thread_local.connections[db_path] = conn

    return _thread_local.connections[db_path]

def close_connection(db_path):
    """Close the connection for the specified database."""
    if hasattr(_thread_local, 'connections') and db_path in _thread_local.connections:
        _thread_local.connections[db_path].close()
        del _thread_local.connections[db_path]

def close_connections():
    """Close all connections for this thread."""
    if hasattr(_thread_local, 'connections'):
        for conn in _thread_local.connections.values():
            conn.close()
        _thread_local.connections.clear()
```

This approach provides several benefits:

1. **Performance**: Eliminates the overhead of repeatedly opening and closing connections
2. **Thread safety**: Each thread only accesses its own connections
3. **Resource efficiency**: Reduces the number of file handles used
4. **Simplicity**: No complex connection pool management required

Remember to close connections when threads are done with them:

```python
# At the end of your application or thread
from gigq import close_connections
close_connections()
```

### Index Optimization

GigQ creates basic indexes, but you might benefit from additional indexes based on your query patterns:

```python
# Add custom indexes for your specific workload
conn = sqlite3.connect("jobs.db")
conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_name ON jobs (name)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority_status ON jobs (priority, status)")
conn.commit()
conn.close()
```

### Database Maintenance

Regular maintenance helps maintain performance:

```python
def optimize_database(db_path):
    """Perform database maintenance to optimize performance."""
    conn = sqlite3.connect(db_path)

    # Analyze to update statistics
    conn.execute("ANALYZE")

    # Vacuum to reclaim space and defragment
    conn.execute("VACUUM")

    # Reindex to optimize indexes
    conn.execute("REINDEX")

    conn.close()
```

Run this periodically, especially after clearing many jobs.

## Worker Configuration

### Polling Interval

The worker polling interval affects both responsiveness and database load:

```python
# More responsive but higher database load
worker_responsive = Worker("jobs.db", polling_interval=1)

# Less responsive but lower database load
worker_efficient = Worker("jobs.db", polling_interval=10)
```

Finding the right balance depends on your workload:

- For latency-sensitive jobs, use shorter intervals (1-2 seconds)
- For background processing, use longer intervals (5-30 seconds)

### Number of Workers

The optimal number of workers depends on:

1. **CPU Cores**: For CPU-bound jobs, start with one worker per core
2. **I/O Operations**: For I/O-bound jobs, you can use more workers than cores
3. **SQLite Limitations**: Too many concurrent workers can cause lock contention

A simple formula to start with:

```python
def calculate_workers(job_type="mixed"):
    import os
    cores = os.cpu_count() or 4

    if job_type == "cpu_bound":
        return cores
    elif job_type == "io_bound":
        return cores * 2
    else:  # mixed
        return cores + 2
```

### Specialized Workers

Create specialized workers for different job types:

```python
class HighPriorityWorker(Worker):
    """Worker that only processes high-priority jobs."""

    def _claim_job(self):
        conn = self._get_connection()
        try:
            conn.execute("BEGIN EXCLUSIVE TRANSACTION")

            cursor = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ? AND priority >= 50
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,)
            )

            # Rest of method implementation...
```

### Worker Process Management

For long-running workers, consider using a process manager:

```python
# Example with multiprocessing
from multiprocessing import Process
import os

def start_workers(db_path, count=4):
    """Start multiple worker processes."""
    processes = []

    for i in range(count):
        worker_id = f"worker-{i+1}"
        p = Process(target=run_worker, args=(db_path, worker_id))
        p.daemon = True
        p.start()
        processes.append(p)

    return processes

def run_worker(db_path, worker_id):
    """Run a worker in a separate process."""
    worker = Worker(db_path, worker_id=worker_id)
    worker.start()

# Usage
procs = start_workers("jobs.db", count=4)

# To stop workers
for p in procs:
    p.terminate()
```

## Job Optimization

### Job Batching

Batching small jobs into larger ones reduces overhead:

```python
# Instead of submitting many small jobs
for item in items:
    job = Job(name=f"process_{item}", function=process_item, params={"item": item})
    queue.submit(job)

# Batch them into a single job
def process_batch(items):
    results = []
    for item in items:
        results.append(process_item(item))
    return results

batch_job = Job(name="process_batch", function=process_batch, params={"items": items})
queue.submit(batch_job)
```

### Job Prioritization

Use priorities to ensure important jobs run first:

```python
# Critical job - will execute first
critical_job = Job(
    name="critical_task",
    function=critical_function,
    priority=100
)

# Standard job - will execute after critical jobs
standard_job = Job(
    name="standard_task",
    function=standard_function,
    priority=0
)

# Background job - will execute when no other jobs are available
background_job = Job(
    name="background_task",
    function=background_function,
    priority=-100
)
```

### Appropriate Timeouts

Set job timeouts based on expected execution time:

```python
# Quick job with short timeout
quick_job = Job(
    name="quick_task",
    function=quick_function,
    timeout=30  # 30 seconds
)

# Long-running job with longer timeout
long_job = Job(
    name="long_task",
    function=long_function,
    timeout=3600  # 1 hour
)
```

Appropriate timeouts prevent jobs from getting stuck and blocking workers.

### Efficient Job Functions

Optimize your job functions for performance:

```python
# Less efficient version
def process_data_inefficient(file_path):
    # Read the entire file into memory
    with open(file_path, 'r') as f:
        data = f.read()

    # Process line by line
    lines = data.split('\n')
    results = []
    for line in lines:
        results.append(process_line(line))

    return results

# More efficient version
def process_data_efficient(file_path):
    results = []
    # Process the file in chunks
    with open(file_path, 'r') as f:
        for line in f:
            results.append(process_line(line.strip()))

    return results
```

## Database Cleanup

Regular database cleanup prevents performance degradation over time:

```python
# Automated cleanup job
def cleanup_job(db_path, days_to_keep=7):
    queue = JobQueue(db_path)

    # Calculate cutoff date
    import datetime
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days_to_keep)).isoformat()

    # Clear completed and cancelled jobs before cutoff
    cleared = queue.clear_completed(before_timestamp=cutoff)

    # Optimize the database
    optimize_database(db_path)

    return {"cleared": cleared}

# Schedule this to run periodically
cleanup_job_obj = Job(
    name="database_cleanup",
    function=cleanup_job,
    params={"db_path": "jobs.db", "days_to_keep": 7},
    description="Weekly database cleanup"
)
```

## Memory Usage Optimization

### Memory-Efficient Job Processing

For memory-intensive jobs, consider streaming approaches:

```python
# Memory-intensive approach
def analyze_large_file_memory_intensive(file_path):
    import pandas as pd

    # Load entire dataset into memory
    df = pd.read_csv(file_path)
    result = df.groupby('category').sum()
    return result.to_dict()

# Memory-efficient approach
def analyze_large_file_memory_efficient(file_path):
    import csv
    from collections import defaultdict

    # Process the file in chunks
    results = defaultdict(int)
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row['category']
            value = float(row['value'])
            results[category] += value

    return dict(results)
```

### Limiting Job Result Size

Large job results can consume significant memory:

```python
# Instead of returning large datasets
def job_with_large_result():
    # Process data...
    return large_dataset  # Could be megabytes of data

# Save results to a file and return the file path
def job_with_efficient_result():
    # Process data...
    result_path = f"results/job_{uuid.uuid4()}.json"
    os.makedirs(os.path.dirname(result_path), exist_ok=True)

    with open(result_path, 'w') as f:
        json.dump(large_dataset, f)

    return {"result_file": result_path}
```

## Benchmarking and Monitoring

### Job Performance Metrics

Track job performance to identify bottlenecks:

```python
def job_with_metrics(params):
    import time

    # Measure execution time
    start_time = time.time()

    # Process step 1
    step1_start = time.time()
    step1_result = process_step1(params)
    step1_time = time.time() - step1_start

    # Process step 2
    step2_start = time.time()
    step2_result = process_step2(step1_result)
    step2_time = time.time() - step2_start

    # Process step 3
    step3_start = time.time()
    final_result = process_step3(step2_result)
    step3_time = time.time() - step3_start

    total_time = time.time() - start_time

    # Add metrics to the result
    metrics = {
        "execution_time": total_time,
        "steps": {
            "step1": step1_time,
            "step2": step2_time,
            "step3": step3_time
        }
    }

    return {
        "result": final_result,
        "metrics": metrics
    }
```

### Queue Monitoring

Monitor queue health to detect performance issues:

```python
def monitor_queue_performance(db_path):
    """Monitor queue performance metrics."""
    import time

    queue = JobQueue(db_path)

    # Get initial counts
    pending_count_start = len(queue.list_jobs(status="pending"))

    # Submit a benchmark job
    benchmark_job = Job(
        name="benchmark",
        function=lambda: time.sleep(0.1),
        params={}
    )

    # Measure submission time
    submit_start = time.time()
    job_id = queue.submit(benchmark_job)
    submit_time = time.time() - submit_start

    # Measure queue processing time
    worker = Worker(db_path)
    process_start = time.time()
    worker.process_one()
    process_time = time.time() - process_start

    # Get status check time
    status_start = time.time()
    queue.get_status(job_id)
    status_time = time.time() - status_start

    # Get final counts
    pending_count_end = len(queue.list_jobs(status="pending"))

    return {
        "submit_time": submit_time,
        "process_time": process_time,
        "status_time": status_time,
        "pending_delta": pending_count_end - pending_count_start
    }
```

## Production Deployment Tips

### Database Journaling Mode

Adjust SQLite journaling mode for better performance:

```python
def optimize_sqlite_settings(db_path):
    """Configure SQLite for better performance."""
    conn = sqlite3.connect(db_path)

    # Use WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode = WAL")

    # Set cache size (adjust based on available memory)
    conn.execute("PRAGMA cache_size = -10000")  # ~10MB

    # Control how often SQLite syncs to disk
    conn.execute("PRAGMA synchronous = NORMAL")

    conn.close()
```

### Process Supervision

In production, use proper process supervision:

```ini
# Example systemd service file for GigQ workers
[Unit]
Description=GigQ Worker
After=network.target

[Service]
User=appuser
WorkingDirectory=/path/to/app
ExecStart=/path/to/python -m gigq.cli --db /path/to/jobs.db worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Database Backup

Regularly backup your job queue database:

```python
def backup_database(db_path, backup_dir):
    """Create a backup of the job queue database."""
    import shutil
    import datetime

    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    # Generate a timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create backup file path
    backup_path = os.path.join(backup_dir, f"jobs_backup_{timestamp}.db")

    # Copy the database file
    shutil.copy2(db_path, backup_path)

    # Vacuum the backup to optimize size
    conn = sqlite3.connect(backup_path)
    conn.execute("VACUUM")
    conn.close()

    return {"original": db_path, "backup": backup_path}
```

## Load Testing

Before deploying to production, load test your GigQ setup:

```python
def load_test_gigq(db_path, num_jobs=1000, num_workers=4, job_type="mixed"):
    """Run a load test for GigQ."""
    import time
    import random
    import multiprocessing

    # Create a queue
    queue = JobQueue(db_path)

    # Define test job functions
    def cpu_intensive_job(iterations=1000000):
        result = 0
        for i in range(iterations):
            result += i * i
        return {"result": result}

    def io_intensive_job(sleep_time=0.1):
        time.sleep(sleep_time)
        return {"slept_for": sleep_time}

    def mixed_job(iterations=10000, sleep_time=0.05):
        result = 0
        for i in range(iterations):
            result += i * i
        time.sleep(sleep_time)
        return {"result": result, "slept_for": sleep_time}

    # Choose job function based on type
    if job_type == "cpu":
        job_func = cpu_intensive_job
    elif job_type == "io":
        job_func = io_intensive_job
    else:
        job_func = mixed_job

    # Submit jobs
    print(f"Submitting {num_jobs} jobs...")
    start_time = time.time()

    for i in range(num_jobs):
        job = Job(
            name=f"load_test_{i}",
            function=job_func,
            params={"iterations": random.randint(10000, 1000000)} if job_type != "io" else {"sleep_time": random.uniform(0.01, 0.2)},
            priority=random.randint(-10, 10)
        )
        queue.submit(job)

    submit_time = time.time() - start_time
    print(f"Submitted {num_jobs} jobs in {submit_time:.2f} seconds")

    # Start workers
    print(f"Starting {num_workers} workers...")
    processes = []
    for i in range(num_workers):
        p = multiprocessing.Process(target=run_worker, args=(db_path, f"worker-{i+1}"))
        p.start()
        processes.append(p)

    # Monitor progress
    total_jobs = num_jobs
    while True:
        time.sleep(5)
        pending = len(queue.list_jobs(status="pending"))
        running = len(queue.list_jobs(status="running"))
        completed = len(queue.list_jobs(status="completed"))
        failed = len(queue.list_jobs(status="failed"))

        progress = (completed + failed) / total_jobs * 100
        print(f"Progress: {progress:.1f}% | Pending: {pending} | Running: {running} | Completed: {completed} | Failed: {failed}")

        if pending == 0 and running == 0:
            break

    # Stop workers
    for p in processes:
        p.terminate()

    # Calculate stats
    end_time = time.time()
    total_time = end_time - start_time

    print(f"\nLoad Test Results:")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Average job time: {total_time / total_jobs:.4f} seconds")
    print(f"Jobs per second: {total_jobs / total_time:.2f}")

    return {
        "total_time": total_time,
        "jobs_per_second": total_jobs / total_time,
        "average_job_time": total_time / total_jobs
    }

def run_worker(db_path, worker_id):
    """Run a worker for load testing."""
    worker = Worker(db_path, worker_id=worker_id, polling_interval=0.1)
    worker.start()
```

## Next Steps

Now that you understand how to optimize GigQ's performance, you might want to explore:

- [Concurrency](concurrency.md) - Learn more about GigQ's concurrency model
- [SQLite Schema](sqlite-schema.md) - Understand the database schema for advanced optimization
- [Custom Job Types](custom-job-types.md) - Creating specialized job types
