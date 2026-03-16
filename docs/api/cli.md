# CLI API Reference

This page documents the Command Line Interface (CLI) API for GigQ. The CLI is implemented in the `cli.py` module and is automatically installed as the `gigq` command when you install the package.

## Overview

The GigQ CLI provides a command-line interface for interacting with job queues, submitting jobs, and managing workers. It's designed to be used both interactively and in scripts.

## Main Entry Point

```python
def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="GigQ: Lightweight SQLite-backed job queue")
    parser.add_argument("--db", default="gigq.db", help="Path to SQLite database file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    # Add subcommands...

    args = parser.parse_args()
    return args.func(args)
```

This is the main entry point for the CLI, which sets up the argument parser and dispatches to the appropriate command function.

## Commands

The CLI supports the following commands:

### submit

```python
def cmd_submit(args):
    """Submit a job to the queue."""
```

Submits a job to the queue.

#### Arguments

- `function`: The function to execute (in module.function format)
- `--name`: Name for the job (required)
- `--param`, `-p`: Parameters as key=value (can be specified multiple times)
- `--priority`: Job priority (higher runs first, default: 0)
- `--max-attempts`: Maximum execution attempts (default: 3)
- `--timeout`: Timeout in seconds (default: 300)
- `--description`: Job description

#### Example

```bash
gigq --db jobs.db submit my_module.process_data --name "Process CSV" \
    --param "filename=data.csv" --param "threshold=0.7" \
    --priority 10 --max-attempts 5 --timeout 600 \
    --description "Process the daily data CSV file"
```

#### Implementation Details

The `submit` command:

1. Imports the specified function from its module
2. Parses parameters from the command line
3. Creates a `Job` object
4. Submits the job to the queue
5. Prints the job ID

### status

```python
def cmd_status(args):
    """Check the status of a job."""
```

Checks the status of a specific job.

#### Arguments

- `job_id`: Job ID to check
- `--show-params`: Show job parameters
- `--show-result`: Show job result
- `--show-executions`: Show execution history

#### Example

```bash
gigq --db jobs.db status 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p --show-result
```

#### Implementation Details

The `status` command:

1. Gets the job status from the queue
2. Prints job details (ID, name, status, timestamps, etc.)
3. Optionally prints parameters, result, and execution history

### list

```python
def cmd_list(args):
    """List jobs in the queue."""
```

Lists jobs in the queue.

#### Arguments

- `--status`: Filter by status
- `--limit`: Maximum number of jobs to list (default: 100)

#### Example

```bash
gigq --db jobs.db list --status pending --limit 20
```

#### Implementation Details

The `list` command:

1. Gets a list of jobs from the queue, optionally filtered by status
2. Formats and prints the jobs in a table using the built-in `table_formatter`

### stats

```python
def cmd_stats(args):
    """Show aggregate job statistics."""
```

Shows aggregate statistics about jobs in the queue.

#### Arguments

This command uses the global `--db` option to select the SQLite database, just like the other commands.

#### Example

```bash
gigq --db jobs.db stats
```

#### Implementation Details

The `stats` command:

1. Calls `JobQueue.stats()` to retrieve counts of jobs by status
2. Ensures all statuses from `JobStatus` are present in the output (with `0` if missing)
3. Adds a `total` row with the sum of all jobs
4. Formats and prints the statistics in a table using the same `table_formatter` as other commands

### cancel

```python
def cmd_cancel(args):
    """Cancel a pending job."""
```

Cancels a pending job.

#### Arguments

- `job_id`: Job ID to cancel

#### Example

```bash
gigq --db jobs.db cancel 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
```

#### Implementation Details

The `cancel` command:

1. Attempts to cancel the specified job
2. Prints whether the cancellation was successful

### requeue

```python
def cmd_requeue(args):
    """Requeue a failed job."""
```

Requeues a failed job.

#### Arguments

- `job_id`: Job ID to requeue

#### Example

```bash
gigq --db jobs.db requeue 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
```

#### Implementation Details

The `requeue` command:

1. Attempts to requeue the specified job
2. Prints whether the requeue was successful

### clear

```python
def cmd_clear(args):
    """Clear completed jobs."""
```

Clears completed jobs from the queue.

#### Arguments

- `--before`: Clear jobs completed more than N days ago

#### Example

```bash
gigq --db jobs.db clear --before 7
```

#### Implementation Details

The `clear` command:

1. Calculates the cutoff timestamp (if `--before` is specified)
2. Clears completed jobs from the queue
3. Prints the number of jobs cleared

### worker

```python
def cmd_worker(args):
    """Start a worker process."""
```

Starts a worker process.

#### Arguments

- `--worker-id`: Worker ID (generated if not provided)
- `--polling-interval`: Polling interval in seconds (default: 5)
- `--once`: Process one job and exit
- `--concurrency`: Number of concurrent job-processing threads (default: 1)

#### Example

```bash
gigq --db jobs.db worker --polling-interval 2

# Process up to 8 jobs concurrently
gigq --db jobs.db worker --concurrency 8
```

#### Implementation Details

The `worker` command:

1. Creates a worker with the specified parameters
2. If `--once` is specified, processes a single job and exits
3. Otherwise, starts the worker and keeps it running until interrupted

## Helper Functions

The CLI module includes several helper functions:

### format_time

```python
def format_time(timestamp):
    """Format a timestamp for display."""
```

Formats an ISO timestamp for display.

#### Parameters

- `timestamp`: ISO format timestamp

#### Returns

Formatted timestamp string (YYYY-MM-DD HH:MM:SS)

## Using the CLI in Scripts

The GigQ CLI can be used in shell scripts to automate job management. Here's an example:

```bash
#!/bin/bash

# Submit a job
JOB_ID=$(gigq --db jobs.db submit my_module.process_data --name "Process Data" \
    --param "filename=data.csv" | grep -oP 'Job submitted: \K.*')

echo "Submitted job: $JOB_ID"

# Wait for job to complete
while true; do
    STATUS=$(gigq --db jobs.db status $JOB_ID | grep -oP 'Status: \K.*')
    echo "Job status: $STATUS"

    if [[ "$STATUS" == "completed" ]]; then
        echo "Job completed successfully!"
        break
    elif [[ "$STATUS" == "failed" || "$STATUS" == "timeout" || "$STATUS" == "cancelled" ]]; then
        echo "Job failed!"
        exit 1
    fi

    sleep 5
done

# Get the result
gigq --db jobs.db status $JOB_ID --show-result
```

## Extending the CLI

You can extend the GigQ CLI by adding new commands. Here's an example of adding a custom command:

```python
# In your own module
import argparse
from gigq import JobQueue

def cmd_monthly_report(args):
    """Generate a monthly report of job statistics."""
    queue = JobQueue(args.db)

    # Your command implementation
    # ...

    return 0

def add_to_cli():
    """Add custom commands to the GigQ CLI."""
    # This function would be called from your application's entry point
    from gigq.cli import main_parser

    # Add your command to the parser
    report_parser = main_parser.add_parser("monthly-report", help="Generate monthly job statistics")
    report_parser.add_argument("--month", help="Month (YYYY-MM format)")
    report_parser.set_defaults(func=cmd_monthly_report)
```

## Environment Variables

The GigQ CLI respects the following environment variables:

- `GIGQ_DB`: Default database path
- `GIGQ_WORKER_ID`: Default worker ID
- `GIGQ_POLLING_INTERVAL`: Default polling interval

Example:

```bash
export GIGQ_DB=/path/to/jobs.db
gigq list  # Will use /path/to/jobs.db
```

## Exit Codes

The GigQ CLI returns the following exit codes:

- `0`: Success
- `1`: Error (e.g., job not found, failed to submit, etc.)

## Source Code

The full implementation of the CLI can be found in the `gigq/cli.py` file in the GigQ repository.

## See Also

- [CLI User Guide](../user-guide/cli.md) - More detailed information on using the CLI
- [Core API Reference](core.md) - Documentation for the core GigQ classes and functions
