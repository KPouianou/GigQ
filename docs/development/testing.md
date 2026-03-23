# Testing GigQ

This guide explains how to test GigQ, both for developers contributing to the project and for users who want to ensure GigQ works correctly in their environment.

## Testing Philosophy

GigQ follows these testing principles:

1. **Comprehensive Coverage**: All core functionality should be tested
2. **Isolated Tests**: Tests should be independent of each other
3. **Fast Execution**: The test suite should run quickly
4. **Simple Setup**: Tests should be easy to run

## Test Structure

The tests are organized in the `tests/` directory, split into `unit/` (per-component tests) and `integration/` (end-to-end tests). Tests use both `pytest` and Python's built-in `unittest.TestCase`.

The test suite includes:

- **Unit Tests**: Testing individual functions and methods
- **Integration Tests**: Testing interactions between components
- **Functional Tests**: Testing end-to-end functionality

## Running Tests

### Basic Test Execution

To run the complete test suite:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/unit/test_job_queue.py
```

To run a specific test class:

```bash
pytest tests/unit/test_job_queue.py::TestJobQueue
```

To run a specific test method:

```bash
pytest tests/unit/test_job_queue.py::TestJobQueue::test_submit_job
```

### Running Tests with Coverage

To run tests with coverage reporting:

```bash
# Run tests with coverage (pytest-cov is used in CI)
pytest --cov=gigq

# Generate an HTML coverage report
pytest --cov=gigq --cov-report=html
```

The HTML report will be available in the `htmlcov/` directory.

## Writing Tests

### Test File Organization

Each test file should:

1. Import the necessary modules
2. Define test classes that inherit from `unittest.TestCase`
3. Include `setUp` and `tearDown` methods if needed
4. Define test methods that start with `test_`

Example:

```python
"""
Tests for the GigQ job queue functionality.
"""
import unittest
import tempfile
import os
from gigq import JobQueue, Job

class TestJobQueue(unittest.TestCase):
    """Tests for the JobQueue class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_submit_job(self):
        """Test that a job can be submitted to the queue."""
        job = Job(
            name="test_job",
            function=lambda: {"result": "success"}
        )

        job_id = self.queue.submit(job)
        self.assertEqual(job_id, job.id)

        # Check that the job was stored correctly
        status = self.queue.get_status(job_id)
        self.assertTrue(status["exists"])
        self.assertEqual(status["name"], "test_job")
```

### Test Case Best Practices

When writing test cases, follow these best practices:

1. **Test One Thing**: Each test method should test one specific piece of functionality
2. **Descriptive Names**: Use descriptive method names that explain what's being tested
3. **Arrange, Act, Assert**: Structure your tests with setup, execution, and verification
4. **Minimize Dependencies**: Avoid dependencies between test cases
5. **Clean Up**: Always clean up resources in `tearDown` methods

Example of a well-structured test:

```python
def test_job_timeout_detection(self):
    """Test that the worker detects timed out jobs."""
    # Arrange - Set up the test conditions
    job = Job(
        name="long_job",
        function=lambda: time.sleep(2),
        timeout=1
    )
    job_id = self.queue.submit(job)

    # Act - Execute the functionality being tested
    worker = Worker(self.db_path)
    worker.process_one()  # This should time out

    # Assert - Verify the results
    status = self.queue.get_status(job_id)
    self.assertEqual(status["status"], "timeout")
```

### Testing Async Code

For testing asynchronous code or long-running jobs, you may need to use timeouts and polling:

```python
def test_concurrent_workers(self):
    """Test that multiple workers can process jobs concurrently."""
    # Submit multiple jobs
    job_ids = []
    for i in range(5):
        job = Job(
            name=f"concurrent_job_{i}",
            function=lambda i=i: {"job_number": i}
        )
        job_id = self.queue.submit(job)
        job_ids.append(job_id)

    # Start multiple workers in separate threads
    workers = []
    for i in range(3):
        worker = Worker(self.db_path, worker_id=f"worker-{i}")
        thread = threading.Thread(target=worker.start)
        thread.daemon = True
        thread.start()
        workers.append((worker, thread))

    # Wait for all jobs to complete (with timeout)
    deadline = time.time() + 10  # 10 second timeout
    while time.time() < deadline:
        statuses = [self.queue.get_status(job_id)["status"] for job_id in job_ids]
        if all(status == "completed" for status in statuses):
            break
        time.sleep(0.1)

    # Stop all workers
    for worker, _ in workers:
        worker.stop()

    # Verify all jobs completed
    for job_id in job_ids:
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], "completed")
```

### Mocking Dependencies

For testing components in isolation, use `unittest.mock` to mock dependencies:

```python
from unittest.mock import MagicMock, patch

def test_worker_process_one_with_mock():
    """Test worker.process_one with mocked job function."""
    job = Job(
        name="mocked_job",
        function=lambda: None  # This will be mocked
    )
    job_id = self.queue.submit(job)

    # Mock the _import_function method
    mock_function = MagicMock(return_value={"mocked": True})

    with patch.object(Worker, '_import_function', return_value=mock_function):
        worker = Worker(self.db_path)
        worker.process_one()

    # Verify the mock was called
    mock_function.assert_called_once()

    # Verify the job is marked as completed
    status = self.queue.get_status(job_id)
    self.assertEqual(status["status"], "completed")
```

## Test Data

### Creating Test Data

For tests that require specific data:

1. **Small Data**: Include directly in the test
2. **Medium Data**: Create in `setUp` method
3. **Large Data**: Use fixtures in separate files

Example with medium data in `setUp`:

```python
def setUp(self):
    """Set up test data."""
    self.db_fd, self.db_path = tempfile.mkstemp()
    self.queue = JobQueue(self.db_path)

    # Create test jobs
    self.test_jobs = []
    for i in range(10):
        job = Job(
            name=f"test_job_{i}",
            function=lambda i=i: {"job_number": i},
            priority=i
        )
        job_id = self.queue.submit(job)
        self.test_jobs.append(job_id)
```

### Testing with Fixtures

For larger test data, use fixtures:

```python
import json
import os

def load_test_data(filename):
    """Load test data from a fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path, 'r') as f:
        return json.load(f)

class TestLargeDataset(unittest.TestCase):
    def setUp(self):
        self.test_data = load_test_data('large_dataset.json')
```

## Testing Specific Components

### Testing Job Class

```python
class TestJob(unittest.TestCase):
    """Tests for the Job class."""

    def test_job_initialization(self):
        """Test that a job can be initialized with the correct parameters."""
        job = Job(
            name="test_job",
            function=lambda x: x * 2,
            params={"x": 42},
            priority=5,
            dependencies=["job1", "job2"],
            max_attempts=2,
            timeout=120,
            description="A test job"
        )

        self.assertEqual(job.name, "test_job")
        self.assertEqual(job.params, {"x": 42})
        self.assertEqual(job.priority, 5)
        self.assertEqual(job.dependencies, ["job1", "job2"])
        self.assertEqual(job.max_attempts, 2)
        self.assertEqual(job.timeout, 120)
        self.assertEqual(job.description, "A test job")
        self.assertTrue(job.id)  # ID should be generated
```

### Testing JobQueue Class

```python
class TestJobQueue(unittest.TestCase):
    """Tests for the JobQueue class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_submit_job(self):
        """Test that a job can be submitted to the queue."""
        # Test code...

    def test_get_status(self):
        """Test that job status can be retrieved."""
        # Test code...

    def test_list_jobs(self):
        """Test that jobs can be listed from the queue."""
        # Test code...

    def test_cancel_job(self):
        """Test that a pending job can be cancelled."""
        # Test code...

    def test_requeue_job(self):
        """Test that a failed job can be requeued."""
        # Test code...

    def test_clear_completed(self):
        """Test that completed jobs can be cleared."""
        # Test code...
```

### Testing Worker Class

```python
class TestWorker(unittest.TestCase):
    """Tests for the Worker class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_process_one_job(self):
        """Test that a worker can process a job."""
        # Test code...

    def test_process_failing_job(self):
        """Test that a worker handles failing jobs correctly."""
        # Test code...

    def test_timeout_detection(self):
        """Test that the worker detects timed out jobs."""
        # Test code...

    def test_worker_stop(self):
        """Test that a worker can be stopped."""
        # Test code...
```

### Testing Workflow Class

```python
class TestWorkflow(unittest.TestCase):
    """Tests for the Workflow class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_workflow_dependencies(self):
        """Test that workflow dependencies are set correctly."""
        # Test code...

    def test_workflow_submission(self):
        """Test that a workflow can be submitted."""
        # Test code...

    def test_complex_workflow(self):
        """Test a complex workflow with multiple dependencies."""
        # Test code...
```

## Testing the CLI

To test the command-line interface:

```python
import sys
import io
from contextlib import redirect_stdout
from gigq.cli import main

class TestCLI(unittest.TestCase):
    """Tests for the command-line interface."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_submit_command(self):
        """Test the 'submit' command."""
        # Prepare test arguments
        sys.argv = [
            'gigq',
            '--db', self.db_path,
            'submit', 'builtins.print',
            '--name', 'test_job',
            '--param', 'message=Hello'
        ]

        # Capture stdout
        f = io.StringIO()
        with redirect_stdout(f):
            exit_code = main()

        # Check the output
        output = f.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Job submitted:", output)

    def test_list_command(self):
        """Test the 'list' command."""
        # First submit a job
        sys.argv = [
            'gigq',
            '--db', self.db_path,
            'submit', 'builtins.print',
            '--name', 'test_job'
        ]
        main()

        # Then list jobs
        sys.argv = [
            'gigq',
            '--db', self.db_path,
            'list'
        ]

        # Capture stdout
        f = io.StringIO()
        with redirect_stdout(f):
            exit_code = main()

        # Check the output
        output = f.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("test_job", output)
```

## Integration Testing

Integration tests verify that different components work together:

```python
class TestIntegration(unittest.TestCase):
    """Integration tests for GigQ."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_end_to_end_workflow(self):
        """Test an end-to-end workflow from submission to completion."""
        # Create a queue
        queue = JobQueue(self.db_path)

        # Create a workflow
        workflow = Workflow("test_workflow")

        # Define test functions
        def step1():
            return {"step1_complete": True}

        def step2(step1_result):
            return {"step2_complete": True, "step1_result": step1_result}

        # Create jobs
        job1 = Job(name="step1", function=step1)
        job2 = Job(name="step2", function=step2, params={"step1_result": {"step1_complete": True}})

        # Add jobs to workflow
        workflow.add_job(job1)
        workflow.add_job(job2, depends_on=[job1])

        # Submit workflow
        job_ids = workflow.submit_all(queue)

        # Create a worker and process jobs
        worker = Worker(self.db_path)

        # Process first job
        self.assertTrue(worker.process_one())

        # Check first job status
        status1 = queue.get_status(job_ids[0])
        self.assertEqual(status1["status"], "completed")

        # Process second job
        self.assertTrue(worker.process_one())

        # Check second job status
        status2 = queue.get_status(job_ids[1])
        self.assertEqual(status2["status"], "completed")
        self.assertEqual(status2["result"]["step2_complete"], True)
```

## Performance Testing

Test performance characteristics:

```python
class TestPerformance(unittest.TestCase):
    """Performance tests for GigQ."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        """Clean up the temporary database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_job_submission_performance(self):
        """Test the performance of job submission."""
        import time

        num_jobs = 1000
        start_time = time.time()

        # Submit many jobs
        for i in range(num_jobs):
            job = Job(
                name=f"perf_job_{i}",
                function=lambda: None
            )
            self.queue.submit(job)

        elapsed = time.time() - start_time
        jobs_per_second = num_jobs / elapsed

        print(f"Submitted {num_jobs} jobs in {elapsed:.2f} seconds ({jobs_per_second:.2f} jobs/sec)")

        # Assert that performance is reasonable
        self.assertGreater(jobs_per_second, 50)  # At least 50 jobs per second
```

## Continuous Integration

GigQ uses GitHub Actions for continuous integration. The CI pipeline runs:

1. **Formatting**: Checks code formatting with Black
2. **Type Checking**: Verifies type hints with mypy
3. **Tests**: Runs the full test suite with pytest
4. **Coverage**: Uploads coverage to Codecov

You can run the same checks locally:

```bash
# Check formatting
black --check gigq tests

# Run type checking
mypy gigq

# Run tests with coverage
pytest --cov=gigq
```

## Troubleshooting Tests

### Common Issues

1. **Database Locking**: If tests fail with database locking errors, ensure proper cleanup in `tearDown` methods.

2. **Race Conditions**: If tests involving multiple workers are flaky, add appropriate synchronization or timeouts.

3. **Resource Leaks**: If tests leave behind temporary files, check that all file handles are properly closed.

### Debugging Tests

For debugging tests:

```bash
# Run with increased verbosity
python -m unittest discover tests -v

# Add print statements for debugging
def test_problematic_function(self):
    print("Starting test")
    result = problematic_function()
    print(f"Result: {result}")
    self.assertTrue(result)
```

## Next Steps

Now that you understand how to test GigQ, you might want to explore:

- [Contributing Guide](contributing.md) - Learn how to contribute to GigQ
