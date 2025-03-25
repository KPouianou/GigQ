# Job Queue

The `JobQueue` is the central component in GigQ that manages job persistence, state transitions, and retrieval. This guide explains how to use the job queue to submit, monitor, and manage jobs.

## Creating a Job Queue

To create a job queue, instantiate the `JobQueue` class with a path to a SQLite database file:

```python
from gigq import JobQueue

# Create a new job queue (or connect to an existing one)
queue = JobQueue("jobs.db")
```

If the database file doesn't exist, it will be created automatically. If it does exist, the queue will connect to it.

You can also specify whether to initialize the database:

```python
# Connect without initializing (useful if you're sure the DB is already initialized)
queue = JobQueue("jobs.db", initialize=False)
```

## Submitting Jobs

Once you have a job queue, you can submit jobs to it:

```python
from gigq import Job

# Create a job
job = Job(
    name="example_job",
    function=process_data,
    params={"data": "example"}
)

# Submit the job
job_id = queue.submit(job)
print(f"Submitted job with ID: {job_id}")
```

The `submit` method returns the job ID, which you can use to track the job's status.

## Checking Job Status

To check the status of a job, use the `get_status` method:

```python
# Get job status
status = queue.get_status(job_id)

print(f"Job status: {status['status']}")
print(f"Created at: {status['created_at']}")

if status['status'] == 'completed':
    print(f"Result: {status['result']}")
elif status['status'] == 'failed':
    print(f"Error: {status['error']}")
```

The `get_status` method returns a dictionary with the following keys:

| Key            | Description                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| `exists`       | Boolean indicating if the job exists in the queue                           |
| `id`           | The job ID                                                                  |
| `name`         | The job name                                                                |
| `status`       | Current status (pending, running, completed, failed, cancelled, timeout)    |
| `created_at`   | ISO format timestamp of when the job was created                            |
| `updated_at`   | ISO format timestamp of when the job was last updated                       |
| `attempts`     | Number of execution attempts                                                |
| `max_attempts` | Maximum number of attempts                                                  |
| `started_at`   | When the job started (if it has started)                                    |
| `completed_at` | When the job completed (if it has completed)                                |
| `params`       | The parameters passed to the job                                            |
| `result`       | The job result (if completed)                                               |
| `error`        | Error message (if failed)                                                   |
| `worker_id`    | ID of the worker processing the job (if running)                            |
| `executions`   | List of execution attempts (each with id, status, started_at, completed_at) |

## Listing Jobs

To list jobs in the queue, use the `list_jobs` method:

```python
from gigq import JobStatus

# List all jobs
all_jobs = queue.list_jobs()

# List only pending jobs
pending_jobs = queue.list_jobs(status=JobStatus.PENDING)

# List with a limit
recent_jobs = queue.list_jobs(limit=10)

# Print job information
for job in pending_jobs:
    print(f"{job['id']}: {job['name']} (priority: {job['priority']})")
```

The `list_jobs` method returns a list of job dictionaries with the same keys as `get_status`.

## Cancelling Jobs

To cancel a pending job:

```python
# Cancel a job
result = queue.cancel(job_id)

if result:
    print(f"Job {job_id} cancelled successfully")
else:
    print(f"Failed to cancel job {job_id} (may not be in pending state)")
```

The `cancel` method returns `True` if the job was cancelled, or `False` if it couldn't be cancelled (e.g., because it's already running or completed).

## Requeuing Failed Jobs

If a job fails, you can requeue it:

```python
# Requeue a failed job
result = queue.requeue_job(job_id)

if result:
    print(f"Job {job_id} requeued successfully")
else:
    print(f"Failed to requeue job {job_id} (may not be in failed state)")
```

The `requeue_job` method:

- Resets the job's `attempts` counter to 0
- Sets the job's status to `pending`
- Clears the error message
- Returns `True` if successful, `False` otherwise

## Clearing Completed Jobs

To clean up the queue by removing completed or cancelled jobs:

```python
# Clear all completed and cancelled jobs
count = queue.clear_completed()
print(f"Cleared {count} completed jobs")

# Clear jobs completed before a certain date
from datetime import datetime, timedelta
one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
count = queue.clear_completed(before_timestamp=one_week_ago)
print(f"Cleared {count} jobs older than one week")
```

## Connection Management

GigQ uses thread-local connection management to efficiently reuse SQLite connections. When you're done using a `JobQueue` instance, you should close its connection:

```python
# Close the connection for this queue
queue.close()
```

Or to close all connections in the current thread:

```python
from gigq import close_connections

# Close all connections in the current thread
close_connections()
```

This is especially important in multi-threaded applications or long-running processes to avoid resource leaks.

## Job Queue Persistence

The job queue uses SQLite as its backend, which provides:

1. **Persistence** - Jobs remain in the queue even if the application restarts
2. **Atomicity** - Job state transitions are atomic (all-or-nothing)
3. **Concurrency** - Multiple workers can access the queue safely

When you create a `JobQueue` with the same database file, you're connecting to the same queue. This allows you to:

- Submit jobs from one process
- Process jobs from another process
- Monitor jobs from a third process

All while maintaining consistency.

## Advanced Usage

### Working with Job Dependencies

When submitting jobs with dependencies, the queue ensures that dependent jobs only run after their dependencies are complete:

```python
# Create and submit a job
job1 = Job(name="first_job", function=first_function)
job1_id = queue.submit(job1)

# Create and submit a dependent job
job2 = Job(
    name="second_job",
    function=second_function,
    dependencies=[job1_id]
)
job2_id = queue.submit(job2)

# Clean up when done
queue.close()
```

The second job will only be picked up by workers after the first job has completed successfully.

### Using Custom Job Processing Order

By default, workers process jobs in order of:

1. Priority (higher first)
2. Creation time (older first)

You can use the priority parameter to control processing order:

```python
# High priority job (processes first)
high_job = Job(name="urgent", function=urgent_task, priority=100)
queue.submit(high_job)

# Normal priority job
normal_job = Job(name="normal", function=normal_task, priority=0)
queue.submit(normal_job)

# Low priority job (processes last)
low_job = Job(name="background", function=background_task, priority=-100)
queue.submit(low_job)
```

### Monitoring Job Progress

For long-running jobs, you might want to periodically check their status:

```python
import time

# Create a job queue
queue = JobQueue("jobs.db")

# Submit a job
job_id = queue.submit(long_running_job)

try:
    # Monitor the job
    while True:
        status = queue.get_status(job_id)
        print(f"Job status: {status['status']}")

        if status['status'] in ('completed', 'failed', 'cancelled', 'timeout'):
            break

        time.sleep(5)  # Check every 5 seconds
finally:
    # Always close the queue when done
    queue.close()
```

### Working with Multiple Queues

You can work with multiple queues by creating multiple `JobQueue` instances:

```python
# Create different queues for different types of jobs
high_priority_queue = JobQueue("high_priority.db")
background_queue = JobQueue("background.db")

try:
    # Submit to the appropriate queue
    high_priority_queue.submit(important_job)
    background_queue.submit(background_job)

    # Create workers for each queue
    high_worker = Worker("high_priority.db")
    background_worker = Worker("background.db")

    # Process jobs...
finally:
    # Clean up all connections
    high_priority_queue.close()
    background_queue.close()
    high_worker.close()
    background_worker.close()
```

This allows you to:

- Separate different types of jobs
- Allocate different resources to different queues
- Manage priorities across job categories

## Thread-Safe Usage

GigQ uses thread-local connection management to ensure thread safety:

```python
import threading
from gigq import JobQueue, Worker, close_connections

def worker_thread(db_path):
    # Each thread gets its own connections
    queue = JobQueue(db_path)
    worker = Worker(db_path)

    try:
        # Process jobs
        worker.start()
    except KeyboardInterrupt:
        worker.stop()
    finally:
        # Clean up connections
        queue.close()
        worker.close()
        close_connections()  # Close any other connections in this thread

# Create multiple worker threads
threads = []
for i in range(4):
    thread = threading.Thread(target=worker_thread, args=("jobs.db",))
    thread.daemon = True
    threads.append(thread)
    thread.start()

# Wait for threads to complete
for thread in threads:
    thread.join()
```

## Best Practices

1. **Use a consistent database path** across all components that need to access the same queue.

2. **Always close connections** when you're done with them to prevent resource leaks.

3. **Regularly clean up completed jobs** to keep the database size manageable, either through `clear_completed()` or by setting up a periodic task.

4. **Monitor queue size** - If the queue grows continuously, it may indicate that you need more workers or that jobs are taking too long to process.

5. **Use appropriate error handling** when submitting jobs or checking status to account for potential database connectivity issues.

## Example: Job Queue Dashboard

Here's an example of creating a simple dashboard for monitoring job queue status:

```python
def print_queue_stats(db_path):
    """Print statistics about the job queue."""

    # Create a queue to query the database
    queue = JobQueue(db_path)

    try:
        # Get job counts by status
        statuses = ["pending", "running", "completed", "failed", "cancelled", "timeout"]
        counts = {}

        for status in statuses:
            jobs = queue.list_jobs(status=status)
            counts[status] = len(jobs)

        total = sum(counts.values())

        # Print summary
        print(f"=== Job Queue Statistics ===")
        print(f"Total jobs: {total}")
        for status, count in counts.items():
            percentage = (count / total) * 100 if total > 0 else 0
            print(f"{status.capitalize()}: {count} ({percentage:.1f}%)")

        # Print recently completed jobs
        completed = queue.list_jobs(status="completed", limit=5)
        if completed:
            print("\nRecently completed jobs:")
            for job in completed:
                print(f"  {job['name']} - Completed at {job['completed_at']}")

        # Print failed jobs
        failed = queue.list_jobs(status="failed", limit=5)
        if failed:
            print("\nRecent failures:")
            for job in failed:
                print(f"  {job['name']} - {job['error']}")
    finally:
        # Always close the queue when done
        queue.close()

# Usage
print_queue_stats("jobs.db")
```

## Next Steps

Now that you understand how to manage jobs in the queue, learn how to:

- [Process jobs with workers](workers.md)
- [Create workflows with dependencies](workflows.md)
- [Handle errors and retries](error-handling.md)
