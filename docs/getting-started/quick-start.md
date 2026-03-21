# Quick Start

## Define and Run a Task

The `@task` decorator is the simplest way to use GigQ. Decorate a function, submit it to a queue, and start a worker:

```python
from gigq import task, JobQueue, Worker

@task(max_attempts=3, timeout=300)
def process_file(filename, threshold=0.5):
    with open(filename, 'r') as f:
        content = f.read()
    word_count = len(content.split())
    return {"filename": filename, "word_count": word_count}

# Submit a job — parameters are keyword arguments
queue = JobQueue("my_jobs.db")
job_id = process_file.submit(queue, filename="data.csv", threshold=0.7)

# Start a worker to process jobs (blocks until stopped with Ctrl+C)
Worker("my_jobs.db").start()
```

The decorator supports `priority`, `max_attempts`, `timeout`, `description`, and `name`. The function stays directly callable for testing: `process_file("test.txt")`.

## Check Results

```python
# Get full status
status = queue.get_status(job_id)
print(f"Job status: {status['status']}")

# Get just the return value
result = queue.get_result(job_id)
print(f"Result: {result}")
```

## Workflows with `parent_results`

Build pipelines by wiring `@task` functions into a `Workflow`. Dependent tasks declare a `parent_results` parameter and automatically receive a dict of parent job ID to deserialized result.

### Fan-out / fan-in

```python
from gigq import task, JobQueue, Workflow, Worker

@task()
def source():
    return {"items": [1, 2, 3]}

@task()
def branch_a(parent_results):
    data = next(iter(parent_results.values()))
    return {"branch": "a", "len": len(data["items"])}

@task()
def branch_b(parent_results):
    data = next(iter(parent_results.values()))
    return {"branch": "b", "len": len(data["items"])}

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

The `merge` task receives both `branch_a` and `branch_b` results in a single dict, keyed by parent job ID.

### Linear pipeline

```python
@task()
def generate():
    return {"numbers": list(range(10))}

@task()
def transform(parent_results):
    data = next(iter(parent_results.values()))
    evens = [n for n in data["numbers"] if n % 2 == 0]
    return {"evens": evens, "count": len(evens)}

@task()
def summarize(parent_results):
    data = next(iter(parent_results.values()))
    return {"summary": f"Found {data['count']} even numbers"}

wf = Workflow("pipeline")
step1 = wf.add_task(generate)
step2 = wf.add_task(transform, depends_on=[step1])
wf.add_task(summarize, depends_on=[step2])
wf.submit_all(queue)
```

## Using the Command Line Interface

GigQ provides a CLI for working with jobs.

### Submit a Job

```bash
gigq --db my_jobs.db submit my_module.process_file --name "Process CSV" --param "filename=data.csv" --param "threshold=0.7"
```

### Start a Worker

```bash
# Start a worker
gigq --db my_jobs.db worker

# With concurrent threads
gigq --db my_jobs.db worker --concurrency 4

# Process just one job
gigq --db my_jobs.db worker --once
```

### Check Job Status

```bash
gigq --db my_jobs.db status your-job-id --show-result
```

### List Jobs

```bash
gigq --db my_jobs.db list
gigq --db my_jobs.db list --status pending
```

### Queue Stats

```bash
gigq --db my_jobs.db stats
```

## Using `Job()` Directly

For full control over job configuration, you can construct `Job` objects directly instead of using `@task`:

```python
from gigq import Job, JobQueue

queue = JobQueue("my_jobs.db")
job = Job(
    name="process_csv_file",
    function=process_file,
    params={"filename": "data.csv", "threshold": 0.7},
    max_attempts=3,
    timeout=300,
    priority=5,
)
job_id = queue.submit(job)
```

Jobs can also be added to workflows via `workflow.add_job(job, depends_on=[...])`.

## Next Steps

- Learn about the [`@task` decorator](../user-guide/decorators.md) options
- Explore [workflow capabilities](../user-guide/workflows.md) including `parent_results`
- See a [parallel tasks example](../examples/parallel-tasks.md) combining decorators and concurrency
- Understand [error handling](../user-guide/error-handling.md) and retries
