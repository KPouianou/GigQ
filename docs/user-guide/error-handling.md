# Error Handling

Robust error handling is essential for any job processing system. This guide explains how GigQ handles errors, how to implement retry logic, and best practices for error recovery.

## How GigQ Handles Errors

When a job raises an exception during execution, GigQ follows these steps:

1. The exception is caught by the worker
2. The error details are logged
3. The job's attempt counter is incremented
4. If the job has not reached its maximum attempts, it's requeued as pending
5. If the job has reached its maximum attempts, it's marked as failed
6. The error message and traceback are stored in the job's record

This approach ensures that:

- Transient errors can be resolved through retries
- Permanent errors are properly recorded for diagnosis
- The system remains stable even when jobs fail

## Automatic Retry Mechanism

By default, GigQ will retry failed jobs automatically:

```python
from gigq import Job

# This job will be attempted up to 3 times (default)
job = Job(
    name="potentially_failing_job",
    function=risky_operation,
    params={"important": "data"}
)

# Customize retry attempts
job_with_more_retries = Job(
    name="important_job",
    function=critical_operation,
    params={"data": "valuable"},
    max_attempts=5  # Try up to 5 times
)

# Disable retries
job_without_retries = Job(
    name="one_shot_job",
    function=simple_operation,
    params={"quick": "task"},
    max_attempts=1  # Only try once
)
```

The `max_attempts` parameter determines how many times a job will be executed before it's considered permanently failed.

### Retry Delay

For transient failures (API rate limits, temporary outages), retrying immediately often fails again. Use `retry_delay` to add a waiting period between retries:

```python
from gigq import Job

# Wait 30 seconds between retries
job_with_delay = Job(
    name="rate_limited_job",
    function=call_api,
    params={"endpoint": "/data"},
    max_attempts=5,
    retry_delay=30,  # seconds to wait before retrying
)
```

When a job with `retry_delay` fails, it is set back to pending but won't be picked up by any worker until the delay has elapsed. This works at the queue level — no sleep or busy-wait in the worker.

The same option is available on the `@task` decorator:

```python
from gigq import task

@task(max_attempts=3, timeout=60, retry_delay=30)
def call_api(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()
```

And via the CLI:

```bash
gigq submit my_module.call_api --name "Fetch data" \
    --max-attempts 3 --retry-delay 30
```

## Handling Timeouts

Jobs that run for too long will be interrupted and potentially retried:

```python
# Job with a 5-minute timeout
job = Job(
    name="long_running_job",
    function=process_large_file,
    params={"file": "huge_dataset.csv"},
    timeout=300,  # 5 minutes in seconds
    max_attempts=2
)
```

When a job exceeds its timeout:

1. It's marked as timed out or requeued for retry
2. The worker moves on to the next job
3. A timeout error is recorded in the job's execution history

Timeouts are detected:

- By the worker processing the job (if it's still running)
- By any worker during its startup (if it finds abandoned jobs)

## Implementing Error Handling in Job Functions

While GigQ handles exceptions at the system level, it's often better to handle expected errors within your job functions:

```python
def robust_job_function(input_data):
    try:
        # Attempt to process the data
        result = process_data(input_data)
        return {"status": "success", "result": result}
    except ValueError as e:
        # Handle expected validation errors
        logger.warning(f"Validation error: {e}")
        return {"status": "error", "error_type": "validation", "message": str(e)}
    except IOError as e:
        # Handle I/O errors (might be transient)
        logger.error(f"I/O error: {e}")
        # Re-raise to trigger GigQ's retry mechanism
        raise
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error: {e}")
        # Re-raise to trigger GigQ's retry mechanism
        raise
```

This approach allows you to:

- Handle expected errors gracefully
- Return partial results or error information
- Let GigQ handle retries for transient errors
- Properly log all error information

## Manual Retry and Requeue

You can manually requeue failed jobs:

```python
from gigq import JobQueue

queue = JobQueue("jobs.db")

# Requeue a failed job
if queue.requeue_job(job_id):
    print(f"Job {job_id} requeued successfully")
else:
    print(f"Failed to requeue job {job_id}")
```

The `requeue_job` method:

- Resets the job's attempt counter to 0
- Sets the status back to "pending"
- Clears any error information
- Returns `True` if successful, `False` otherwise

## Job Dependencies and Error Propagation

When a job fails, its dependent jobs won't run:

```python
# Create a workflow with dependencies
workflow = Workflow("data_pipeline")

extract_job = Job(name="extract", function=extract_data)
transform_job = Job(name="transform", function=transform_data)
load_job = Job(name="load", function=load_data)

workflow.add_job(extract_job)
workflow.add_job(transform_job, depends_on=[extract_job])
workflow.add_job(load_job, depends_on=[transform_job])

# Submit the workflow
workflow.submit_all(queue)
```

If `extract_job` fails:

- `transform_job` won't run because its dependency failed
- `load_job` won't run because its dependency won't run

This prevents cascading failures and ensures data integrity.

## Handling Different Types of Errors

Different errors may require different handling strategies:

### Transient Errors

Transient errors like network timeouts or temporary service unavailability can often be resolved by simply retrying:

```python
def fetch_remote_data(url):
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            raise  # Re-raise after all retries failed
```

### Permanent Errors

Permanent errors like invalid input data should be handled definitively:

```python
def process_data(data):
    # Validate input
    if not validate_input(data):
        # Return a result indicating validation failure
        return {
            "success": False,
            "error": "Input validation failed",
            "details": get_validation_errors(data)
        }

    # Process the valid data
    result = perform_processing(data)

    return {
        "success": True,
        "result": result
    }
```

### Catastrophic Errors

For truly catastrophic errors that might affect system stability:

```python
def risky_operation():
    try:
        # Attempt the operation
        result = perform_risky_operation()
        return result
    except Exception as e:
        # Log detailed error information
        logger.critical(f"Catastrophic error: {e}", exc_info=True)

        # Notify administrators
        send_alert("Catastrophic job failure", str(e))

        # Raise to mark the job as failed
        raise
```

## Logging and Monitoring

Effective error handling relies on good logging and monitoring:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gigq.log'
)
logger = logging.getLogger('gigq.jobs')

def job_function_with_logging(param1, param2):
    logger.info(f"Starting job with params: {param1}, {param2}")

    try:
        # Perform the job
        result = perform_operation(param1, param2)
        logger.info(f"Job completed successfully: {result}")
        return result
    except Exception as e:
        logger.exception(f"Job failed: {e}")
        raise
```

## Creating a Custom Error Handler

You can create a custom error handler to centralize your error handling logic:

```python
class JobErrorHandler:
    def __init__(self, queue, notification_service=None):
        self.queue = queue
        self.notification_service = notification_service
        self.logger = logging.getLogger('gigq.error_handler')

    def handle_failed_jobs(self):
        """Check for failed jobs and handle them."""
        failed_jobs = self.queue.list_jobs(status="failed")

        for job in failed_jobs:
            # Analyze the error
            error_message = job.get('error', '')

            # Handle based on error type
            if 'connection refused' in error_message.lower():
                # Network issue - requeue
                self.logger.info(f"Requeuing job {job['id']} due to connection error")
                self.queue.requeue_job(job['id'])

            elif 'validation error' in error_message.lower():
                # Data validation issue - notify but don't retry
                self.logger.warning(f"Job {job['id']} failed validation: {error_message}")
                if self.notification_service:
                    self.notification_service.send_alert(
                        f"Job {job['name']} failed validation",
                        f"Error: {error_message}\nJob ID: {job['id']}"
                    )

            else:
                # Unknown error - notify
                self.logger.error(f"Unhandled job failure: {job['id']} - {error_message}")
                if self.notification_service:
                    self.notification_service.send_alert(
                        f"Unhandled job failure: {job['name']}",
                        f"Error: {error_message}\nJob ID: {job['id']}"
                    )

# Usage
error_handler = JobErrorHandler(queue, notification_service=email_service)
error_handler.handle_failed_jobs()
```

## Best Practices for Error Handling

1. **Set appropriate `max_attempts`** based on the nature of the job and expected transient failures.

2. **Use appropriate timeouts** to prevent jobs from running indefinitely.

3. **Handle expected errors** within job functions when possible.

4. **Implement exponential backoff** for retrying operations with external dependencies.

5. **Include context in error messages** to aid in debugging.

6. **Log generously** but appropriately based on error severity.

7. **Design for idempotency** so that jobs can be safely retried.

8. **Return structured results** that include success/failure status and error details.

9. **Implement monitoring** to detect patterns of failures.

10. **Consider dependencies** when designing error handling strategies. Jobs with many dependents may need more aggressive retry logic.

## Example: Robust Data Import Job

Here's a complete example of a robust data import job with comprehensive error handling:

```python
import logging
import time
import requests
from gigq import Job, JobQueue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('data_import')

def import_data_from_api(api_url, target_file, api_key=None, max_retries=3, retry_delay=5):
    """
    Import data from an API and save to a file.

    Args:
        api_url: URL of the API endpoint
        target_file: Path to save the imported data
        api_key: Optional API key for authentication
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Base delay between retries (in seconds)

    Returns:
        dict: Result information including success status and error details if any
    """
    logger.info(f"Starting data import from {api_url} to {target_file}")

    headers = {}
    if api_key:
        headers['Authorization'] = f"Bearer {api_key}"

    # Track attempt number for internal retries
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"API request attempt {attempt}/{max_retries}")

            # Make the API request
            response = requests.get(api_url, headers=headers, timeout=30)

            # Check for HTTP errors
            if response.status_code == 429:  # Too Many Requests
                wait_time = int(response.headers.get('Retry-After', retry_delay * attempt))
                logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry.")
                time.sleep(wait_time)
                continue

            elif response.status_code == 401 or response.status_code == 403:
                return {
                    "success": False,
                    "error": "API authentication failed",
                    "status_code": response.status_code,
                    "details": response.text
                }

            elif response.status_code >= 400:
                # Server error (possibly transient)
                if attempt < max_retries and response.status_code >= 500:
                    wait_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(f"Server error: {response.status_code}. Retrying in {wait_time} seconds.")
                    time.sleep(wait_time)
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"API request failed with status {response.status_code}",
                        "status_code": response.status_code,
                        "details": response.text
                    }

            # Parse the data
            try:
                data = response.json()
            except ValueError:
                return {
                    "success": False,
                    "error": "Failed to parse API response as JSON",
                    "details": response.text[:1000]  # Include the start of the response
                }

            # Validate the data structure
            if not isinstance(data, list) or len(data) == 0:
                return {
                    "success": False,
                    "error": "API returned invalid or empty data structure",
                    "details": str(data)[:1000]  # Include the start of the data
                }

            # Write the data to the file
            try:
                with open(target_file, 'w') as f:
                    import json
                    json.dump(data, f, indent=2)
            except IOError as e:
                return {
                    "success": False,
                    "error": f"Failed to write data to file: {str(e)}",
                    "file": target_file
                }

            # Success
            logger.info(f"Successfully imported {len(data)} records to {target_file}")
            return {
                "success": True,
                "records_imported": len(data),
                "file": target_file
            }

        except requests.Timeout:
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(f"Request timed out. Retrying in {wait_time} seconds.")
                time.sleep(wait_time)
            else:
                return {
                    "success": False,
                    "error": "API request timed out after multiple attempts",
                    "attempts": attempt
                }

        except requests.ConnectionError as e:
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(f"Connection error: {e}. Retrying in {wait_time} seconds.")
                time.sleep(wait_time)
            else:
                return {
                    "success": False,
                    "error": f"Failed to connect to API after {max_retries} attempts",
                    "details": str(e)
                }

        except Exception as e:
            logger.exception(f"Unexpected error during import")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "exception_type": type(e).__name__
            }

    # Should never reach here, but just in case
    return {
        "success": False,
        "error": "Maximum retry attempts exceeded"
    }

# Usage example
if __name__ == "__main__":
    # Create a job to import data
    import_job = Job(
        name="daily_data_import",
        function=import_data_from_api,
        params={
            "api_url": "https://api.example.com/data",
            "target_file": "data/daily_import.json",
            "api_key": "secret_key",
            "max_retries": 3,
            "retry_delay": 5
        },
        max_attempts=2,  # GigQ-level retries (on top of function-level retries)
        timeout=300,  # 5 minutes
        description="Import daily data from the Example API"
    )

    # Submit the job
    queue = JobQueue("import_jobs.db")
    job_id = queue.submit(import_job)

    print(f"Submitted import job with ID: {job_id}")
```

## Next Steps

Now that you understand how GigQ handles errors, you may want to explore:

- [Job Queue Management](job-queue.md) - Learn more about managing and monitoring jobs
- [Workers](workers.md) - Understand how workers process jobs and handle failures
- [Workflows](workflows.md) - Learn how to create complex workflows with error handling
- [Advanced Concurrency](../advanced/concurrency.md) - Understand how GigQ handles concurrent job processing
