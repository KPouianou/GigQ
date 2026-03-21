# Changelog

All notable changes to GigQ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-03-21

### Added

- `retry_delay` (seconds) on `Job`, `@task`, and CLI: when a job fails and has retries left, the worker defers the next attempt until `retry_after` (schema migration; default `0` preserves previous behavior). MCP server supports the same option.

### Changed

- Documentation: scheduling guide (cron and long-running Python loops), `llms.txt` / `llms-full.txt` for AI tooling, `GITHUB_TOPICS.md`, and richer PyPI metadata (keywords, classifiers). README and docs cleaned up for clarity.

### Fixed

- Broken documentation link to the GitHub Pages site.

## [0.5.0] - 2026-03-21

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

## [0.3.0] - 2026-03-16

### Added

- `--concurrency N` flag for the `gigq worker` command — one worker process, N threads, each independently claiming and executing jobs from the queue
- SQLite WAL (Write-Ahead Logging) mode enabled by default on all connections, reducing lock contention under concurrent access
- Per-thread worker IDs (e.g., `worker-abc-0`, `worker-abc-1`) for monitoring concurrent threads
- Per-thread loggers scoped to thread-specific worker IDs

### Changed

- `Worker` class accepts a new `concurrency` parameter (default: `1`, no breaking change)
- `Worker.current_job_id` is now a thread-safe property backed by `threading.local()`
- Signal handlers in `Worker.start()` are only registered when running on the main thread

## [0.2.1] - 2026-03-13

### Added

- `JobQueue.stats()` method to retrieve aggregate job counts by status in a single query
- `gigq stats` CLI command to display queue statistics in a table
- `JobQueue.get_result()` method to fetch only the deserialized job result for completed jobs

### Changed

- Minimum Python version bumped from 3.9 to 3.10

## [0.2.0] - 2025-03-24

### Added

- Thread-local SQLite connection management for improved performance
- New `db_utils` module for database connection handling
- `close_connections()` function to clean up thread resources

### Changed

- JobQueue and Worker now reuse connections within each thread
- Updated tests to properly handle thread-local connections

## [0.1.1] - 2025-03-22

### Fixed

- Fixed project shields in README
- Implemented comprehensive test coverage

## [0.1.0] - 2025-03-15

### Added

- Core job queue functionality with SQLite backend
- Job definition with parameters, priorities, and dependencies
- Worker implementation for job processing
- Workflow support for dependent jobs
- Command-line interface for job and worker management
- Automatic retry and timeout handling
- GitHub Archive processing example
- Documentation with MkDocs

[Unreleased]: https://github.com/kpouianou/gigq/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/kpouianou/gigq/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/kpouianou/gigq/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/kpouianou/gigq/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/kpouianou/gigq/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/kpouianou/gigq/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/kpouianou/gigq/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/kpouianou/gigq/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kpouianou/gigq/releases/tag/v0.1.0
