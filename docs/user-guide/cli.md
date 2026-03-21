# Command Line Interface

GigQ provides a powerful command-line interface (CLI) that allows you to manage jobs and workers directly from your terminal. This guide covers all available commands and their options.

## Overview

The CLI is automatically installed when you install GigQ. You can access it using the `gigq` command:

```bash
gigq --help
```

This will display a list of available commands and general options.

## Global Options

These options can be used with any command:

| Option      | Description                                           |
| ----------- | ----------------------------------------------------- |
| `--db PATH` | Path to the SQLite database file (default: `gigq.db`) |
| `--help`    | Show help message and exit                            |

## Commands

### Submit a Job

Submit a new job to the queue:

```bash
gigq submit MODULE.FUNCTION [OPTIONS]
```

Where `MODULE.FUNCTION` is the fully qualified name of the function to execute (e.g., `my_package.my_module.my_function`).

#### Options

| Option                              | Description                                                          |
| ----------------------------------- | -------------------------------------------------------------------- |
| `--name NAME`                       | Name for the job (required)                                          |
| `--param KEY=VALUE`, `-p KEY=VALUE` | Parameters to pass to the function (can be specified multiple times) |
| `--priority INT`                    | Job priority (higher runs first, default: 0)                         |
| `--max-attempts INT`                | Maximum execution attempts (default: 3)                              |
| `--timeout INT`                     | Timeout in seconds (default: 300)                                    |
| `--description TEXT`                | Job description                                                      |
| `--retry-delay INT`                | Seconds to wait before retrying a failed job (default: 0)            |

#### Example

```bash
gigq submit my_module.process_data --name "Process CSV" \
    --param "filename=data.csv" --param "threshold=0.7" \
    --priority 10 --max-attempts 5 --timeout 600 \
    --description "Process the daily data CSV file"
```

### Check Job Status

Check the status of a specific job:

```bash
gigq status JOB_ID [OPTIONS]
```

#### Options

| Option              | Description            |
| ------------------- | ---------------------- |
| `--show-params`     | Show job parameters    |
| `--show-result`     | Show job result        |
| `--show-executions` | Show execution history |

#### Example

```bash
gigq status 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p --show-result
```

Example output:

```
Job: Process CSV (1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p)
Status: completed
Created: 2023-03-01 12:34:56
Updated: 2023-03-01 12:35:12
Started: 2023-03-01 12:35:01
Completed: 2023-03-01 12:35:12
Attempts: 1 / 3
Worker: worker-1234

Result:
  processed: True
  record_count: 1250
  errors: 0
```

### List Jobs

List jobs in the queue:

```bash
gigq list [OPTIONS]
```

#### Options

| Option            | Description                                                                |
| ----------------- | -------------------------------------------------------------------------- |
| `--status STATUS` | Filter by status (pending, running, completed, failed, cancelled, timeout) |
| `--limit INT`     | Maximum number of jobs to list (default: 100)                              |

#### Example

```bash
gigq list --status pending --limit 20
```

Example output:

```
ID                                   Name                 Status    Priority  Created              Updated
------------------------------------ -------------------- --------- --------- -------------------- --------------------
1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p Process CSV          pending   10        2023-03-01 12:34:56  2023-03-01 12:34:56
abcd1234-5e6f-7g8h-9i0j-1k2l3m4n5o6p Import Users         pending   5         2023-03-01 12:30:12  2023-03-01 12:30:12
```

### Cancel a Job

Cancel a pending job:

```bash
gigq cancel JOB_ID
```

#### Example

```bash
gigq cancel 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
```

### Requeue a Failed Job

Requeue a failed job:

```bash
gigq requeue JOB_ID
```

#### Example

```bash
gigq requeue 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
```

### Clear Completed Jobs

Clear completed jobs from the queue:

```bash
gigq clear [OPTIONS]
```

#### Options

| Option          | Description                               |
| --------------- | ----------------------------------------- |
| `--before DAYS` | Clear jobs completed more than N days ago |

#### Example

```bash
gigq clear --before 7  # Clear jobs completed more than 7 days ago
```

### Start a Worker

Start a worker process:

```bash
gigq worker [OPTIONS]
```

#### Options

| Option                   | Description                              |
| ------------------------ | ---------------------------------------- |
| `--worker-id ID`         | Worker ID (generated if not provided)    |
| `--polling-interval INT` | Polling interval in seconds (default: 5) |
| `--once`                 | Process one job and exit                 |

#### Example

```bash
gigq worker --polling-interval 2
```

To run a worker that processes just one job and exits:

```bash
gigq worker --once
```

## Using with Shell Scripts

You can easily integrate GigQ CLI commands into shell scripts:

```bash
#!/bin/bash

# Submit a job
JOB_ID=$(gigq submit my_module.process_data --name "Process Data" --param "filename=data.csv" | grep -oP 'Job submitted: \K.*')

echo "Submitted job: $JOB_ID"

# Wait for job to complete
while true; do
    STATUS=$(gigq status $JOB_ID | grep -oP 'Status: \K.*')
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
gigq status $JOB_ID --show-result
```

## Environment Variables

GigQ CLI respects the following environment variables:

| Variable                | Description                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------- |
| `GIGQ_DB`               | Default database path (overrides the default `gigq.db` but is overridden by `--db`) |
| `GIGQ_WORKER_ID`        | Default worker ID for the worker command                                            |
| `GIGQ_POLLING_INTERVAL` | Default polling interval for workers                                                |

Example:

```bash
export GIGQ_DB=/path/to/my/jobs.db
export GIGQ_POLLING_INTERVAL=2

# Now you don't need to specify --db in every command
gigq list
```

## Command Reference Summary

| Command   | Description               |
| --------- | ------------------------- |
| `submit`  | Submit a job to the queue |
| `status`  | Check job status          |
| `list`    | List jobs                 |
| `cancel`  | Cancel a pending job      |
| `requeue` | Requeue a failed job      |
| `clear`   | Clear completed jobs      |
| `worker`  | Start a worker process    |

## Next Steps

Now that you know how to use the CLI, you might want to explore:

- [Job Queue Management](job-queue.md) - Learn more about managing the job queue programmatically
- [Workers](workers.md) - Learn more about workers and how they process jobs
- [Error Handling](error-handling.md) - Learn how GigQ handles errors and how to customize error handling
