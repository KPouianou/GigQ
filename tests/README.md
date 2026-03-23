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

# GigQ Tests

GigQ is a lightweight job queue system with SQLite as its backend.

## Project Structure

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
│   ├── parallel_tasks.py       # @task decorator + concurrent workers
│   ├── data_pipeline.py        # Sequential pipeline with parent_results
│   └── hyperparameter_tuning.py # ML hyperparameter tuning demo
│
├── gigq/                        # Main package code
│   ├── __init__.py             # Package initialization and public API
│   ├── job.py                  # Job class
│   ├── job_queue.py            # JobQueue class
│   ├── job_status.py           # JobStatus enum
│   ├── worker.py               # Worker class
│   ├── workflow.py             # Workflow class
│   ├── decorators.py           # @task decorator
│   ├── db_utils.py             # Thread-local connection management
│   ├── utils.py                # setup_logging and utilities
│   ├── cli.py                  # Command-line interface
│   └── table_formatter.py      # Table formatting for CLI output
│
├── tests/                       # Test directory
│   ├── __init__.py             # Test package initialization
│   ├── README.md               # This file
│   ├── job_functions.py        # Shared test functions
│   │
│   ├── unit/                   # Unit tests
│   │   ├── __init__.py
│   │   ├── run_all.py          # Run all unit tests
│   │   ├── test_cli.py         # CLI unit tests
│   │   ├── test_cli_formatter.py  # CLI formatter tests
│   │   ├── test_db_utils.py    # DB utilities tests
│   │   ├── test_decorators.py  # @task decorator tests
│   │   ├── test_job.py         # Job class tests
│   │   ├── test_job_queue.py   # JobQueue class tests
│   │   ├── test_table_formatter.py  # Table formatter tests
│   │   ├── test_thread_local_job_queue.py  # Thread-local connection tests
│   │   ├── test_worker.py      # Worker class tests
│   │   └── test_workflow.py    # Workflow class tests
│   │
│   └── integration/            # Integration tests
│       ├── __init__.py
│       ├── base.py             # Base class for integration tests
│       ├── run_all.py          # Run all integration tests
│       ├── test_basic.py       # Basic job processing tests
│       ├── test_basic_workflow.py  # Simple workflow tests
│       ├── test_cli.py         # CLI integration tests
│       ├── test_concurrent_workers.py  # Multiple workers tests
│       ├── test_decorator.py   # @task decorator integration tests
│       ├── test_error_handling.py  # Error handling tests
│       ├── test_persistence.py  # Persistence tests
│       ├── test_retry_delay.py  # retry_delay feature tests
│       ├── test_timeout_handling.py  # Timeout handling tests
│       ├── test_worker_concurrency.py  # Worker concurrency tests
│       ├── test_workflow_dependencies.py  # Workflow dependencies tests
│       └── test_workflow_parent_results.py  # parent_results passing tests
│
├── .github/                     # GitHub configuration
│   └── workflows/               # GitHub Actions workflows
│       ├── ci.yml              # Continuous integration workflow
│       └── docs.yml            # Documentation deployment workflow
│
├── LICENSE                      # MIT License
├── README.md                    # Project readme
├── pyproject.toml               # Project configuration
└── setup.py                     # Minimal setup.py for backward compatibility
```

## Installation

### Basic Installation

Install GigQ from PyPI:

```bash
pip install gigq
```

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

   # For development (formatting, testing)
   pip install -e ".[dev]"

   # Or install everything at once
   pip install -e ".[examples,docs,dev]"
   ```

## Dependencies

- **Build dependencies**: setuptools (>=42) and wheel
- **Core dependencies**: Python 3.10+
- **Examples**: pandas, requests, schedule, scikit-learn
- **Documentation**: mkdocs-material, pymdown-extensions, mkdocstrings[python], etc.
- **Development**: pytest, black, coverage, mypy

## Running Tests

```bash
# Run the full test suite
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=gigq

# Run a specific test file
pytest tests/unit/test_job_queue.py

# Run with verbose output
pytest -v
```

## Check Formatting

```bash
black --check gigq tests
```

To auto-fix formatting:

```bash
black gigq tests
```

## Examples

See `examples/parallel_tasks.py` for a zero-dep demo or `examples/hyperparameter_tuning.py` for the full showpiece.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
