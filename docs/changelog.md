# Changelog

All notable changes to GigQ are documented here. See the full [CHANGELOG.md](https://github.com/kpouianou/gigq/blob/main/CHANGELOG.md) on GitHub for links to diffs.

## 0.5.0 (2026-03-21)

### Added

- `parent_results`: dependent jobs automatically receive parent job results via a `parent_results` parameter. Auto-detected from function signature, or controlled via `Job(pass_parent_results=True/False/None)` and `Workflow.add_task(..., pass_parent_results=...)`.
- `examples/data_pipeline.py`: sequential pipeline example demonstrating `parent_results` chaining (generate → transform → format).
- MCP server (`mcp_server/`): Model Context Protocol server for AI agent integration — submit jobs and workflows, monitor queues, retrieve results. Separate package (`gigq-mcp`).
- Docs integration page for the MCP server.

### Changed

- Library no longer configures logging on import. `NullHandler` is used by default (standard Python library convention). Call `setup_logging()` explicitly for verbose output. The CLI configures its own logging.
- `parallel_tasks.py` example updated: `summarise` now uses `parent_results` to receive and process parent job outputs.

### Fixed

- Code formatting (Black) in `job_queue.py` and `tests/job_functions.py`.

## 0.3.0 (2026-03-16)

### Added

- `--concurrency N` flag for the `gigq worker` command — one worker process, N threads, each independently claiming and executing jobs from the queue.
- SQLite WAL (Write-Ahead Logging) mode enabled by default on all connections, reducing lock contention under concurrent access.
- Per-thread worker IDs (e.g., `worker-abc-0`, `worker-abc-1`) for monitoring concurrent threads.

### Changed

- `Worker` class accepts a new `concurrency` parameter (default: `1`, no breaking change).
- `Worker.current_job_id` is now a thread-safe property backed by `threading.local()`.
- Signal handlers in `Worker.start()` are only registered when running on the main thread.

## 0.2.1 (2026-03-13)

### Added

- `JobQueue.stats()` method to retrieve aggregate job counts by status in a single query.
- `gigq stats` CLI command to display queue statistics in a table.
- `JobQueue.get_result()` method to fetch only the deserialized job result for completed jobs.

### Changed

- Minimum Python version bumped from 3.9 to 3.10.

## 0.2.0 (2025-03-24)

### Added

- Thread-local SQLite connection management for improved performance.
- New `db_utils` module for database connection handling.
- `close_connections()` function to clean up thread resources.

### Changed

- JobQueue and Worker now reuse connections within each thread.

## 0.1.1 (2025-03-22)

### Fixed

- Fixed project shields in README.
- Implemented comprehensive test coverage.

## 0.1.0 (2025-03-15)

Initial release of GigQ.

### Added

- Core job queue functionality with SQLite backend.
- Job definition with parameters, priorities, and dependencies.
- Worker implementation for job processing.
- Workflow support for dependent jobs.
- Command-line interface for job and worker management.
- Automatic retry and timeout handling.
- Documentation with MkDocs.
