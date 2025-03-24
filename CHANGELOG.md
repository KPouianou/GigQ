# Changelog

All notable changes to GigQ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[Unreleased]: https://github.com/kpouianou/gigq/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kpouianou/gigq/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/kpouianou/gigq/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kpouianou/gigq/releases/tag/v0.1.0
