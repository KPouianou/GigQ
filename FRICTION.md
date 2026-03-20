# Friction notes (internals & design)

## Workflow parent result passing (`parent_results`)

### Design choices

- **Explicit parameter name:** Dependent tasks opt in by declaring a parameter
  named `parent_results` (or `**kwargs`). Values are a `dict` mapping **parent
  job ID → deserialized result** from the `jobs.result` column. This keeps
  behavior visible in the function signature and avoids guessing which user
  parameter should receive which parent output.

- **Tri-state `Job.pass_parent_results`:** `None` (auto: inject only when the
  signature accepts `parent_results` or `**kwargs`), `True` (always inject when
  there are dependencies), `False` (never inject). This keeps existing jobs
  that have dependencies but no `parent_results` parameter working unchanged
  under auto mode.

- **Schema:** A dedicated `pass_parent_results` column on `jobs` stores the
  tri-state. Alternatives like encoding flags inside `params` JSON were
  rejected to avoid collisions with user data and to keep the worker’s merge
  logic clear.

### What made this harder than it should be

- **Job functions must be importable:** The worker loads callables by
  `(module, name)` from the DB, so ad-hoc lambdas or nested functions cannot be
  used as job targets. Integration tests that want to assert “no injection”
  need a module-level helper (e.g. in `tests/job_functions.py`), not a closure
  defined inside a test method.

- **No single place for “job execution context”:** Injection is implemented in
  `Worker.process_one` because that is where `params` meet the imported
  function. A shared “execution context” layer would centralize this and other
  future concerns (e.g. tracing), but that would be a larger refactor.

- **Circular import risk:** Normalizing DB values for `pass_parent_results` is
  shared between `JobQueue` and `Worker` via a small helper in `job_queue.py`
  imported by `worker.py`. A dedicated `schema.py` or `types.py` module could
  hold shared primitives without tying `worker` to `job_queue`.
