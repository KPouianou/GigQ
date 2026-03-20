"""
GigQ MCP server (stdio transport by default).

Database path: set ``GIGQ_DB_PATH`` or pass ``db_path`` on each tool (absolute
paths recommended in multi-project setups).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from gigq_mcp import handlers

INSTRUCTIONS = (
    "GigQ MCP: submit and monitor SQLite-backed jobs and workflows. "
    "Jobs run only when a separate GigQ worker process uses the same database. "
    "Target functions must be importable module-level callables; workflow steps "
    "must use @task-decorated functions. Single-machine, synchronous Python; "
    "results must be JSON-serializable."
)

mcp = FastMCP(
    "GigQ",
    instructions=INSTRUCTIONS,
)


@mcp.tool()
def gigq_submit_job(
    function_path: str,
    name: str,
    params: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    priority: int = 0,
    max_attempts: int = 3,
    timeout: int = 300,
    description: str = "",
) -> Dict[str, Any]:
    """Enqueue a single GigQ job.

    ``function_path`` must be importable as ``module.submodule.callable_name`` with
    the callable defined at **module level** (workers dynamic-import it). Pass
    keyword arguments via ``params``; return values must be JSON-serializable in
    SQLite. GigQ is single-machine and synchronous only.

    On success, the response includes ``job_id``, ``db_path``, ``worker_note``, and
    ``worker_command_example`` (e.g. ``gigq --db <path> worker --concurrency 4``).
    Nothing executes until a worker runs against that database—if jobs stay
    pending, start a worker or check ``gigq_queue_stats``.
    """
    return handlers.submit_job(
        function_path=function_path,
        name=name,
        params=params,
        db_path=db_path,
        priority=priority,
        max_attempts=max_attempts,
        timeout=timeout,
        description=description,
    )


@mcp.tool()
def gigq_get_job_status(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return the full job record from ``JobQueue.get_status`` (status, params, error, executions, …).

    ``success`` is false if the id does not exist in the database.
    """
    return handlers.get_job_status(job_id, db_path=db_path)


@mcp.tool()
def gigq_get_job_result(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return the deserialized job return value (``JobQueue.get_result``).

    If the job is missing, ``success`` is false. If the job exists but is not
    ``completed``, ``result`` is null and ``message`` explains the current status.
    """
    return handlers.get_job_result(job_id, db_path=db_path)


@mcp.tool()
def gigq_list_jobs(
    status_filter: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """List jobs newest-first (up to ``limit``).

    ``status_filter`` is optional: one of pending, running, completed, failed,
    cancelled, timeout. Invalid values return ``success`` false with code
    ``invalid_status``.
    """
    return handlers.list_jobs(status_filter=status_filter, limit=limit, db_path=db_path)


@mcp.tool()
def gigq_queue_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate job counts per status (``JobQueue.stats``).

    Includes ``signals.pending_without_runner`` (true when pending>0 and
    running=0) and ``interpretation`` text so you can tell that work is queued
    but no worker is processing it. Also repeats worker reminder fields.
    """
    return handlers.queue_stats(db_path=db_path)


@mcp.tool()
def gigq_cancel_job(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Cancel a job that is still **pending** (``JobQueue.cancel``).

    Running or finished jobs cannot be cancelled this way; ``success`` is false
    with ``cancel_failed`` if the job was not pending.
    """
    return handlers.cancel_job(job_id, db_path=db_path)


@mcp.tool()
def gigq_requeue_job(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Requeue a failed, timed-out, or cancelled job (``JobQueue.requeue_job``).

    Resets attempts and clears error; the job becomes pending again. Requires a
    worker to run. On failure, ``success`` is false with ``requeue_failed``.
    """
    return handlers.requeue_job(job_id, db_path=db_path)


@mcp.tool()
def gigq_submit_workflow(
    name: str,
    steps: List[Dict[str, Any]],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit many ``@task`` jobs as one workflow (``Workflow`` + ``submit_all``).

    Each element of ``steps`` must include: ``id`` (unique string),
    ``function`` (import path to a **@task-decorated** function), optional
    ``params`` (kwargs for ``to_job()``), optional ``depends_on`` (list of step
    ids to wait on—use for fan-in or sequential chains), optional
    ``pass_parent_results`` (bool or omit for GigQ auto-detection). Dependent
    tasks receive ``parent_results`` (parent job id → result) per GigQ.

    Steps may be listed in any order; dependencies are ordered topologically.
    Fan-out: multiple steps with no ``depends_on``; fan-in: one step whose
    ``depends_on`` lists all parents. Returns ``submitted_job_ids``,
    ``step_id_to_job_id``, and worker reminder fields.

    Import errors return ``success`` false with ``import_error`` and ``step_id``.
    """
    return handlers.submit_workflow(name, steps, db_path=db_path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
