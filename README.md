<h1 align="center">
  <span style="color: #4f81e6;">Gig</span><span style="color: #60cdff;">Q</span>
</h1>
<p align="center">Lightweight SQLite Job Queue</p>

<p align="center">
  <a href="https://pypi.org/project/gigq/"><img alt="PyPI" src="https://img.shields.io/pypi/v/gigq.svg?style=flat-square"></a>
  <a href="https://pypi.org/project/gigq/"><img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/gigq.svg?style=flat-square"></a>
  <a href="https://github.com/kpouianou/gigq/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/kpouianou/gigq?style=flat-square"></a>
  <a href="https://github.com/kpouianou/gigq/actions/workflows/ci.yml"><img alt="Build Status" src="https://img.shields.io/github/actions/workflow/status/kpouianou/gigq/ci.yml?branch=main&style=flat-square"></a>
</p>

**A job queue that lives in a single file. No Redis. No infrastructure. Just `pip install` and go.**

GigQ is a small Python library that runs background work through a **SQLite** database on disk. It fits teams and side projects that have outgrown a raw `for` loop with `try`/`except`, but do not want to operate Redis, a broker, or cloud queue infrastructure. You define functions, enqueue them, and run one or more workers on any machine that can see the database file.

```python
from gigq import task, JobQueue, Worker

@task()
def greet(name="world"):
    return f"Hello, {name}!"

queue = JobQueue("jobs.db")
greet.submit(queue, name="Alice")
Worker("jobs.db").start()
```

You get **retries with backoff**, **crash recovery** (stuck work is reclaimed), and **queryable status and results** from the same DB the workers use.

## When to use GigQ

**Good fit**

- Local or single-server automation, ETL, scraping batches, ML prep, or any scriptable work you want off the request path
- A few concurrent worker threads or processes against one SQLite file
- You are fine storing queue state in a file next to your app

**Not the right tool**

- Multi-datacenter orchestration, strict global ordering, or millions of jobs per second
- When you already run Redis/Kafka/SQS and need their ecosystem

## Workflows and `parent_results`

Model pipelines as a **DAG**: add `@task` functions to a `Workflow`, wire dependencies, then submit once. Dependent tasks can declare a `parent_results` argument; GigQ injects a dict of **parent job id → deserialized result** so fan-out and fan-in steps can pass data without serializing it through job parameters.

```python
from gigq import task, JobQueue, Workflow, Worker

@task()
def source():
    return {"items": [1, 2, 3]}

@task()
def branch_a(parent_results):
    n = next(iter(parent_results.values()))["items"]
    return {"branch": "a", "len": len(n)}

@task()
def branch_b(parent_results):
    n = next(iter(parent_results.values()))["items"]
    return {"branch": "b", "len": len(n)}

@task()
def merge(parent_results):
    return {"combined": list(parent_results.values())}

queue = JobQueue("jobs.db")
wf = Workflow("fan")
s = wf.add_task(source)
a = wf.add_task(branch_a, depends_on=[s])
b = wf.add_task(branch_b, depends_on=[s])
wf.add_task(merge, depends_on=[a, b])
wf.submit_all(queue)
Worker("jobs.db").start()
```

## Installation

```bash
pip install gigq
```

## CLI

The `gigq` command uses `--db` (default `gigq.db`) and a subcommand:

| Command | Purpose |
|--------|---------|
| `gigq worker` | Run a worker; add `--concurrency N` for threaded workers |
| `gigq list` | List jobs; optional `--status pending` (etc.) |
| `gigq status <id> --show-result` | Inspect a job and its result |
| `gigq stats` | Aggregate counts by status |
| `gigq submit` | Enqueue by import path `module.function` |

## How it works

Jobs, dependencies, and results live in **SQLite** tables (`jobs`, `job_executions`). Workers claim work in **transactions** so only one worker runs a given job at a time; multiple threads or processes coordinate through the database file (WAL mode is enabled for less contention). Retries and timeouts are enforced in the worker loop.

## Examples

| Example | Description |
|--------|-------------|
| [`examples/parallel_tasks.py`](examples/parallel_tasks.py) | Fan-out workers plus a fan-in task using `parent_results` |
| [`examples/data_pipeline.py`](examples/data_pipeline.py) | Linear pipeline: generate → transform → format via `parent_results` |
| [`examples/hyperparameter_tuning.py`](examples/hyperparameter_tuning.py) | scikit-learn search with sequential vs parallel workers and crash recovery |

## Integrations

- **[`mcp_server/`](mcp_server/)** — **Model Context Protocol** server (`gigq-mcp`) so agents can submit jobs, inspect queues, and read results. See the [MCP integration docs](https://gigq.github.io/gigq/integrations/mcp/).

## Documentation

Full guides and API reference: **[https://gigq.github.io/gigq](https://gigq.github.io/gigq)**

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
