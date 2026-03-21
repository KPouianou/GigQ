# Task Decorator

The `@task` decorator provides a concise way to define GigQ jobs. Instead of manually constructing `Job` objects, you decorate your functions and gain `.submit()` and `.to_job()` methods — while the function itself remains directly callable.

## Basic Usage

### Bare Decorator

The simplest form uses `@task` with no arguments:

```python
from gigq import task, JobQueue

@task
def process_file(filename, threshold=0.5):
    with open(filename) as f:
        lines = f.readlines()
    return {"lines": len(lines), "threshold": threshold}

# The function still works normally
result = process_file("data.txt", threshold=0.8)

# But now you can also submit it as a job
queue = JobQueue("jobs.db")
job_id = process_file.submit(queue, filename="data.txt", threshold=0.8)
```

### Decorator with Options

Pass job options at decoration time to configure retry behavior, timeouts, priority, and more:

```python
@task(max_attempts=5, timeout=120, priority=10)
def fetch_api_data(endpoint, page=1):
    # ... fetch data from API ...
    return {"records": 42, "page": page}
```

All options are fixed when the decorator is applied — they cannot be changed at submit time. This keeps the API simple and predictable.

## Available Options

| Option         | Type | Default | Description                                 |
| -------------- | ---- | ------- | ------------------------------------------- |
| `name`         | str  | `fn.__name__` | Job name visible in the queue and logs |
| `priority`     | int  | 0       | Higher values run first                     |
| `max_attempts` | int  | 3       | Retries on failure before marking as failed |
| `timeout`      | int  | 300     | Maximum runtime in seconds                  |
| `description`  | str  | `""`    | Optional human-readable description         |
| `retry_delay`  | int  | 0       | Seconds to wait before retrying after failure |

## Submitting Jobs

Use `.submit()` to create and enqueue a job in one call. Pass the function's parameters as keyword arguments:

```python
queue = JobQueue("jobs.db")

# Submit returns the job ID
job_id = fetch_api_data.submit(queue, endpoint="/users", page=3)

# Check status later
status = queue.get_status(job_id)
print(status["status"])  # "pending", "running", "completed", ...
```

The `queue` argument is positional-only to avoid conflicts with your function's parameter names.

## Creating Jobs Without Submitting

Use `.to_job()` when you need a `Job` object but don't want to submit it yet — for example, to add it to a `Workflow`:

```python
job = fetch_api_data.to_job(endpoint="/repos", page=1)
print(job.name)       # "fetch_api_data"
print(job.params)     # {"endpoint": "/repos", "page": 1}
print(job.timeout)    # 120
```

## Workflows with `add_task`

The `Workflow` class has an `add_task` method that accepts `@task`-decorated functions directly, so you don't need to call `.to_job()` yourself:

```python
from gigq import task, Workflow, JobQueue, Worker

@task(timeout=60)
def download(url):
    # ... download data ...
    return {"path": "/tmp/data.csv"}

@task(timeout=120)
def transform(input_path):
    # ... transform data ...
    return {"path": "/tmp/cleaned.csv"}

@task(timeout=300)
def load(input_path, table_name):
    # ... load into database ...
    return {"rows_loaded": 1500}

# Build a dependency graph
wf = Workflow("etl_pipeline")
dl = wf.add_task(download, params={"url": "https://example.com/data.csv"})
tr = wf.add_task(transform, params={"input_path": "/tmp/data.csv"}, depends_on=[dl])
ld = wf.add_task(load, params={"input_path": "/tmp/cleaned.csv", "table_name": "events"}, depends_on=[tr])

# Submit all jobs with dependencies wired up
queue = JobQueue("pipeline.db")
job_ids = wf.submit_all(queue)
```

## Direct Calling

Decorated functions remain directly callable. This is essential for testing and for the worker to execute them:

```python
@task(timeout=30)
def add(x, y):
    return x + y

# Works exactly like the original function
assert add(2, 3) == 5
```

## Combining with Concurrency

The `@task` decorator pairs naturally with concurrent workers. Decorate your functions, submit many jobs, and let a multi-threaded worker chew through them:

```python
@task(timeout=60, max_attempts=2)
def process_chunk(chunk_id, data_path):
    # ... process one chunk ...
    return {"chunk_id": chunk_id, "rows": 10000}

queue = JobQueue("processing.db")

# Submit a batch of jobs
for i in range(20):
    process_chunk.submit(queue, chunk_id=i, data_path=f"/data/chunk_{i}.csv")

# Process with 4 concurrent threads
worker = Worker("processing.db", concurrency=4)
worker.start()
```

See the [Parallel Tasks example](../examples/parallel-tasks.md) for a complete runnable demonstration.

## Validation Rules

The `@task` decorator validates your function at decoration time and raises `TypeError` with a clear message if any of these rules are violated:

| Rule | Rationale |
| ---- | --------- |
| Must be a named callable | The worker resolves functions by `__module__` + `__name__` |
| Must be defined at module level | Closures and nested functions can't be imported by the worker |
| Cannot be a lambda | Lambdas have no stable `__name__` |
| Cannot be async or a generator | GigQ workers call functions synchronously |
| Cannot be a class method | Methods require an instance the worker doesn't have |
| Cannot be applied twice | Prevents accidental double-wrapping |
| Only known options allowed | Catches typos like `@task(timout=60)` early |

## Decorator vs. Explicit Job

Both approaches are fully supported. Use whichever fits your style:

=== "Decorator"

    ```python
    from gigq import task, JobQueue

    @task(max_attempts=5, timeout=120)
    def my_job(x, y):
        return x + y

    queue = JobQueue("jobs.db")
    job_id = my_job.submit(queue, x=1, y=2)
    ```

=== "Explicit Job"

    ```python
    from gigq import Job, JobQueue

    def my_job(x, y):
        return x + y

    queue = JobQueue("jobs.db")
    job = Job(
        name="my_job",
        function=my_job,
        params={"x": 1, "y": 2},
        max_attempts=5,
        timeout=120,
    )
    job_id = queue.submit(job)
    ```

The decorator approach is more concise when the same function is always submitted with the same job options. The explicit `Job()` approach gives you full control when you need different options per submission.

## Next Steps

- [Parallel Tasks example](../examples/parallel-tasks.md) — see decorators + concurrency in action
- [Hyperparameter Tuning example](../examples/hyperparameter-tuning.md) — a real-world data science use case
- [Workers](workers.md) — learn about concurrent processing
- [Workflows](workflows.md) — build dependency graphs
