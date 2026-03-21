"""
GigQ MCP tool implementations (plain functions for testing and reuse).

GigQ is single-machine, synchronous Python only: workers run callables loaded by
import path; return values must be JSON-serializable in the DB.
"""

from __future__ import annotations

import importlib
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from gigq import Job, JobQueue, JobStatus, Workflow
from gigq.decorators import TaskWrapper


def resolve_db_path(db_path: str | None) -> str:
    """
    Resolve SQLite path: explicit tool arg > GIGQ_DB_PATH > ./gigq.db (absolute).
    """
    if db_path is not None and str(db_path).strip():
        return os.path.abspath(str(db_path))
    env = os.environ.get("GIGQ_DB_PATH")
    if env:
        return os.path.abspath(env)
    return os.path.abspath("gigq.db")


def worker_hint(db_path: str) -> Dict[str, Any]:
    """Reminder and exact CLI for agents when jobs are queued."""
    cmd = f"gigq --db {db_path} worker --concurrency 4"
    return {
        "worker_required": True,
        "worker_command_example": cmd,
        "worker_note": (
            "GigQ only stores jobs in SQLite until a worker process runs. "
            "If jobs stay pending, start a worker in a separate terminal using "
            "the command above (adjust --concurrency as needed). "
            "This MCP server does not start workers."
        ),
    }


def import_callable(function_path: str) -> Any:
    """
    Import a module-level callable: 'some.module.function_name'.

    Raises:
        ValueError: with an agent-oriented message if import or lookup fails.
    """
    if "." not in function_path:
        raise ValueError(
            "function_path must look like 'package.module.function_name' "
            "(got no dot-separated module path)."
        )
    module_path, name = function_path.rsplit(".", 1)
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise ValueError(
            f"Module {module_path!r} could not be imported — ensure it is on "
            f"PYTHONPATH, the environment is installed, and dependencies exist. "
            f"Import error: {e}"
        ) from e
    try:
        obj = getattr(mod, name)
    except AttributeError as e:
        raise ValueError(
            f"Callable {name!r} not found in module {module_path!r} — "
            f"check the function name and that it is defined at module level."
        ) from e
    if not callable(obj):
        raise ValueError(
            f"{function_path!r} resolves to {type(obj).__name__}, not a callable."
        )
    return obj


def import_task(function_path: str) -> TaskWrapper:
    """Import a @task-decorated function (TaskWrapper)."""
    obj = import_callable(function_path)
    if not isinstance(obj, TaskWrapper):
        raise ValueError(
            f"{function_path!r} is not a @task-decorated function (expected "
            f"gigq.decorators.TaskWrapper, got {type(obj).__name__}). "
            f"Use Workflow steps only with functions decorated with @task."
        )
    return obj


def topological_order_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order workflow steps so dependencies come first; detect cycles."""
    if not steps:
        raise ValueError("workflow requires at least one step")
    by_id = {s["id"]: s for s in steps}
    if len(by_id) != len(steps):
        raise ValueError("duplicate step id in workflow steps")

    ids = set(by_id.keys())
    for s in steps:
        for d in s.get("depends_on") or []:
            if d not in ids:
                raise ValueError(f"step {s['id']!r} depends_on unknown id {d!r}")

    in_degree: Dict[str, int] = {i: 0 for i in ids}
    children: Dict[str, List[str]] = defaultdict(list)
    for s in steps:
        sid = s["id"]
        for d in s.get("depends_on") or []:
            in_degree[sid] += 1
            children[d].append(sid)

    queue = [i for i in ids if in_degree[i] == 0]
    ordered: List[Dict[str, Any]] = []
    while queue:
        n = queue.pop(0)
        ordered.append(by_id[n])
        for c in children[n]:
            in_degree[c] -= 1
            if in_degree[c] == 0:
                queue.append(c)

    if len(ordered) != len(ids):
        raise ValueError("workflow dependency graph has a cycle")

    return ordered


def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, **data}


def _err(
    code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    if details:
        out["error"]["details"] = details
    return out


def submit_job(
    function_path: str,
    name: str,
    params: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    priority: int = 0,
    max_attempts: int = 3,
    timeout: int = 300,
    description: str = "",
    retry_delay: int = 0,
) -> Dict[str, Any]:
    """
    Submit a single job referencing a module-level callable by import path.

    The worker process imports ``function_path`` (``module.submodule.func``) and
    invokes it with ``params``. The callable must exist at module scope so workers
    can import it. Return values are stored as JSON; use JSON-serializable data.

    After submission, a GigQ worker must be running against the same database or
    the job will remain pending indefinitely.
    """
    path = resolve_db_path(db_path)
    try:
        fn = import_callable(function_path)
    except ValueError as e:
        return _err("import_error", str(e))

    job = Job(
        name=name,
        function=fn,
        params=dict(params or {}),
        priority=priority,
        max_attempts=max_attempts,
        timeout=timeout,
        description=description,
        retry_delay=retry_delay,
    )
    queue = JobQueue(path)
    try:
        job_id = queue.submit(job)
    finally:
        queue.close()

    return _ok(
        {
            "job_id": job_id,
            "db_path": path,
            **worker_hint(path),
        }
    )


def get_job_status(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return full job record from ``JobQueue.get_status`` (status, params, error, …)."""
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        status = queue.get_status(job_id)
    finally:
        queue.close()

    if not status.get("exists"):
        return _err("not_found", f"No job with id {job_id!r} in {path!r}.")
    return _ok({"status": status, "db_path": path})


def get_job_result(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Return the deserialized result for a completed job (``JobQueue.get_result``).

    If the job is not finished successfully, ``result`` is null and ``message``
    explains why (still running, failed, etc.).
    """
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        try:
            raw = queue.get_result(job_id)
        except KeyError:
            return _err("not_found", f"No job with id {job_id!r} in {path!r}.")
        st = queue.get_status(job_id)
    finally:
        queue.close()

    if st.get("status") != JobStatus.COMPLETED.value:
        return _ok(
            {
                "job_id": job_id,
                "result": None,
                "job_status": st.get("status"),
                "message": (
                    "Result is only available when status is 'completed'. "
                    f"Current status: {st.get('status')!r}."
                ),
                "db_path": path,
            }
        )

    return _ok({"job_id": job_id, "result": raw, "db_path": path})


def list_jobs(
    status_filter: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """List recent jobs, optionally filtered by status (pending, running, completed, …)."""
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        if status_filter:
            try:
                js = JobStatus(status_filter)
            except ValueError:
                valid = ", ".join(s.value for s in JobStatus)
                return _err(
                    "invalid_status",
                    f"Unknown status {status_filter!r}. Use one of: {valid}.",
                )
            rows = queue.list_jobs(status=js, limit=limit)
        else:
            rows = queue.list_jobs(limit=limit)
    finally:
        queue.close()

    return _ok({"jobs": rows, "count": len(rows), "db_path": path})


def queue_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Aggregate counts from ``JobQueue.stats``.

    When ``pending > 0`` and ``running == 0``, jobs are queued but no worker is
    executing them — usually because no worker is running (or workers are idle).
    """
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        stats = queue.stats()
    finally:
        queue.close()

    pending = stats.get("pending", 0)
    running = stats.get("running", 0)

    interpretation: Optional[str] = None
    if pending > 0 and running == 0:
        interpretation = (
            "There are pending jobs but none running — typically no GigQ worker is "
            "connected to this database, or workers are between poll cycles. "
            f"Start: {worker_hint(path)['worker_command_example']}"
        )
    elif pending > 0 and running > 0:
        interpretation = "Jobs are being processed (pending and running both non-zero)."
    elif pending == 0 and running > 0:
        interpretation = "No backlog: all jobs are either running or finished (workers are busy or finishing)."
    elif pending == 0 and running == 0:
        interpretation = "Queue has no pending or running work (idle or empty)."

    return _ok(
        {
            "stats": stats,
            "db_path": path,
            "interpretation": interpretation,
            "signals": {
                "pending_without_runner": pending > 0 and running == 0,
            },
            **worker_hint(path),
        }
    )


def cancel_job(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Cancel a pending job (``JobQueue.cancel``)."""
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        ok = queue.cancel(job_id)
    finally:
        queue.close()

    if not ok:
        return _err(
            "cancel_failed",
            f"Job {job_id!r} could not be cancelled (not pending or missing).",
            {"db_path": path},
        )
    return _ok({"job_id": job_id, "cancelled": True, "db_path": path})


def requeue_job(job_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Requeue a failed, timed-out, or cancelled job (``JobQueue.requeue_job``)."""
    path = resolve_db_path(db_path)
    queue = JobQueue(path)
    try:
        ok = queue.requeue_job(job_id)
    finally:
        queue.close()

    if not ok:
        return _err(
            "requeue_failed",
            f"Job {job_id!r} could not be requeued (must be failed, timeout, or "
            f"cancelled, and must exist).",
            {"db_path": path},
        )
    return _ok(
        {
            "job_id": job_id,
            "requeued": True,
            "db_path": path,
            **worker_hint(path),
        }
    )


def submit_workflow(
    name: str,
    steps: List[Dict[str, Any]],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit a DAG of @task jobs in one call (fan-out, fan-in, chains).

    Each ``steps`` item must include:

    - ``id``: unique string among steps (used in ``depends_on``).
    - ``function``: import path to a ``@task``-decorated function
      (``module.submodule.func``).
    - ``params`` (optional): keyword arguments for that task's ``to_job()`` call.
    - ``depends_on`` (optional): list of step ids that must finish first.
      Dependent tasks receive ``parent_results`` (parent job id → result) per GigQ
      rules unless ``pass_parent_results`` is set.

    - ``pass_parent_results`` (optional): ``true`` / ``false`` / omit for GigQ
      auto-detection.

    Functions must be importable on the worker environment. Results must be
    JSON-serializable. Topological order is computed automatically.
    """
    path = resolve_db_path(db_path)

    try:
        ordered = topological_order_steps(steps)
    except ValueError as e:
        return _err("invalid_workflow", str(e))

    wf = Workflow(name)
    step_to_job: Dict[str, Any] = {}

    try:
        for step in ordered:
            if not isinstance(step, dict):
                return _err(
                    "invalid_workflow",
                    "each step must be a JSON object with 'id' and 'function'.",
                )
            sid = step.get("id")
            fn_path = step.get("function")
            if not isinstance(sid, str) or not sid.strip():
                return _err(
                    "invalid_workflow",
                    "each step must have a non-empty string 'id'.",
                )
            if not isinstance(fn_path, str) or not fn_path.strip():
                return _err(
                    "invalid_workflow",
                    f"step {sid!r} must have a non-empty string 'function' (import path).",
                )
            try:
                tw = import_task(fn_path)
            except ValueError as e:
                return _err("import_error", str(e), {"step_id": sid})

            dep_ids = step.get("depends_on") or []
            dep_jobs = [step_to_job[d] for d in dep_ids]
            params = step.get("params")
            ppr = step.get("pass_parent_results")
            if ppr is not None and not isinstance(ppr, bool):
                return _err(
                    "invalid_pass_parent_results",
                    "pass_parent_results must be boolean or omitted.",
                    {"step_id": sid},
                )

            j = wf.add_task(
                tw,
                params=dict(params) if params else None,
                depends_on=dep_jobs or None,
                pass_parent_results=ppr,
            )
            step_to_job[sid] = j

        queue = JobQueue(path)
        try:
            job_ids = wf.submit_all(queue)
        finally:
            queue.close()
    except (TypeError, KeyError) as e:
        return _err("workflow_build_error", str(e))

    step_to_job_id = {s["id"]: step_to_job[s["id"]].id for s in steps}

    return _ok(
        {
            "workflow_name": name,
            "submitted_job_ids": job_ids,
            "step_id_to_job_id": step_to_job_id,
            "db_path": path,
            **worker_hint(path),
        }
    )
