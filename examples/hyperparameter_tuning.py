"""
Hyperparameter Tuning with GigQ.

Three-act demo showing the @task decorator, concurrent workers, and crash recovery:

  Act 1 — Sequential baseline    (concurrency=1)
  Act 2 — Parallel speedup       (concurrency=8)
  Act 3 — Crash recovery         (stop mid-run, resume, zero work repeated)

Requires scikit-learn:
    pip install scikit-learn

Usage:
    python examples/hyperparameter_tuning.py

GigQ does not configure logging on import. For verbose worker/job logs, call
``setup_logging()`` from ``gigq`` before starting workers.
"""

import itertools
import os
import sys
import tempfile
import threading
import time

try:
    from sklearn.datasets import make_classification
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
except ImportError:
    print(
        "This example requires scikit-learn.\n"
        "Install it with:  pip install scikit-learn\n"
        "Or install all example dependencies:  pip install gigq[examples]"
    )
    sys.exit(1)

import numpy as np

from gigq import JobQueue, Worker, task

# ─── ANSI display helpers ────────────────────────────────────────────────

_TTY = sys.stdout.isatty()

BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
GREEN = "\033[92m" if _TTY else ""
YELLOW = "\033[93m" if _TTY else ""
CYAN = "\033[96m" if _TTY else ""
RED = "\033[91m" if _TTY else ""
R = "\033[0m" if _TTY else ""  # reset


def _hr():
    return "\u2500" * 58


def header(title):
    print(f"\n  {_hr()}\n  {BOLD}{title}{R}\n  {_hr()}\n")


def progress(done, running, total, width=35):
    pct = done / total if total else 1
    filled = int(width * pct)
    active = min(int(width * running / total) if total else 0, width - filled)
    empty = width - filled - active
    bar = (
        f"{GREEN}\u2588{R}" * filled
        + f"{YELLOW}\u2593{R}" * active
        + f"{DIM}\u2591{R}" * empty
    )
    tag = f"{GREEN}\u2713{R}" if done >= total else f"{done}/{total}"
    line = f"  [{bar}] {tag}"
    if _TTY:
        print(f"\033[2K\r{line}", end="", flush=True)
    else:
        print(line)


def finish_progress():
    if _TTY:
        print()


# ─── Dataset ─────────────────────────────────────────────────────────────


def _save_dataset(path, X, y):
    np.savez_compressed(path, X=X, y=y)


def _load_dataset(path):
    d = np.load(path)
    return d["X"], d["y"]


# ─── Task definition ─────────────────────────────────────────────────────


@task(timeout=120, max_attempts=2)
def train_experiment(dataset_path, n_estimators, max_depth, criterion):
    X, y = _load_dataset(dataset_path)
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        criterion=criterion,
        random_state=42,
        n_jobs=1,
    )
    scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy")
    return {
        "params": {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "criterion": criterion,
        },
        "mean_accuracy": round(float(scores.mean()), 5),
        "std_accuracy": round(float(scores.std()), 5),
        "fold_scores": [round(float(s), 5) for s in scores],
    }


# ─── Grid ────────────────────────────────────────────────────────────────

GRID = {
    "n_estimators": [10, 30, 50],
    "max_depth": [3, 5, 10, 20, None],
    "criterion": ["gini", "entropy"],
}


def all_combos():
    return list(itertools.product(*GRID.values()))


# ─── Helpers ─────────────────────────────────────────────────────────────


def submit_all_experiments(queue, dataset_path, combos):
    job_ids = []
    for n_est, max_d, crit in combos:
        jid = train_experiment.submit(
            queue,
            dataset_path=dataset_path,
            n_estimators=n_est,
            max_depth=max_d,
            criterion=crit,
        )
        job_ids.append(jid)
    return job_ids


def poll_until(queue, target, total):
    while True:
        stats = queue.stats()
        done = stats.get("completed", 0)
        running = stats.get("running", 0)
        progress(done, running, total)
        if done >= target:
            break
        time.sleep(0.3)
    finish_progress()
    return done


def fresh_db():
    return tempfile.mktemp(suffix=".db")


def cleanup_db(path):
    for suffix in ("", "-wal", "-shm"):
        p = path + suffix
        if os.path.exists(p):
            os.unlink(p)


# ─── Act 1: Sequential ──────────────────────────────────────────────────


def act_sequential(dataset_path, combos):
    header("Act 1 \u00b7 Sequential Baseline (concurrency=1)")

    db = fresh_db()
    queue = JobQueue(db)
    submit_all_experiments(queue, dataset_path, combos)
    total = len(combos)
    print(f"  {CYAN}\u25b8{R} {total} experiments, single-threaded worker\n")

    worker = Worker(db, concurrency=1, polling_interval=0.1)
    t = threading.Thread(target=worker.start, daemon=True)
    t0 = time.time()
    t.start()

    poll_until(queue, total, total)
    elapsed = time.time() - t0

    worker.stop()
    t.join(timeout=5)
    worker.close()

    print(f"\n  {BOLD}{elapsed:.1f}s{R} for {total} experiments\n")

    queue.close()
    cleanup_db(db)
    return elapsed


# ─── Act 2: Parallel ────────────────────────────────────────────────────


def act_parallel(dataset_path, combos, concurrency=8):
    header(f"Act 2 \u00b7 Parallel (concurrency={concurrency})")

    db = fresh_db()
    queue = JobQueue(db)
    submit_all_experiments(queue, dataset_path, combos)
    total = len(combos)
    print(f"  {CYAN}\u25b8{R} {total} experiments, {concurrency} threads\n")

    worker = Worker(db, concurrency=concurrency, polling_interval=0.1)
    t = threading.Thread(target=worker.start, daemon=True)
    t0 = time.time()
    t.start()

    poll_until(queue, total, total)
    elapsed = time.time() - t0

    worker.stop()
    t.join(timeout=5)
    worker.close()

    print(f"\n  {BOLD}{elapsed:.1f}s{R} for {total} experiments\n")

    queue.close()
    cleanup_db(db)
    return elapsed


# ─── Speedup chart ──────────────────────────────────────────────────────


def show_speedup(seq_time, par_time):
    header("Speedup")
    bar_width = 40
    par_width = max(1, int(bar_width * par_time / seq_time))
    speedup = seq_time / par_time if par_time > 0 else float("inf")

    seq_bar = f"{DIM}{'=' * bar_width}{R}"
    par_bar = f"{GREEN}{'=' * par_width}{R}{DIM}{'.' * (bar_width - par_width)}{R}"
    print(f"  Sequential  {seq_bar}  {seq_time:.1f}s")
    print(
        f"  Parallel    {par_bar}  {par_time:.1f}s  {GREEN}\u25b8 {speedup:.1f}\u00d7 faster{R}"
    )
    print()


# ─── Act 3: Crash recovery ──────────────────────────────────────────────


def act_crash_recovery(dataset_path, combos, concurrency=8):
    header("Act 3 \u00b7 Crash Recovery")

    db = fresh_db()
    queue = JobQueue(db)
    job_ids = submit_all_experiments(queue, dataset_path, combos)
    total = len(combos)
    halfway = total // 2

    print(f"  {CYAN}\u25b8{R} {total} experiments submitted\n")

    # Phase 1: process until roughly half done
    worker = Worker(db, concurrency=concurrency, polling_interval=0.1)
    t = threading.Thread(target=worker.start, daemon=True)
    t.start()

    actually_done = poll_until(queue, halfway, total)

    worker.stop()
    t.join(timeout=5)
    worker.close()

    # Let any in-flight completions settle
    time.sleep(0.3)
    stats = queue.stats()
    done_count = stats.get("completed", 0)
    pending_count = stats.get("pending", 0)

    print(f"\n\n  {RED}\u2716 Simulating crash \u2014 worker stopped.{R}\n")
    print(f"  {DIM}Checking database...{R}")
    print(f"  {GREEN}\u2713{R} {done_count} results safely persisted to SQLite")
    print(f"  {DIM}\u25cb{R} {pending_count} experiments still pending\n")

    # Phase 2: restart and finish
    print(f"  {CYAN}\u25b8{R} Restarting worker...\n")

    worker2 = Worker(db, concurrency=concurrency, polling_interval=0.1)
    t2 = threading.Thread(target=worker2.start, daemon=True)
    t2.start()

    poll_until(queue, total, total)

    worker2.stop()
    t2.join(timeout=5)
    worker2.close()

    print(
        f"\n\n  {GREEN}\u2713{R} {BOLD}All {total} experiments finished. Zero work repeated.{R}\n"
    )

    return db, job_ids


# ─── Results table ──────────────────────────────────────────────────────


def show_results(db_path, job_ids):
    header("Results")

    queue = JobQueue(db_path)
    results = []
    for jid in job_ids:
        r = queue.get_result(jid)
        if r:
            results.append(r)
    results.sort(key=lambda r: r["mean_accuracy"], reverse=True)

    print(
        f"  {BOLD}{'#':>3}  {'n_est':>6}  {'depth':>6}  {'criterion':>10}  {'accuracy':>16}{R}"
    )
    print(f"  {'\u2500'*3}  {'\u2500'*6}  {'\u2500'*6}  {'\u2500'*10}  {'\u2500'*16}")

    for i, r in enumerate(results[:5], 1):
        p = r["params"]
        md = str(p["max_depth"]) if p["max_depth"] is not None else "None"
        star = f"{GREEN}\u2605{R}" if i == 1 else " "
        print(
            f" {star}{i:>2}  {p['n_estimators']:>6}  {md:>6}  "
            f"{p['criterion']:>10}  "
            f"{r['mean_accuracy']:.5f} \u00b1 {r['std_accuracy']:.5f}"
        )

    best = results[0]
    header("Best Model")
    bp = best["params"]
    md = str(bp["max_depth"]) if bp["max_depth"] is not None else "None"
    print(
        f"    n_estimators={GREEN}{bp['n_estimators']}{R}  max_depth={GREEN}{md}{R}  criterion={GREEN}{bp['criterion']}{R}"
    )
    print(
        f"    accuracy = {BOLD}{GREEN}{best['mean_accuracy']:.5f} \u00b1 {best['std_accuracy']:.5f}{R}"
    )
    print(f"    folds    = {best['fold_scores']}")
    print()

    queue.close()


# ─── Main ────────────────────────────────────────────────────────────────


def main():
    n_samples = 3000
    combos = all_combos()
    concurrency = 8

    print(f"\n  {BOLD}GigQ: Hyperparameter Tuning{R}")
    print(f"  {_hr()}\n")
    print(f"  {CYAN}\u25b8{R} Dataset     {n_samples:,} samples \u00d7 20 features")
    print(f"  {CYAN}\u25b8{R} Model       RandomForestClassifier")
    print(f"  {CYAN}\u25b8{R} Grid        {len(combos)} combinations")
    print(f"  {CYAN}\u25b8{R} CV folds    5")

    # Generate dataset
    X, y = make_classification(
        n_samples=n_samples,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        random_state=42,
    )
    dataset_path = tempfile.mktemp(suffix=".npz")
    _save_dataset(dataset_path, X, y)

    try:
        seq_time = act_sequential(dataset_path, combos)
        par_time = act_parallel(dataset_path, combos, concurrency=concurrency)
        show_speedup(seq_time, par_time)
        db, job_ids = act_crash_recovery(dataset_path, combos, concurrency=concurrency)
        try:
            show_results(db, job_ids)
        finally:
            cleanup_db(db)
    finally:
        os.unlink(dataset_path)


if __name__ == "__main__":
    main()
