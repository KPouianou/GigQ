"""
Data Pipeline — sequential GigQ workflow.

Unlike parallel_tasks.py (many parents → one child), this is a linear chain:
generate → transform → format. Each step after the first reads the previous
step's return value through parent_results.

Usage:
    python examples/data_pipeline.py
"""

import os
import tempfile
import threading
import time

from gigq import JobQueue, Worker, Workflow, task


@task(timeout=30)
def generate(count=6):
    nums = list(range(1, count + 1))
    print(f"  [generate] produced {nums}")
    return {"numbers": nums, "count": len(nums)}


@task(timeout=30)
def transform(parent_results):
    prev = next(iter(parent_results.values()))
    nums = prev["numbers"]
    evens = [n for n in nums if n % 2 == 0]
    out = {"evens": evens, "sum_evens": sum(evens)}
    print(f"  [transform] received {nums!r} → evens {evens!r}, sum={out['sum_evens']}")
    return out


@task(timeout=30)
def format_summary(parent_results):
    prev = next(iter(parent_results.values()))
    text = (
        f"Pipeline: dropped odds, kept {prev['evens']}, "
        f"sum of evens = {prev['sum_evens']}"
    )
    print(f"  [format] received {prev!r}")
    print(f"  [format] → {text!r}")
    return {"summary": text}


def main():
    db = tempfile.mktemp(suffix=".db")
    queue = JobQueue(db)

    wf = Workflow("stats_pipeline")
    g = wf.add_task(generate, params={"count": 6})
    t = wf.add_task(transform, depends_on=[g])
    f = wf.add_task(format_summary, depends_on=[t])
    wf_ids = wf.submit_all(queue)
    print("Submitted: generate → transform → format\n")

    worker = Worker(db, concurrency=2, polling_interval=0.1)
    th = threading.Thread(target=worker.start, daemon=True)
    th.start()
    while queue.get_status(wf_ids[-1])["status"] != "completed":
        time.sleep(0.1)
    worker.stop()
    th.join(timeout=5)
    worker.close()

    final = queue.get_result(wf_ids[-1])
    print(f"\nFinal job result: {final['summary']}")

    queue.close()
    for suffix in ("", "-wal", "-shm"):
        p = db + suffix
        if os.path.exists(p):
            os.unlink(p)


if __name__ == "__main__":
    main()
