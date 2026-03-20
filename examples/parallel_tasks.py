"""
Parallel Tasks — minimal GigQ example.

Shows the @task decorator and Worker(concurrency=N) with zero external
dependencies.  The workflow at the end fans out hash_block jobs and fans in
with summarise(), which receives every parent's return value via parent_results.

Usage:
    python examples/parallel_tasks.py

GigQ does not configure logging on import. For verbose worker/job logs during
development, call ``setup_logging()`` from ``gigq`` before starting workers.
"""

import hashlib
import os
import tempfile
import threading
import time

from gigq import JobQueue, Worker, Workflow, task


@task(timeout=30, max_attempts=2)
def hash_block(block_id, rounds=200_000):
    """Hash random data repeatedly to simulate a small workload."""
    data = os.urandom(64)
    for _ in range(rounds):
        data = hashlib.sha256(data).digest()
    return {"block_id": block_id, "sha256": data.hex()}


@task(timeout=10)
def summarise(parent_results):
    """Fan-in step: merge outputs from all hash_block parents (via parent_results)."""
    rows = sorted(
        (r for r in parent_results.values() if isinstance(r, dict)),
        key=lambda r: r["block_id"],
    )
    n = len(rows)
    digests = "".join(r["sha256"] for r in rows)
    combined = hashlib.sha256(digests.encode()).hexdigest()
    return {
        "parent_count": n,
        "combined_sha256_of_digests": combined,
        "sample_parents": [
            {"block_id": r["block_id"], "sha256_prefix": r["sha256"][:16]}
            for r in rows[:3]
        ],
    }


def main():
    db = tempfile.mktemp(suffix=".db")
    queue = JobQueue(db)

    # ── Batch submit ──────────────────────────────────────────
    num_jobs = 16
    job_ids = []
    for i in range(num_jobs):
        jid = hash_block.submit(queue, block_id=i)
        job_ids.append(jid)
    print(f"Submitted {num_jobs} jobs")

    # ── Process with concurrent worker ────────────────────────
    concurrency = 4
    worker = Worker(db, concurrency=concurrency, polling_interval=0.1)
    t = threading.Thread(target=worker.start, daemon=True)
    t0 = time.time()
    t.start()

    while True:
        stats = queue.stats()
        done = stats.get("completed", 0)
        if done >= num_jobs:
            break
        print(f"\r  {done}/{num_jobs} completed", end="", flush=True)
        time.sleep(0.3)
    elapsed = time.time() - t0
    print(
        f"\r  {num_jobs}/{num_jobs} completed in {elapsed:.1f}s (concurrency={concurrency})"
    )

    worker.stop()
    t.join(timeout=5)
    worker.close()

    for jid in job_ids[:3]:
        r = queue.get_result(jid)
        print(f"  block {r['block_id']}: {r['sha256'][:32]}...")

    # ── Workflow with dependencies ────────────────────────────
    db2 = tempfile.mktemp(suffix=".db")
    queue2 = JobQueue(db2)
    n = 8

    wf = Workflow("hash_pipeline")
    hash_jobs = []
    for i in range(n):
        j = wf.add_task(hash_block, params={"block_id": i})
        hash_jobs.append(j)
    wf.add_task(summarise, depends_on=hash_jobs)

    wf_ids = wf.submit_all(queue2)
    print(f"\nSubmitted workflow: {n} hash jobs → 1 summary")

    worker2 = Worker(db2, concurrency=4, polling_interval=0.1)
    t2 = threading.Thread(target=worker2.start, daemon=True)
    t2.start()

    while queue2.get_status(wf_ids[-1])["status"] != "completed":
        time.sleep(0.3)
    worker2.stop()
    t2.join(timeout=5)
    worker2.close()

    for wid in wf_ids:
        s = queue2.get_status(wid)
        print(f"  {s['name']:15s} {s['status']}")

    summary = queue2.get_result(wf_ids[-1])
    print(
        f"\n  summarise (parent_results): merged {summary['parent_count']} hash outputs"
    )
    print(
        f"  combined digest (sha256 of concatenated hex): {summary['combined_sha256_of_digests'][:32]}..."
    )
    for sp in summary["sample_parents"]:
        print(f"    parent block {sp['block_id']}: {sp['sha256_prefix']}...")

    # ── Cleanup ───────────────────────────────────────────────
    queue.close()
    queue2.close()
    for p in (db, db2):
        for suffix in ("", "-wal", "-shm"):
            f = p + suffix
            if os.path.exists(f):
                os.unlink(f)

    print("\nDone.")


if __name__ == "__main__":
    main()
