# Core API Reference

This page documents the core classes and functions in the GigQ library.

## JobStatus

```python
class JobStatus(Enum):
    """Enum representing the possible states of a job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
```

An enumeration of possible job states:

- `PENDING`: The job is waiting to be executed
- `RUNNING`: The job is currently being executed by a worker
- `COMPLETED`: The job has successfully completed
- `FAILED`: The job has failed after exhausting all retry attempts
- `CANCELLED`: The job was cancelled by the user
- `TIMEOUT`: The job execution exceeded the timeout

## Job

```python
class Job:
    """
    Represents a job to be executed by the queue system.
    """
    def __init__(
        self,
        name: str,
        function: Callable,
        params: Dict[str, Any] = None,
        priority: int = 0,
        dependencies: List[str] = None,
        max_attempts: int = 3,
        timeout: int = 300,
        description: str = "",
    ):
        """
        Initialize a new job.

        Args:
            name: A name for the job.
            function: The function to execute.
            params: Parameters to pass to the function.
            priority: Job priority (higher numbers executed first).
            dependencies: List of job IDs that must complete before this job runs.
            max_attempts: Maximum number of execution attempts.
            timeout: Maximum runtime in seconds before the job is considered hung.
            description: Optional description of the job.
        """
```

The `Job` class represents a unit of work to be executed by the queue system.

### Properties

| Property       | Type     | Description                                                  |
| -------------- | -------- | ------------------------------------------------------------ |
| `id`           | str      | Unique identifier (UUID) for the job                         |
| `name`         | str      | Human-readable name for the job                              |
| `function`     | callable | The function to execute                                      |
| `params`       | dict     | Parameters to pass to the function                           |
| `priority`     | int      | Execution priority (higher values run first)                 |
| `dependencies` | list     | List of job IDs that must complete before this job runs      |
| `max_attempts` | int      | Maximum number of execution attempts                         |
| `timeout`      | int      | Maximum runtime in seconds before the job is considered hung |
| `description`  | str      | Optional description of the job                              |
| `created_at`   | str      | ISO format timestamp of when the job was created             |

### Example

```python
from gigq import Job

def process_data(filename, threshold=0.5):
    # Process data...
    return {"processed": True, "count": 42}

# Create a job
job = Job(
    name="process_data_job",
    function=process_data,
    params={"filename": "data.csv", "threshold": 0.7},
    priority=10,
    max_attempts=3,
    timeout=300,
    description="Process the daily data CSV file"
)
```

## JobQueue

```python
class JobQueue:
    """
    Manages a queue of jobs using SQLite as a backend.
    """
    def __init__(self, db_path: str, initialize: bool = True):
        """
        Initialize the job queue.

        Args:
            db_path: Path to the SQLite database file.
            initialize: Whether to initialize the database if it doesn't exist.
        """
```

The `JobQueue` class manages job persistence, state transitions, and retrieval.

### Methods

#### submit

```python
def submit(self, job: Job) -> str:
    """
    Submit a job to the queue.

    Args:
        job: The job to submit.

    Returns:
        The ID of the submitted job.
    """
```

Submits a job to the queue and returns its ID.

#### cancel

```python
def cancel(self, job_id: str) -> bool:
    """
    Cancel a pending job.

    Args:
        job_id: The ID of the job to cancel.

    Returns:
        True if the job was cancelled, False if it couldn't be cancelled.
    """
```

Cancels a pending job. Returns `True` if the job was cancelled, `False` otherwise (e.g., if the job is already running or completed).

#### get_status

```python
def get_status(self, job_id: str) -> Dict[str, Any]:
    """
    Get the current status of a job.

    Args:
        job_id: The ID of the job to check.

    Returns:
        A dictionary containing the job's status and related information.
    """
```

Returns a dictionary with the job's current status and details.

#### get_result

```python
def get_result(self, job_id: str) -> Optional[Any]:
    """
    Get the result value for a job.

    This returns the deserialized result for a completed job,
    or None if the job exists but is not yet completed or has
    no stored result. A KeyError is raised if the job does not exist.
    """
```

Provides a lightweight way to fetch only the job's return value, which is
especially useful for integrations (such as MCP tools) that don't need
the full status payload.

#### list_jobs

```python
def list_jobs(
    self,
    status: Optional[Union[JobStatus, str]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    List jobs in the queue, optionally filtered by status.

    Args:
        status: Filter jobs by this status.
        limit: Maximum number of jobs to return.

    Returns:
        A list of job dictionaries.
    """
```

Returns a list of jobs, optionally filtered by status.

#### clear_completed

```python
def clear_completed(self, before_timestamp: Optional[str] = None) -> int:
    """
    Clear completed jobs from the queue.

    Args:
        before_timestamp: Only clear jobs completed before this timestamp.

    Returns:
        Number of jobs cleared.
    """
```

Removes completed and cancelled jobs from the queue.

#### requeue_job

```python
def requeue_job(self, job_id: str) -> bool:
    """
    Requeue a failed job, resetting its attempts.

    Args:
        job_id: The ID of the job to requeue.

    Returns:
        True if the job was requeued, False if not.
    """
```

Resets a failed job to pending status for another attempt.

### Example

```python
from gigq import JobQueue, Job

# Create a job queue
queue = JobQueue("jobs.db")

# Submit a job
job = Job(name="example", function=example_function)
job_id = queue.submit(job)

# Check job status
status = queue.get_status(job_id)
print(f"Job status: {status['status']}")

# Get only the completed job result (if available)
result = queue.get_result(job_id)
if result is not None:
    print(f"Job result: {result}")

# List pending jobs
pending_jobs = queue.list_jobs(status="pending")

# Cancel a job
if queue.cancel(job_id):
    print(f"Job {job_id} cancelled")
```

## Worker

```python
class Worker:
    """
    A worker that processes jobs from the queue.
    """
    def __init__(
        self,
        db_path: str,
        worker_id: Optional[str] = None,
        polling_interval: int = 5
    ):
        """
        Initialize a worker.

        Args:
            db_path: Path to the SQLite database file.
            worker_id: Unique identifier for this worker (auto-generated if not provided).
            polling_interval: How often to check for new jobs, in seconds.
        """
```

The `Worker` class processes jobs from the queue.

### Methods

#### start

```python
def start(self):
    """Start the worker process."""
```

Starts the worker, which will continuously process jobs until stopped.

#### stop

```python
def stop(self):
    """Stop the worker process."""
```

Stops the worker after completing its current job (if any).

#### process_one

```python
def process_one(self) -> bool:
    """
    Process a single job from the queue.

    Returns:
        True if a job was processed, False if no job was available.
    """
```

Processes a single job from the queue and returns.

### Example

```python
from gigq import Worker

# Create a worker
worker = Worker("jobs.db")

# Process a single job
if worker.process_one():
    print("Processed one job")
else:
    print("No jobs available")

# Start the worker (blocks until stopped)
worker.start()
```

## Workflow

```python
class Workflow:
    """
    A utility class to help define workflows of dependent jobs.
    """
    def __init__(self, name: str):
        """
        Initialize a new workflow.

        Args:
            name: Name of the workflow.
        """
```

The `Workflow` class helps define and manage workflows with dependent jobs.

### Methods

#### add_job

```python
def add_job(self, job: Job, depends_on: List[Job] = None) -> Job:
    """
    Add a job to the workflow, with optional dependencies.

    Args:
        job: The job to add.
        depends_on: List of jobs this job depends on.

    Returns:
        The job that was added.
    """
```

Adds a job to the workflow, optionally specifying dependencies.

#### submit_all

```python
def submit_all(self, queue: JobQueue) -> List[str]:
    """
    Submit all jobs in the workflow to a queue.

    Args:
        queue: The job queue to submit to.

    Returns:
        List of job IDs that were submitted.
    """
```

Submits all jobs in the workflow to the queue.

### Example

```python
from gigq import Workflow, Job, JobQueue

# Create a workflow
workflow = Workflow("data_pipeline")

# Define jobs
job1 = Job(name="download", function=download_data)
job2 = Job(name="process", function=process_data)
job3 = Job(name="analyze", function=analyze_data)

# Add jobs with dependencies
workflow.add_job(job1)
workflow.add_job(job2, depends_on=[job1])
workflow.add_job(job3, depends_on=[job2])

# Submit all jobs
queue = JobQueue("workflow.db")
job_ids = workflow.submit_all(queue)

print(f"Submitted {len(job_ids)} jobs")
```

## Complete Usage Example

Here's a complete example showing how to use the core GigQ API:

```python
import time
from gigq import Job, JobQueue, Worker, Workflow, JobStatus

# Define job functions
def download_data(url):
    print(f"Downloading data from {url}")
    time.sleep(1)  # Simulate work
    return {"downloaded": True, "url": url, "bytes": 1024}

def process_data(downloaded_info):
    print(f"Processing data from {downloaded_info['url']}")
    time.sleep(2)  # Simulate work
    return {"processed": True, "records": 42}

def generate_report(processing_result):
    print(f"Generating report for {processing_result['records']} records")
    time.sleep(1)  # Simulate work
    return {"report_generated": True, "pages": 5}

# Create a job queue
queue = JobQueue("example.db")

# Create a workflow
workflow = Workflow("data_pipeline")

# Define jobs
download_job = Job(
    name="download_data",
    function=download_data,
    params={"url": "https://example.com/data.csv"}
)

process_job = Job(
    name="process_data",
    function=process_data,
    params={"downloaded_info": {"url": "https://example.com/data.csv", "bytes": 1024}}
)

report_job = Job(
    name="generate_report",
    function=generate_report,
    params={"processing_result": {"records": 42}}
)

# Add jobs to workflow with dependencies
workflow.add_job(download_job)
workflow.add_job(process_job, depends_on=[download_job])
workflow.add_job(report_job, depends_on=[process_job])

# Submit all jobs
job_ids = workflow.submit_all(queue)
print(f"Submitted {len(job_ids)} jobs")

# Create a worker and process jobs
worker = Worker("example.db")

# Process jobs one at a time
for _ in range(3):
    if worker.process_one():
        print("Processed one job")
    else:
        print("No jobs available")

    # Check status of all jobs
    for job_id in job_ids:
        status = queue.get_status(job_id)
        print(f"Job {status['name']}: {status['status']}")
```

## Extension Points

GigQ is designed to be extensible. Here are some common extension points:

### Custom Job Types

You can create subclasses of `Job` for specific types of jobs:

```python
class DataProcessingJob(Job):
    """A specialized job for data processing tasks."""

    def __init__(self, name, function, input_file, output_file, **kwargs):
        params = {
            "input_file": input_file,
            "output_file": output_file
        }
        super().__init__(name, function, params=params, **kwargs)
        self.input_file = input_file
        self.output_file = output_file
```

### Custom Worker Logic

You can subclass `Worker` to customize job processing behavior:

```python
class PrioritizedWorker(Worker):
    """A worker that only processes high-priority jobs."""

    def _claim_job(self):
        """Claim a job from the queue, but only high-priority ones."""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN EXCLUSIVE TRANSACTION")

            cursor = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ? AND priority > 50
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,)
            )

            # Rest of the method follows the original implementation...
```

### Custom Queue Persistence

While GigQ uses SQLite by default, you could extend the `JobQueue` class to use a different backend:

```python
class PostgresJobQueue(JobQueue):
    """A job queue that uses PostgreSQL as a backend."""

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self._initialize_db()

    def _get_connection(self):
        """Get a connection to the PostgreSQL database."""
        import psycopg2
        conn = psycopg2.connect(self.connection_string)
        return conn

    def _initialize_db(self):
        """Create the necessary database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tables with PostgreSQL syntax
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            -- Rest of the schema...
        )
        ''')

        # Create indices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)')

        conn.commit()
        conn.close()
```

## Internal API Methods

The following methods are used internally by GigQ and are not typically called directly by users, but understanding them can be helpful for advanced use cases or extending GigQ.

### Worker Internal Methods

#### `_get_connection()`

Gets a connection to the SQLite database with appropriate settings.

#### `_import_function(module_name, function_name)`

Dynamically imports a function from a module.

#### `_claim_job()`

Attempts to claim a job from the queue using an exclusive transaction.

#### `_complete_job(job_id, execution_id, status, result, error)`

Marks a job as completed or failed.

#### `_check_for_timeouts()`

Checks for jobs that have timed out and marks them accordingly.

### JobQueue Internal Methods

#### `_initialize_db()`

Creates the necessary database tables if they don't exist.

#### `_get_connection()`

Gets a connection to the SQLite database with appropriate settings.

## Thread Safety and Concurrency

GigQ is designed to work safely with multiple workers. Key points to understand:

- **Job claiming** is done in an exclusive transaction to ensure only one worker claims a job.
- **Job state transitions** are atomic.
- **SQLite locking** is used to manage concurrent access to the database.

When running multiple workers:

- They can be in separate processes or threads.
- They can be on different machines if they all have access to the same database file (e.g., via a network share).
- Workers will automatically respect job priorities and dependencies.

## Error Handling

GigQ includes several mechanisms for handling errors:

- **Automatic retries** based on the `max_attempts` setting.
- **Timeout detection** to recover from hung jobs.
- **Transaction-based state transitions** to maintain consistency even when errors occur.
- **Detailed error logging** to aid in debugging.

The `JobQueue` and `Worker` classes include appropriate error handling to ensure that database operations are safe and consistent.

## Performance Considerations

When using GigQ, keep these performance considerations in mind:

- **Worker polling interval** affects both responsiveness and database load.
- **Job timeouts** should be set appropriately for the expected runtime.
- **Database file location** can impact performance, especially over network shares.
- **Number of workers** should be balanced with available system resources.
- **Job priority** can be used to ensure critical jobs are processed first.

## Next Steps

Now that you understand the core API, you might want to explore:

- [CLI API Reference](cli.md) - Documentation for the command-line interface
- [Job Queue Management](../user-guide/job-queue.md) - More information on managing job queues
- [Workers](../user-guide/workers.md) - More information on worker configuration and usage
- [Workflows](../user-guide/workflows.md) - More information on creating complex workflows
