# Scheduling Jobs

GigQ doesn't include a built-in scheduler — it doesn't need one. The queue handles persistence and delivery; scheduling is just submitting jobs on a timer. Two patterns cover virtually every case.

!!! note
    In both patterns, a worker must be running independently to process submitted jobs. Start one in a separate terminal or run it as a system service:

    ```bash
    gigq worker --db jobs.db
    ```

## Pattern 1: System Cron + CLI

The simplest approach. Use your system's cron daemon to call `gigq submit` on a schedule.

Say you have a task function in a module:

```python
# tasks.py
def generate_report(format="pdf"):
    """Generate the daily summary report."""
    # ... your logic here ...
    return {"status": "done", "format": format}
```

Add a crontab entry to submit a job every hour:

```
# Run 'crontab -e' to edit
0 * * * * gigq submit tasks.generate_report --name "Hourly report" --param "format=pdf" --db /path/to/jobs.db
```

That's it. Cron handles the schedule, `gigq submit` creates the job, and the worker picks it up.

## Pattern 2: Python Loop

When cron isn't available — Windows machines, containers without cron, or cases where you want submission logic in Python — use a simple loop:

```python
import time
from gigq import Job, JobQueue

queue = JobQueue("jobs.db")

while True:
    job = Job(
        name="Hourly report",
        function="tasks.generate_report",
        params={"format": "pdf"},
    )
    queue.submit(job)
    time.sleep(3600)  # wait one hour
```

This is just a submission loop — it puts jobs on the queue but doesn't run them. The worker processes jobs separately, as always.

!!! tip
    For either pattern, you can set `max_attempts` and `retry_delay` on the job to handle transient failures automatically. See [Error Handling](error-handling.md) for details.
