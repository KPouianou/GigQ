# Changelog

This page documents the release history and notable changes for GigQ.

## 0.3.0 (2026-03-16)

### Features

- **Worker concurrency:** Added `--concurrency N` flag to the `gigq worker` command. A single worker process can now run N threads, each independently claiming and executing jobs from the queue. Default remains `--concurrency 1` (no breaking change).
- **WAL mode enabled by default:** SQLite connections now use Write-Ahead Logging (`PRAGMA journal_mode = WAL`), which significantly reduces lock contention under concurrent access. This creates `-wal` and `-shm` sidecar files alongside the database.

### API

- `Worker` class accepts a new `concurrency` parameter (default: `1`)
- `Worker.current_job_id` is now a thread-safe property backed by `threading.local()`
- Each concurrent thread gets a unique worker ID suffix (e.g., `worker-abc-0`, `worker-abc-1`) for monitoring

## 0.1.0 (2025-03-15)

Initial release of GigQ.

### Features

- Core job queue functionality with SQLite backend
- Job definition with parameters, priorities, and dependencies
- Worker implementation for job processing
- Workflow support for dependent jobs
- Command-line interface for job and worker management
- Automatic retry and timeout handling
- GitHub Archive processing example

### API

- `Job` class for defining jobs
- `JobQueue` class for managing jobs
- `Worker` class for processing jobs
- `Workflow` class for creating job workflows
- `JobStatus` enum for job state

### CLI Commands

- `submit` - Submit a job
- `status` - Check job status
- `list` - List jobs
- `cancel` - Cancel a job
- `requeue` - Requeue a failed job
- `clear` - Clear completed jobs
- `worker` - Start a worker

## Future Development

While not yet released, these features are planned for future versions:

### 0.2.0 (Planned)

- Enhanced monitoring and metrics
- Additional backend options (Redis, PostgreSQL)
- Job scheduling capabilities
- Better error handling and recovery
- Improved CLI with interactive mode
- Web-based admin interface

### 0.3.0 (Planned)

- Distributed job processing
- Custom job types
- Workflow templates
- Advanced job prioritization
- Performance optimizations
- Plugin system

## Contributing

GigQ is open for contributions. If you'd like to contribute, please:

1. Check the [issue tracker](https://github.com/kpouianou/gigq/issues) for open issues
2. Submit a pull request with your changes
3. Ensure tests pass and code meets the project's style guidelines

When contributing, please update the changelog with your changes under an "Unreleased" section.
