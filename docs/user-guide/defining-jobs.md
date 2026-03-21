# Defining Jobs

Jobs are the fundamental unit of work in GigQ. This guide explains how to define jobs, configure their parameters, and understand their lifecycle.

## Basic Job Definition

To create a job, you'll use the `Job` class:

```python
from gigq import Job

# Create a simple job
job = Job(
    name="process_data",
    function=process_data_function,
    params={"filename": "data.csv", "threshold": 0.7}
)
```

This creates a job that will execute the `process_data_function` with the specified parameters.

## Job Parameters

The `Job` class accepts the following parameters:

| Parameter      | Type     | Required | Description                                              |
| -------------- | -------- | -------- | -------------------------------------------------------- |
| `name`         | str      | Yes      | A human-readable name for the job                        |
| `function`     | callable | Yes      | The function to execute                                  |
| `params`       | dict     | No       | Parameters to pass to the function                       |
| `priority`     | int      | No       | Execution priority (higher values run first, default: 0) |
| `dependencies` | list     | No       | List of job IDs that must complete before this job runs  |
| `max_attempts` | int      | No       | Maximum number of execution attempts (default: 3)        |
| `timeout`      | int      | No       | Maximum runtime in seconds (default: 300)                |
| `description`  | str      | No       | Optional description of the job                          |
| `retry_delay`  | int      | No       | Seconds to wait before retrying a failed job (default: 0)|

### Job Function Requirements

The function referenced by a job must:

1. Accept the parameters defined in the `params` dictionary
2. Be importable from its module (for serialization purposes)
3. Return a JSON-serializable result (or None)

Example job function:

```python
def process_data(filename, threshold=0.5):
    """
    Process data from a file.

    Args:
        filename: Path to the file to process
        threshold: Processing threshold (default: 0.5)

    Returns:
        dict: Processing results
    """
    # Process the data...
    return {
        "processed": True,
        "records": 100,
        "errors": 0,
        "threshold_used": threshold
    }
```

## Job Identification

Each job is assigned a unique ID (UUID) when created. This ID is used to:

- Track the job in the queue
- Reference the job as a dependency for other jobs
- Query the job's status

```python
# Get the job ID
job_id = job.id

# Use the ID when submitting the job
queue = JobQueue("jobs.db")
submitted_id = queue.submit(job)  # This will be the same as job.id

# Reference the job as a dependency
dependent_job = Job(
    name="dependent_job",
    function=another_function,
    dependencies=[job.id]
)
```

## Job Priorities

Jobs with higher priority values are executed before jobs with lower priority values:

```python
# High priority job (will execute first)
high_priority_job = Job(
    name="urgent_task",
    function=urgent_function,
    priority=100
)

# Normal priority job
normal_job = Job(
    name="regular_task",
    function=regular_function,
    priority=0  # Default
)

# Low priority job (will execute last)
low_priority_job = Job(
    name="background_task",
    function=background_function,
    priority=-10
)
```

When multiple workers are processing jobs, they will preferentially select higher-priority jobs first.

## Job Timeouts

You can specify a timeout for jobs to prevent them from running indefinitely:

```python
# Job with a 10-minute timeout
job_with_timeout = Job(
    name="long_running_task",
    function=long_running_function,
    timeout=600  # 10 minutes in seconds
)
```

If a job exceeds its timeout:

- The job is marked as timed out
- The worker stops processing the job
- If `attempts < max_attempts`, the job is requeued for another attempt

## Job Retries

Jobs can be configured to retry automatically if they fail:

```python
# Job that will retry up to 5 times
job_with_retries = Job(
    name="retry_task",
    function=potentially_failing_function,
    max_attempts=5
)
```

When a job fails (raises an exception):

1. If `attempts < max_attempts`, the job is requeued with `status="pending"`
2. If `attempts >= max_attempts`, the job is marked as failed

### Retry Delay

By default, failed jobs become eligible for pickup immediately. For transient failures (API rate limits, temporary outages), use `retry_delay` to wait before retrying:

```python
# Wait 30 seconds between retries
job = Job(
    name="api_call",
    function=call_api,
    params={"url": "https://api.example.com/data"},
    max_attempts=3,
    retry_delay=30,
)
```

When this job fails, it waits 30 seconds before any worker can pick it up again. The delay applies to each retry. Set `retry_delay=0` (the default) to preserve the original immediate-retry behavior.

## Job Dependencies

Jobs can depend on other jobs, ensuring they only run after those dependencies have completed successfully:

```python
# Create a job
first_job = Job(name="first_step", function=step_one)

# Submit to get an ID
queue = JobQueue("jobs.db")
first_job_id = queue.submit(first_job)

# Create a dependent job
second_job = Job(
    name="second_step",
    function=step_two,
    dependencies=[first_job_id]
)

# Submit the dependent job
queue.submit(second_job)
```

For more complex dependency structures, see the [Workflows](workflows.md) documentation.

## Job Results and Error Handling

When a job completes:

- If successful, its result is stored in the database
- If it fails, the error message is stored

Job functions should handle their own exceptions when possible, but unhandled exceptions will be caught by the worker:

```python
def robust_job_function(input_data):
    try:
        # Process data...
        return {"status": "success", "result": processed_data}
    except ValueError as e:
        # Handle expected errors
        return {"status": "error", "message": str(e)}
    # Unhandled exceptions will be caught by GigQ
```

## Best Practices for Job Design

1. **Keep jobs atomic**: Each job should do one specific thing.

2. **Make jobs idempotent**: Jobs should be safe to run multiple times with the same input.

3. **Limit job interdependencies**: Minimize dependencies between jobs to improve parallelism.

4. **Use meaningful names**: Give jobs clear names that describe their purpose.

5. **Set appropriate timeouts**: Based on the expected runtime of the job.

6. **Validate inputs in job functions**: Detect invalid inputs early.

7. **Return structured results**: Results should provide useful information about what was accomplished.

8. **Record progress for long-running jobs**: For long tasks, consider updating external state to track progress.

## Example: Data Processing Job

Here's a complete example of defining a data processing job:

```python
import pandas as pd
from gigq import Job, JobQueue

def process_csv(input_file, output_file, drop_nulls=False, columns=None):
    """
    Process a CSV file and save the results.

    Args:
        input_file: Path to input CSV
        output_file: Path to save processed CSV
        drop_nulls: Whether to drop rows with null values
        columns: Specific columns to keep (None means all)

    Returns:
        dict: Processing statistics
    """
    # Read the data
    df = pd.read_csv(input_file)
    initial_rows = len(df)

    # Apply transformations
    if columns:
        df = df[columns]

    if drop_nulls:
        df = df.dropna()

    # Save the results
    df.to_csv(output_file, index=False)

    # Return statistics
    return {
        "input_file": input_file,
        "output_file": output_file,
        "initial_rows": initial_rows,
        "final_rows": len(df),
        "rows_dropped": initial_rows - len(df),
        "columns_kept": list(df.columns)
    }

# Create the job
csv_job = Job(
    name="process_monthly_data",
    function=process_csv,
    params={
        "input_file": "data/monthly/raw_202301.csv",
        "output_file": "data/monthly/processed_202301.csv",
        "drop_nulls": True,
        "columns": ["date", "value", "category"]
    },
    max_attempts=2,
    timeout=300,
    description="Process monthly data for January 2023"
)

# Submit the job
queue = JobQueue("data_processing.db")
job_id = queue.submit(csv_job)

print(f"Submitted job: {job_id}")
```

## Next Steps

Now that you understand how to define jobs, learn how to:

- [Manage jobs in the queue](job-queue.md)
- [Process jobs with workers](workers.md)
- [Create workflows with dependencies](workflows.md)
