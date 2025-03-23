<h1 align="center">
  <span style="color: #4f81e6;">Gig</span><span style="color: #60cdff;">Q</span>
</h1>
<p align="center">Lightweight SQLite Job Queue</p>

<p align="center">
  <a href="https://pypi.org/project/gigq/"><img alt="PyPI" src="https://img.shields.io/pypi/v/gigq.svg?style=flat-square"></a>
  <a href="https://pypi.org/project/gigq/"><img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/gigq.svg?style=flat-square"></a>
  <a href="https://github.com/kpouianou/gigq/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/kpouianou/gigq?style=flat-square"></a>
  <a href="https://github.com/kpouianou/gigq/actions/workflows/ci.yml"><img alt="Build Status" src="https://img.shields.io/github/actions/workflow/status/kpouianou/gigq/ci.yml?branch=main&style=flat-square"></a>
</p>

# GigQ

GigQ is a lightweight job queue system with SQLite as its backend. It provides a reliable way to manage and execute small jobs ("gigs") locally with atomicity guarantees, particularly suited for processing tasks like data transformations, API calls, or batch operations.

## Features

- **Zero External Dependencies**

  - No external packages required
  - Uses Python's built-in sqlite3 module
  - Everything needed is bundled with GigQ - no dependency conflicts to worry about

- **Simple Job Definition & Management**

  - Define small jobs with parameters, priority, and basic dependencies
  - Organize jobs into simple workflows
  - Enable job cancellation and status checking

- **SQLite State Storage**

  - Maintain job states in SQLite (pending, running, completed, failed)
  - Use transactions to ensure state consistency
  - Simple, efficient schema design optimized for local usage
  - Handle SQLite locking appropriately for local concurrency

- **Lightweight Concurrency**

  - Prevent duplicate job execution using SQLite locking mechanisms
  - Support a modest number of workers processing jobs simultaneously
  - Implement transaction-based state transitions
  - Handle worker crashes and job recovery

- **Basic Recovery**

  - Configurable retry for failed jobs with backoff
  - Timeout detection for hung jobs
  - Simple but effective error logging

- **CLI Interface**
  - Submit and monitor jobs
  - View job queue and history
  - Simple worker management commands

## Project Structure

The GigQ library is organized as follows:

```
gigq/
├── docs/                        # Documentation
│   ├── advanced/               # Advanced topics
│   ├── api/                    # API reference
│   ├── examples/               # Documentation examples
│   ├── getting-started/        # Getting started guides
│   └── user-guide/             # User guides
│
├── examples/                    # Example applications
│   ├── __init__.py
│   └── github_archive.py       # GitHub Archive processing example
│
├── gigq/                        # Main package code
│   ├── __init__.py             # Package initialization and exports
│   ├── job.py                  # Job class implementation
│   ├── job_status.py           # JobStatus enum implementation
│   ├── job_queue.py            # JobQueue class implementation
│   ├── worker.py               # Worker class implementation
│   ├── workflow.py             # Workflow class implementation
│   ├── utils.py                # Utility functions
│   ├── cli.py                  # Command-line interface
│   └── table_formatter.py      # Table formatting utilities
│
├── tests/                       # Test directory
│   ├── __init__.py             # Test package initialization
│   ├── README.md               # Test documentation
│   ├── job_functions.py        # Shared test functions
│   │
│   ├── unit/                   # Unit tests
│   │   ├── __init__.py
│   │   ├── run_all.py          # Run all unit tests
│   │   ├── test_cli.py         # CLI unit tests
│   │   ├── test_cli_formatter.py  # CLI formatter tests
│   │   ├── test_job.py         # Job class tests
│   │   ├── test_job_queue.py   # JobQueue class tests
│   │   ├── test_table_formatter.py  # Table formatter tests
│   │   ├── test_worker.py      # Worker class tests
│   │   ├── test_workflow.py    # Workflow class tests
│   │   └── test_refactoring.py # Tests for refactored modules
│   │
│   └── integration/            # Integration tests
│       ├── __init__.py
│       ├── base.py             # Base class for integration tests
│       ├── run_all.py          # Run all integration tests
│       ├── test_basic.py       # Basic job processing tests
│       ├── test_basic_workflow.py  # Simple workflow tests
│       ├── test_cli.py         # CLI integration tests
│       ├── test_concurrent_workers.py  # Multiple workers tests
│       ├── test_error_handling.py  # Error handling tests
│       ├── test_persistence.py  # Persistence tests
│       ├── test_timeout_handling.py  # Timeout handling tests
│       └── test_workflow_dependencies.py  # Workflow dependencies tests
│
├── .github/                     # GitHub configuration
│   └── workflows/               # GitHub Actions workflows
│       ├── ci.yml              # Continuous integration workflow
│       └── docs.yml            # Documentation deployment workflow
│
├── LICENSE                      # MIT License
├── README.md                    # Project readme
├── README_REFACTORING.md        # Refactoring documentation
├── REFACTORING_SUMMARY.md       # Summary of refactoring changes
├── update_test_imports.py       # Script to update test imports
├── test_refactoring.py          # Script to test refactored modules
├── pyproject.toml               # Project configuration
├── setup.py                     # Package setup script
└── py.typed                     # Type hint marker
```

## Installation

### Basic Installation

Install GigQ from PyPI:

```bash
pip install gigq
```

This installs the core package with minimal dependencies.

### Development Installation

For contributors and developers:

1. Clone the repository:

   ```bash
   git clone https://github.com/kpouianou/gigq.git
   cd gigq
   ```

2. Install in development mode with all dependencies:

   ```bash
   # Install core package in development mode
   pip install -e .

   # For running examples
   pip install -e ".[examples]"

   # For building documentation
   pip install -e ".[docs]"

   # For development (linting, testing)
   pip install -e ".[dev]"

   # Or install everything at once
   pip install -e ".[examples,docs,dev]"
   ```

## Dependencies

- **Build dependencies**: setuptools (>=42) and wheel
- **Core dependencies**: Python 3.9+ and tabulate
- **Examples**: Additional dependencies for running examples include pandas, requests, and schedule
- **Documentation**: MkDocs and related plugins for building the documentation (mkdocs-material, pymdown-extensions, mkdocstrings[python], etc.)
- **Development**: Testing and code quality tools (pytest, flake8, coverage, mypy, etc.)

Note: If you're only interested in using the CLI or basic functionality, the standard installation is sufficient.

## Quick Start

### Define and Submit a Job

```python
from gigq import Job, JobQueue, Worker

# Define a job function
def process_data(filename, threshold=0.5):
    # Process some data
    print(f"Processing {filename} with threshold {threshold}")
    return {"processed": True, "count": 42}

# Define a job
job = Job(
    name="process_data_job",
    function=process_data,
    params={"filename": "data.csv", "threshold": 0.7},
    max_attempts=3,
    timeout=300
)

# Create or connect to a job queue
queue = JobQueue("jobs.db")
job_id = queue.submit(job)

print(f"Submitted job with ID: {job_id}")
```

### Start a Worker

```python
# Start a worker
worker = Worker("jobs.db")
worker.start()  # This blocks until the worker is stopped
```

Or use the CLI:

```bash
# Start a worker
gigq --db jobs.db worker

# Process just one job
gigq --db jobs.db worker --once
```

### Check Job Status

```python
# Check job status
status = queue.get_status(job_id)
print(f"Job status: {status['status']}")
```

Or use the CLI:

```bash
gigq --db jobs.db status your-job-id
```

## Creating Workflows

GigQ allows you to create workflows of dependent jobs:

```python
from gigq import Workflow

# Create a workflow
workflow = Workflow("data_processing")

# Add jobs with dependencies
job1 = Job(name="download", function=download_data, params={"url": "https://example.com/data.csv"})
job2 = Job(name="process", function=process_data, params={"filename": "data.csv"})
job3 = Job(name="analyze", function=analyze_data, params={"processed_file": "processed.csv"})

# Add jobs to workflow with dependencies
workflow.add_job(job1)
workflow.add_job(job2, depends_on=[job1])
workflow.add_job(job3, depends_on=[job2])

# Submit all jobs in the workflow
job_ids = workflow.submit_all(queue)
```

## CLI Usage

GigQ comes with a command-line interface for common operations:

```bash
# Submit a job
gigq submit my_module.my_function --name "My Job" --param "filename=data.csv" --param "threshold=0.7"

# List jobs
gigq list
gigq list --status pending

# Check job status
gigq status your-job-id --show-result

# Cancel a job
gigq cancel your-job-id

# Requeue a failed job
gigq requeue your-job-id

# Start a worker
gigq worker

# Clear completed jobs
gigq clear
gigq clear --before 7  # Clear jobs completed more than 7 days ago
```

## Example: GitHub Archive Processing

See the `examples/github_archive.py` script for a complete example of using GigQ to process GitHub Archive data.

## Technical Details

### SQLite Schema

GigQ uses a simple SQLite schema with two main tables:

1. `jobs` - Stores job definitions and current state
2. `job_executions` - Tracks individual execution attempts

The schema is designed for simplicity and efficiency with appropriate indexes for common operations.

### Concurrency Handling

GigQ uses SQLite's built-in locking mechanisms to ensure safety when multiple workers are running. Each worker claims jobs using an exclusive transaction, preventing duplicate execution.

### Error Handling

Failed jobs can be automatically retried up to a configurable number of times. Detailed error information is stored in the database for debugging. Jobs that exceed their timeout are automatically detected and marked as failed or requeued.

## Development and Contribution

For local development:

1. Clone the repository
2. Create a virtual environment
3. Install build dependencies: `pip install setuptools wheel`
4. Install in development mode: `pip install -e .`
5. Run tests: `python -m unittest discover tests`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
