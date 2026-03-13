"""
GigQ CLI Interface

This is a replacement for the existing gigq/cli.py file.
The key change is replacing the tabulate dependency with our custom table_formatter.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

from gigq import JobQueue, Worker, JobStatus
from gigq.table_formatter import format_table


def format_time(timestamp):
    """Format a timestamp for display."""
    if not timestamp:
        return "-"
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp


def cmd_submit(args):
    """Submit a job to the queue."""
    queue = JobQueue(args.db)

    # Import the function
    module_path, function_name = args.function.rsplit(".", 1)
    try:
        __import__(module_path)
        module = sys.modules[module_path]
        function = getattr(module, function_name)
    except (ImportError, AttributeError) as e:
        print(f"Error: Could not import {args.function}")
        print(str(e))
        return 1

    # Parse parameters
    params = {}
    if args.param:
        for param in args.param:
            key, value = param.split("=", 1)
            try:
                # Try to parse as JSON
                value = json.loads(value)
            except json.JSONDecodeError:
                # If not valid JSON, use as string
                pass
            params[key] = value

    # Create job
    from gigq import Job

    job = Job(
        name=args.name,
        function=function,
        params=params,
        priority=args.priority,
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        description=args.description,
    )

    # Submit the job
    job_id = queue.submit(job)
    print(f"Job submitted: {job_id}")
    return 0


def cmd_status(args):
    """Check the status of a job."""
    queue = JobQueue(args.db)
    status = queue.get_status(args.job_id)

    if not status.get("exists", False):
        print(f"Job {args.job_id} not found.")
        return 1

    print(f"Job: {status['name']} ({status['id']})")
    print(f"Status: {status['status']}")
    print(f"Created: {format_time(status['created_at'])}")
    print(f"Updated: {format_time(status['updated_at'])}")
    print(f"Started: {format_time(status.get('started_at'))}")
    print(f"Completed: {format_time(status.get('completed_at'))}")
    print(f"Attempts: {status['attempts']} / {status['max_attempts']}")

    if status.get("worker_id"):
        print(f"Worker: {status['worker_id']}")

    if status.get("error"):
        print(f"Error: {status['error']}")

    if args.show_params and status.get("params"):
        print("\nParameters:")
        for key, value in status["params"].items():
            print(f"  {key}: {value}")

    if args.show_result and status.get("result"):
        print("\nResult:")
        if isinstance(status["result"], dict):
            for key, value in status["result"].items():
                print(f"  {key}: {value}")
        else:
            print(f"  {status['result']}")

    if args.show_executions and status.get("executions"):
        print("\nExecutions:")
        headers = ["ID", "Started", "Completed", "Status"]
        rows = []
        for execution in status["executions"]:
            rows.append(
                [
                    execution["id"],
                    format_time(execution["started_at"]),
                    format_time(execution.get("completed_at")),
                    execution["status"],
                ]
            )
        print(format_table(rows, headers=headers))

    return 0


def cmd_list(args):
    """List jobs in the queue."""
    queue = JobQueue(args.db)

    status = None
    if args.status:
        try:
            status = JobStatus(args.status)
        except ValueError:
            print(f"Error: Invalid status '{args.status}'")
            print(f"Valid statuses: {', '.join([s.value for s in JobStatus])}")
            return 1

    jobs = queue.list_jobs(status=status, limit=args.limit)

    if not jobs:
        print("No jobs found.")
        return 0

    headers = ["ID", "Name", "Status", "Priority", "Created", "Updated"]
    rows = []

    for job in jobs:
        rows.append(
            [
                job["id"],
                job["name"],
                job["status"],
                job["priority"],
                format_time(job["created_at"]),
                format_time(job["updated_at"]),
            ]
        )

    print(format_table(rows, headers=headers))
    return 0


def cmd_cancel(args):
    """Cancel a pending job."""
    queue = JobQueue(args.db)

    if queue.cancel(args.job_id):
        print(f"Job {args.job_id} cancelled.")
        return 0
    else:
        print(f"Could not cancel job {args.job_id}. It might not be in pending state.")
        return 1


def cmd_requeue(args):
    """Requeue a failed job."""
    queue = JobQueue(args.db)

    if queue.requeue_job(args.job_id):
        print(f"Job {args.job_id} requeued.")
        return 0
    else:
        print(
            f"Could not requeue job {args.job_id}. It might not be in a failed state."
        )
        return 1


def cmd_clear(args):
    """Clear completed jobs."""
    queue = JobQueue(args.db)

    before = None
    if args.before:
        try:
            before_dt = datetime.now() - timedelta(days=args.before)
            before = before_dt.isoformat()
        except ValueError:
            print(f"Error: Invalid value for --before")
            return 1

    count = queue.clear_completed(before_timestamp=before)
    print(f"Cleared {count} completed jobs.")
    return 0


def cmd_stats(args):
    """Show aggregate job statistics."""
    queue = JobQueue(args.db)
    stats = queue.stats()

    headers = ["Status", "Count"]
    rows = []

    # Ensure a stable, user-friendly order using the JobStatus enum
    for status in JobStatus:
        rows.append([status.value, stats.get(status.value, 0)])

    # Add total as a separate row
    rows.append(["total", stats.get("total", 0)])

    print(format_table(rows, headers=headers))
    return 0


def cmd_worker(args):
    """Start a worker process."""
    worker = Worker(
        args.db, worker_id=args.worker_id, polling_interval=args.polling_interval
    )

    if args.once:
        # Process just one job and exit
        if worker.process_one():
            print("Processed one job.")
            return 0
        else:
            print("No jobs available to process.")
            return 0

    print(f"Starting worker {worker.worker_id}...")
    try:
        worker.start()
    except KeyboardInterrupt:
        print("Worker stopped by user.")

    return 0


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="GigQ: Lightweight SQLite-backed job queue"
    )
    parser.add_argument("--db", default="gigq.db", help="Path to SQLite database file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a job to the queue")
    submit_parser.add_argument("function", help="Function to execute (module.function)")
    submit_parser.add_argument("--name", required=True, help="Name for the job")
    submit_parser.add_argument(
        "--param", "-p", action="append", help="Parameters as key=value"
    )
    submit_parser.add_argument(
        "--priority", type=int, default=0, help="Job priority (higher runs first)"
    )
    submit_parser.add_argument(
        "--max-attempts", type=int, default=3, help="Maximum execution attempts"
    )
    submit_parser.add_argument(
        "--timeout", type=int, default=300, help="Timeout in seconds"
    )
    submit_parser.add_argument("--description", help="Job description")
    submit_parser.set_defaults(func=cmd_submit)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check job status")
    status_parser.add_argument("job_id", help="Job ID to check")
    status_parser.add_argument(
        "--show-params", action="store_true", help="Show job parameters"
    )
    status_parser.add_argument(
        "--show-result", action="store_true", help="Show job result"
    )
    status_parser.add_argument(
        "--show-executions", action="store_true", help="Show execution history"
    )
    status_parser.set_defaults(func=cmd_status)

    # List command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument(
        "--limit", type=int, default=100, help="Maximum number of jobs to list"
    )
    list_parser.set_defaults(func=cmd_list)

    # Cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a pending job")
    cancel_parser.add_argument("job_id", help="Job ID to cancel")
    cancel_parser.set_defaults(func=cmd_cancel)

    # Requeue command
    requeue_parser = subparsers.add_parser("requeue", help="Requeue a failed job")
    requeue_parser.add_argument("job_id", help="Job ID to requeue")
    requeue_parser.set_defaults(func=cmd_requeue)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear completed jobs")
    clear_parser.add_argument(
        "--before", type=int, help="Clear jobs completed more than N days ago"
    )
    clear_parser.set_defaults(func=cmd_clear)

    # Worker command
    worker_parser = subparsers.add_parser("worker", help="Start a worker process")
    worker_parser.add_argument(
        "--worker-id", help="Worker ID (generated if not provided)"
    )
    worker_parser.add_argument(
        "--polling-interval", type=int, default=5, help="Polling interval in seconds"
    )
    worker_parser.add_argument(
        "--once", action="store_true", help="Process one job and exit"
    )
    worker_parser.set_defaults(func=cmd_worker)

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Show aggregate job statistics"
    )
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
