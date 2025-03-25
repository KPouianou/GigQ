# Workflows

Workflows in GigQ allow you to define and manage complex sequences of jobs with dependencies. This is useful for creating multi-step processes where some jobs depend on the successful completion of others.

## Basic Workflow Concepts

A workflow consists of:

- A collection of related jobs
- Dependency relationships between those jobs
- A mechanism for submitting all jobs to a queue

Jobs in a workflow are executed in an order that respects their dependencies, with independent jobs potentially running in parallel (if multiple workers are available).

## Creating a Workflow

To create a workflow:

```python
from gigq import Workflow

# Create a new workflow with a name
workflow = Workflow("data_processing_pipeline")
```

## Adding Jobs to a Workflow

You can add jobs to a workflow with or without dependencies:

```python
from gigq import Job

# Create some jobs
job1 = Job(
    name="download_data",
    function=download_data,
    params={"url": "https://example.com/data.csv"}
)

job2 = Job(
    name="process_data",
    function=process_data,
    params={"input_file": "data.csv", "output_file": "processed.csv"}
)

job3 = Job(
    name="analyze_data",
    function=analyze_data,
    params={"file": "processed.csv"}
)

# Add jobs to the workflow, defining dependencies
workflow.add_job(job1)  # No dependencies
workflow.add_job(job2, depends_on=[job1])  # Depends on job1
workflow.add_job(job3, depends_on=[job2])  # Depends on job2
```

## Multiple Dependencies

A job can depend on multiple other jobs:

```python
# Create more jobs
job4 = Job(
    name="generate_report",
    function=generate_report,
    params={"analysis_file": "analysis.json", "output_file": "report.pdf"}
)

job5 = Job(
    name="send_notification",
    function=send_notification,
    params={"report_file": "report.pdf", "recipients": ["user@example.com"]}
)

# Job4 depends on both job2 and job3
workflow.add_job(job4, depends_on=[job2, job3])

# Job5 depends on job4
workflow.add_job(job5, depends_on=[job4])
```

This would create a workflow like:

```mermaid
graph TD
    A[Download Data] --> B[Process Data]
    B --> C[Analyze Data]
    B --> D[Generate Report]
    C --> D
    D --> E[Send Notification]
```

## Submitting a Workflow

Once you've defined your workflow, you can submit all the jobs to a queue:

```python
from gigq import JobQueue

# Create a job queue
queue = JobQueue("workflow_jobs.db")

try:
    # Submit all jobs in the workflow
    job_ids = workflow.submit_all(queue)

    print(f"Submitted {len(job_ids)} jobs to the queue")
finally:
    # Always close connections when done
    queue.close()
```

This will submit all jobs to the queue with the appropriate dependencies. The workers will then process the jobs in the correct order.

## Advanced Workflow Patterns

### Fan-Out Pattern

The fan-out pattern involves a single job spawning multiple parallel jobs:

```python
# Main job that splits the work
split_job = Job(name="split_data", function=split_data)

# Worker jobs that process the splits in parallel
worker_jobs = []
for i in range(5):
    worker_job = Job(
        name=f"process_chunk_{i}",
        function=process_chunk,
        params={"chunk_id": i}
    )
    worker_jobs.append(worker_job)

# Add to workflow
workflow.add_job(split_job)
for job in worker_jobs:
    workflow.add_job(job, depends_on=[split_job])
```

### Fan-In Pattern

The fan-in pattern involves multiple parallel jobs converging to a single job:

```python
# Add a job that combines results from all worker jobs
combine_job = Job(name="combine_results", function=combine_results)
workflow.add_job(combine_job, depends_on=worker_jobs)
```

Together, the fan-out and fan-in patterns create a workflow like:

```mermaid
graph TD
    A[Split Data] --> B1[Process Chunk 0]
    A --> B2[Process Chunk 1]
    A --> B3[Process Chunk 2]
    A --> B4[Process Chunk 3]
    A --> B5[Process Chunk 4]
    B1 --> C[Combine Results]
    B2 --> C
    B3 --> C
    B4 --> C
    B5 --> C
```

### Dynamic Workflows

You can create workflows dynamically based on runtime conditions:

```python
from datetime import timedelta

def create_dynamic_workflow(data_source, date_range):
    """Create a workflow based on runtime parameters."""
    workflow = Workflow(f"process_{data_source}_{date_range[0]}_{date_range[1]}")

    # Initial setup job
    setup_job = Job(
        name="setup",
        function=setup_environment,
        params={"data_source": data_source}
    )
    workflow.add_job(setup_job)

    # Create a job for each date in the range
    date_jobs = []
    current_date = date_range[0]
    while current_date <= date_range[1]:
        date_str = current_date.strftime('%Y-%m-%d')
        job = Job(
            name=f"process_{date_str}",
            function=process_date,
            params={"date": date_str, "source": data_source}
        )
        workflow.add_job(job, depends_on=[setup_job])
        date_jobs.append(job)
        current_date += timedelta(days=1)

    # Final job to generate a report
    report_job = Job(
        name="generate_report",
        function=generate_report,
        params={"date_range": [date_range[0].strftime('%Y-%m-%d'),
                               date_range[1].strftime('%Y-%m-%d')]}
    )
    workflow.add_job(report_job, depends_on=date_jobs)

    return workflow
```

## Monitoring Workflow Progress

To monitor the progress of a workflow with proper connection management:

```python
def check_workflow_status(db_path, job_ids):
    """Check the status of all jobs in a workflow."""
    # Create a queue to access the database
    queue = JobQueue(db_path)

    try:
        statuses = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "timeout": 0
        }

        for job_id in job_ids:
            status = queue.get_status(job_id)
            statuses[status["status"]] += 1

        total = len(job_ids)
        completed_pct = (statuses["completed"] / total) * 100 if total > 0 else 0

        print(f"Workflow Progress: {completed_pct:.1f}% complete")
        print(f"Pending: {statuses['pending']}")
        print(f"Running: {statuses['running']}")
        print(f"Completed: {statuses['completed']}")
        print(f"Failed: {statuses['failed']}")
        print(f"Cancelled: {statuses['cancelled']}")
        print(f"Timeout: {statuses['timeout']}")

        return statuses
    finally:
        # Clean up connections
        queue.close()
```

## Thread-Safe Workflow Usage

Here's how to use workflows safely in a multi-threaded environment:

```python
import threading
from gigq import Workflow, Job, JobQueue, Worker, close_connections

def workflow_thread(db_path, data_source):
    """Process a workflow in a separate thread."""
    # Create queue for this thread
    queue = JobQueue(db_path)

    try:
        # Create a workflow
        workflow = Workflow(f"process_{data_source}")

        # Add jobs...

        # Submit workflow
        job_ids = workflow.submit_all(queue)

        # Optionally process jobs in the same thread
        worker = Worker(db_path)
        try:
            while True:
                if not worker.process_one():
                    break  # No more jobs to process
        finally:
            worker.close()
    finally:
        # Clean up connections
        queue.close()
        close_connections()

# Start workflows in separate threads
threads = []
for source in ["source1", "source2", "source3"]:
    thread = threading.Thread(target=workflow_thread, args=("workflows.db", source))
    thread.start()
    threads.append(thread)

# Wait for all threads to complete
for thread in threads:
    thread.join()
```

## Best Practices

When designing workflows, consider the following best practices:

1. **Keep jobs atomic**: Each job should perform a single, well-defined task.

2. **Set appropriate timeouts**: Ensure each job has a timeout appropriate for its expected runtime.

3. **Handle errors gracefully**: Jobs should handle exceptions internally when possible and return meaningful error information.

4. **Design for restartability**: If a workflow is interrupted, it should be able to resume from where it left off.

5. **Use meaningful job names**: Clear, descriptive names make it easier to monitor and debug workflows.

6. **Balance parallelism**: Consider the available resources when designing workflows with parallel execution.

7. **Pass minimal data between jobs**: Use file paths or database references rather than large data objects when passing information between jobs.

8. **Properly manage connections**: Always close database connections when you're done with them.

## Example: ETL Workflow

Here's a complete example of an ETL (Extract, Transform, Load) workflow with proper connection management:

```python
from datetime import datetime
from gigq import Job, JobQueue, Workflow, close_connections

# Define job functions
def extract_data(source_url, output_file):
    # Download data from source_url and save to output_file
    print(f"Extracting data from {source_url} to {output_file}")
    # ... extraction logic ...
    return {"rows_extracted": 1000, "file": output_file}

def transform_data(input_file, output_file):
    # Transform data from input_file and save to output_file
    print(f"Transforming data from {input_file} to {output_file}")
    # ... transformation logic ...
    return {"rows_transformed": 950, "file": output_file}

def load_data(input_file, database_connection):
    # Load data from input_file into database
    print(f"Loading data from {input_file} to {database_connection}")
    # ... loading logic ...
    return {"rows_loaded": 950}

def notify_completion(job_results, recipients):
    # Send notification of completion
    print(f"Sending notification to {recipients}")
    # ... notification logic ...
    return {"notifications_sent": len(recipients)}

def run_etl_workflow():
    # Create a workflow
    workflow = Workflow("daily_etl_job")

    # Create date-stamped filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = f"data/raw_{timestamp}.csv"
    transformed_file = f"data/transformed_{timestamp}.csv"

    # Create jobs
    extract_job = Job(
        name="extract",
        function=extract_data,
        params={
            "source_url": "https://example.com/api/data",
            "output_file": raw_file
        },
        timeout=300,  # 5 minutes
        max_attempts=3
    )

    transform_job = Job(
        name="transform",
        function=transform_data,
        params={
            "input_file": raw_file,
            "output_file": transformed_file
        },
        timeout=600,  # 10 minutes
        max_attempts=2
    )

    load_job = Job(
        name="load",
        function=load_data,
        params={
            "input_file": transformed_file,
            "database_connection": "postgresql://user:pass@localhost/db"
        },
        timeout=900,  # 15 minutes
        max_attempts=3
    )

    notify_job = Job(
        name="notify",
        function=notify_completion,
        params={
            "recipients": ["data-team@example.com"]
        },
        timeout=60,  # 1 minute
        max_attempts=5
    )

    # Add jobs to workflow with dependencies
    workflow.add_job(extract_job)
    workflow.add_job(transform_job, depends_on=[extract_job])
    workflow.add_job(load_job, depends_on=[transform_job])
    workflow.add_job(notify_job, depends_on=[load_job])

    # Create a job queue
    queue = JobQueue("etl_jobs.db")

    try:
        # Submit the workflow
        job_ids = workflow.submit_all(queue)
        print(f"Submitted ETL workflow with {len(job_ids)} jobs")
        return job_ids
    finally:
        # Always close connections
        queue.close()

if __name__ == "__main__":
    try:
        job_ids = run_etl_workflow()
        # Optionally start a worker to process the jobs
    finally:
        # Ensure all connections are closed
        close_connections()
```

## Next Steps

Now that you understand how to create and manage workflows, you may want to explore:

- [Error Handling](error-handling.md) - Learn more about how GigQ handles errors in jobs and workflows
- [CLI Usage](cli.md) - Using the command line interface to manage workflows
- [Database Utilities](../advanced/db_utils.md) - Learn about GigQ's thread-local connection management
- [Examples](../examples/github-archive.md) - See complete examples of workflows in action
