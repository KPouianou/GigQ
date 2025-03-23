# Frequently Asked Questions

This page answers common questions about using GigQ. If you don't find your question answered here, please check the detailed documentation or create an issue on GitHub.

## General Questions

### What is GigQ?

GigQ is a lightweight job queue system with SQLite as its backend. It's designed for managing and executing small jobs ("gigs") locally with atomicity guarantees, particularly suited for processing tasks that don't require a distributed system.

### When should I use GigQ?

GigQ is ideal for:

- Processing batches of data locally
- Running background tasks in a single application
- Creating simple workflows with dependencies
- Situations where you need job persistence but don't want to set up Redis, RabbitMQ, or other message brokers

### How does GigQ compare to Celery, RQ, or other task queues?

GigQ is more lightweight and simpler to set up than distributed task queues like Celery or RQ:

| Feature          | GigQ                      | Celery/RQ                               |
| ---------------- | ------------------------- | --------------------------------------- |
| Setup complexity | Low (SQLite only)         | Higher (requires Redis, RabbitMQ, etc.) |
| Scalability      | Moderate (single machine) | High (distributed)                      |
| Dependencies     | None beyond Python stdlib | Multiple dependencies                   |
| Job persistence  | Built-in (SQLite)         | Requires configuration                  |
| Workflows        | Simple built-in support   | Requires additional code/plugins        |
| Monitoring       | Basic CLI tools           | Advanced dashboards available           |

GigQ focuses on simplicity and ease of use for local job processing, while Celery and RQ are designed for distributed, high-throughput scenarios.

## Installation and Setup

### What are GigQ's dependencies?

GigQ has minimal dependencies:

- Python 3.9 or newer
- SQLite 3.8.3 or newer (included with Python)

### How do I install GigQ?

```bash
pip install gigq
```

### Can I use GigQ with a virtual environment?

Yes, and it's recommended:

```bash
python -m venv gigq-env
source gigq-env/bin/activate  # On Windows: gigq-env\Scripts\activate
pip install gigq
```

## Jobs and Job Queue

### How do I submit a job?

```python
from gigq import Job, JobQueue

def process_data(data):
    # Process the data...
    return {"result": "processed"}

queue = JobQueue("jobs.db")
job = Job(name="process", function=process_data, params={"data": "example"})
job_id = queue.submit(job)
```

### How do I check a job's status?

```python
status = queue.get_status(job_id)
print(f"Job status: {status['status']}")
```

### Can I cancel a job?

Yes, pending jobs can be cancelled:

```python
if queue.cancel(job_id):
    print("Job cancelled successfully")
else:
    print("Job could not be cancelled (may be running or completed)")
```

### How do I handle job failures?

GigQ automatically retries failed jobs based on the `max_attempts` setting. You can also manually requeue failed jobs:

```python
if queue.requeue_job(job_id):
    print("Job requeued successfully")
```

### Can job functions accept and return complex data?

Yes, job parameters and results are stored as JSON, so any JSON-serializable data can be passed to jobs and returned from them. This includes:

- Dictionaries
- Lists
- Strings
- Numbers
- Booleans
- None
- Nested combinations of the above

Non-serializable data (like file handles, database connections, etc.) cannot be passed directly and should be initialized within the job function.

## Workers

### How do I start a worker?

```python
from gigq import Worker

worker = Worker("jobs.db")
worker.start()  # This blocks until the worker is stopped
```

Or via the CLI:

```bash
gigq --db jobs.db worker
```

### How many workers can I run simultaneously?

You can run multiple workers simultaneously, limited primarily by your system resources and SQLite's concurrency capabilities. For most use cases, 2-8 workers is a reasonable range.

### How do workers handle job failures?

When a job fails (raises an exception):

1. The worker logs the error
2. The job's attempt counter is incremented
3. If attempts < max_attempts, the job is requeued
4. If attempts >= max_attempts, the job is marked as failed

### Do workers automatically recover timed-out jobs?

Yes. When a worker starts, it checks for jobs that have been running longer than their timeout and either requeues them or marks them as timed out.

### Can workers run on different machines?

Yes, but they must all have access to the same SQLite database file. This could be on a network share, but be aware that SQLite has limitations when accessed over a network. For distributed scenarios, consider using a more appropriate backend.

## Workflows

### How do I create a workflow with dependencies?

```python
from gigq import Workflow, Job, JobQueue

workflow = Workflow("data_pipeline")

job1 = Job(name="download", function=download_data)
job2 = Job(name="process", function=process_data)
job3 = Job(name="analyze", function=analyze_data)

workflow.add_job(job1)
workflow.add_job(job2, depends_on=[job1])
workflow.add_job(job3, depends_on=[job2])

queue = JobQueue("workflow.db")
job_ids = workflow.submit_all(queue)
```

### What happens if a job in a workflow fails?

If a job fails after all retry attempts, any dependent jobs won't run. This prevents cascading failures and ensures data integrity.

### Can I have conditional workflows?

GigQ doesn't directly support conditional workflows, but you can simulate them by:

1. Having a job function return data indicating which path to take
2. Creating a "router" job that submits additional jobs based on the result of a previous job

## Performance and Scaling

### Is SQLite fast enough for production use?

For many use cases, yes. SQLite can handle thousands of jobs per second on modern hardware. However, it's important to consider:

- SQLite's concurrency limitations (it uses file-level locking)
- Network file system performance if the database is shared
- The nature and size of your jobs

### How can I optimize GigQ performance?

1. Use appropriate polling intervals for your workload
2. Run the right number of workers for your hardware
3. Keep the SQLite database on fast local storage
4. Regularly clean up completed jobs
5. Set appropriate job timeouts
6. Use job priorities effectively

### What are the limitations of GigQ?

GigQ is primarily designed for local job processing and has some limitations:

- Not designed for distributed processing across multiple machines
- Limited by SQLite's concurrency capabilities
- No built-in monitoring dashboard
- Simple priority system may not suit complex scheduling needs

## Command Line Interface

### How do I list jobs from the command line?

```bash
gigq --db jobs.db list
gigq --db jobs.db list --status pending
```

### How do I run a worker that processes just one job?

```bash
gigq --db jobs.db worker --once
```

### How do I submit a job from the command line?

```bash
gigq --db jobs.db submit my_module.my_function --name "My Job" --param "filename=data.csv"
```

### How do I clear old jobs from the database?

```bash
gigq --db jobs.db clear --before 7  # Clear jobs completed more than 7 days ago
```

## Security and Data

### Is my data secure with GigQ?

GigQ uses SQLite, which provides basic security through file permissions. However:

- Job parameters and results are stored as plain text in the database
- No encryption is used for data at rest
- Authentication and authorization must be handled by your application

For sensitive data, consider implementing appropriate security measures in your application.

### How do I backup my GigQ data?

Since GigQ uses SQLite, you can simply backup the database file. Make sure to:

1. Either stop all workers before backup, or
2. Use SQLite's backup API or tools designed for hot backups

### Can I use GigQ with Docker?

Yes, GigQ works well in Docker containers. Just ensure that:

- The SQLite database is stored in a persistent volume
- Workers can access the database file
- Signal handling is properly configured

## Troubleshooting

### Why is my job stuck in the "running" state?

This can happen if:

1. A worker crashed while processing the job
2. The job exceeded its timeout but no worker has checked for timeouts yet

Solutions:

- Start a worker, which will check for timed-out jobs
- Manually update the job status in the database
- Increase the job's timeout if it's legitimately long-running

### Why am I getting SQLite locking errors?

SQLite uses file-level locking, which can cause contention with many concurrent workers. Try:

- Reducing the number of workers
- Increasing the polling interval
- Using the `timeout` parameter for SQLite connections (GigQ uses 30 seconds by default)

### How do I debug a failing job?

1. Check the job's error message:

   ```python
   status = queue.get_status(job_id)
   print(f"Error: {status.get('error')}")
   ```

2. Use logging in your job function:

   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. Try running the function directly with the same parameters

### Can I use GigQ with Django/Flask/FastAPI?

Yes, GigQ can be used with any Python web framework. Typical patterns:

- Submit jobs from web handlers
- Run workers as separate processes
- Use the job queue to track the status of long-running operations

## Advanced Usage

### Can I extend GigQ with custom features?

Yes, GigQ is designed to be extensible. You can:

- Subclass `Job`, `Worker`, or `JobQueue` to customize behavior
- Create utility functions for common patterns
- Integrate with other systems through job functions

### Can I use GigQ with a different database backend?

GigQ is specifically designed for SQLite, but you could theoretically create a custom `JobQueue` implementation that uses a different backend. This would require reimplementing much of the queue logic.

### How do I implement a periodic job scheduler with GigQ?

GigQ doesn't have built-in scheduling, but you can:

1. Use a system scheduler (cron, Windows Task Scheduler) to submit jobs
2. Create a daemon process that submits jobs on a schedule
3. Use a dedicated scheduling library alongside GigQ

Example with a simple daemon:

```python
import time
import schedule
from gigq import Job, JobQueue

queue = JobQueue("scheduled_jobs.db")

def submit_daily_job():
    job = Job(name="daily_process", function=daily_processing)
    queue.submit(job)

schedule.every().day.at("01:00").do(submit_daily_job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Contributing to GigQ

### How can I contribute to GigQ?

We welcome contributions! You can:

- Report bugs and suggest features via GitHub issues
- Submit pull requests for bug fixes or enhancements
- Improve documentation
- Share examples and use cases

### How do I run the GigQ tests?

```bash
git clone https://github.com/kpouianou/gigq.git
cd gigq
python -m unittest discover tests
```

### Where can I get help with GigQ?

- Check the [documentation](https://github.com/kpouianou/gigq)
- Create an issue on [GitHub](https://github.com/kpouianou/gigq/issues)
- Ask questions on Stack Overflow with the "gigq" tag
