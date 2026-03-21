# GigQ: Lightweight Local Job Queue

<div style="text-align: center; margin: 30px 0;">
  <h1 style="font-size: 3.5rem; margin: 0; padding: 0;">
    <span style="color: #4f81e6;">Gig</span><span style="color: #60cdff;">Q</span>
  </h1>
  <p style="margin: 0; padding: 0; color: #a0aec0;">Lightweight SQLite Job Queue</p>
</div>

GigQ is a Python job queue backed by SQLite. It fits teams and projects that have outgrown a raw `for` loop with `try`/`except`, but don't want to run Redis or any other broker. Define functions, enqueue them, and run one or more workers on any machine that can reach the database file.

```python
from gigq import task, JobQueue, Worker

@task()
def greet(name="world"):
    return f"Hello, {name}!"

queue = JobQueue("jobs.db")
greet.submit(queue, name="Alice")
Worker("jobs.db").start()
```

## Features

- **Retry & crash recovery** — failed jobs are retried with backoff; if a worker crashes mid-job, the work is reclaimed automatically
- **Workflows** — wire tasks into a DAG with `Workflow`; dependent tasks receive parent return values via `parent_results`
- **Concurrent workers** — multiple threads or processes coordinate through the database file (WAL mode, no external locking)
- **CLI** — submit jobs, start workers, and inspect queues from the command line
- **Zero dependencies** — Python and SQLite only

## Job Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: Job Created
    PENDING --> RUNNING: Worker Claims Job
    RUNNING --> COMPLETED: Successful Execution
    RUNNING --> FAILED: Error (max attempts exceeded)
    RUNNING --> PENDING: Error (retry)
    RUNNING --> TIMEOUT: Execution Time Exceeded
    PENDING --> CANCELLED: User Cancellation
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
    TIMEOUT --> [*]
```

## Installation

```bash
pip install gigq
```

## Next Steps

Check out the [Quick Start Guide](getting-started/quick-start.md) to start using GigQ.

## License

GigQ is released under the MIT License. See [LICENSE](https://github.com/kpouianou/gigq/blob/main/LICENSE) for details.
