# Contributing to GigQ

Thank you for your interest in contributing to GigQ! This guide will help you get started with the development process and outline how to contribute to the project.

## Code of Conduct

By participating in this project, you agree to adhere to our Code of Conduct. Please treat other contributors with respect and maintain a positive and inclusive environment.

## Getting Started

### Prerequisites

To contribute to GigQ, you'll need:

1. Python 3.9 or newer
2. Git
3. A GitHub account

### Setting Up Your Development Environment

1. **Fork the repository** on GitHub.

2. **Clone your fork** to your local machine:

   ```bash
   git clone https://github.com/YOUR-USERNAME/gigq.git
   cd gigq
   ```

3. **Create a virtual environment**:

   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

4. **Install the package in development mode**:

   ```bash
   pip install -e .
   ```

5. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Development Workflow

### Creating a Branch

Before making changes, create a branch from the main branch:

```bash
git checkout -b feature/your-feature-name
```

or

```bash
git checkout -b bugfix/issue-number-description
```

### Making Changes

1. Make your changes to the code.
2. Add tests for any new functionality or bug fixes.
3. Ensure all tests pass:
   ```bash
   python -m unittest discover tests
   ```
4. Run linting to ensure code quality:
   ```bash
   flake8 gigq tests
   ```

### Committing Changes

1. Stage your changes:

   ```bash
   git add .
   ```

2. Commit your changes with a descriptive message:

   ```bash
   git commit -m "Add feature: description of your feature"
   ```

3. Push your changes to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

### Submitting a Pull Request

1. Go to the original GigQ repository on GitHub.
2. Click on "Pull Requests" and then "New Pull Request".
3. Click "compare across forks" and select your fork and branch.
4. Add a title and description for your pull request.
5. Submit the pull request.

## Coding Standards

### Python Style Guide

GigQ follows the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide for Python code. Additionally:

- Use 4 spaces for indentation (no tabs).
- Add docstrings for all modules, classes, and functions.
- Keep line length to a maximum of 88 characters.
- Use descriptive variable names.

### Docstrings

Use Google-style docstrings:

```python
def function_example(param1, param2):
    """
    A brief description of what the function does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of the return value

    Raises:
        ExceptionType: When and why this exception is raised
    """
```

### Type Hints

Use type hints for function parameters and return values:

```python
def function_with_type_hints(param1: str, param2: int) -> Dict[str, Any]:
    """
    Example function with type hints.
    """
    return {"param1": param1, "param2": param2}
```

## Testing

### Writing Tests

All new features and bug fixes should include tests. GigQ uses Python's built-in `unittest` framework:

```python
import unittest
from gigq import Job, JobQueue

class TestJobQueue(unittest.TestCase):
    def setUp(self):
        # Setup code
        self.queue = JobQueue(":memory:")

    def test_submit_job(self):
        job = Job(name="test", function=lambda: None)
        job_id = self.queue.submit(job)
        self.assertIsNotNone(job_id)

    def tearDown(self):
        # Cleanup code
        pass
```

### Running Tests

Run the entire test suite:

```bash
python -m unittest discover tests
```

Run a specific test:

```bash
python -m unittest tests.test_gigq.TestJobQueue.test_submit_job
```

## Documentation

### Updating Documentation

GigQ uses MkDocs with the Material theme for documentation. To update documentation:

1. Edit the markdown files in the `docs/` directory.
2. Preview your changes locally:
   ```bash
   mkdocs serve
   ```
3. Ensure your documentation changes are included in your pull request.

### Adding Examples

If you're adding a new feature, consider adding an example to the `examples/` directory to demonstrate its usage. Make sure to update the documentation to reference your example.

## Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests after the first line

## Releasing

The release process is handled by the project maintainers. If you're interested in helping with releases, please contact one of the maintainers.

## Getting Help

If you need help with contributing to GigQ, you can:

- Open an issue on GitHub
- Reach out to the project maintainers
- Check the documentation for guidance

## Thank You!

Thank you for contributing to GigQ! Your efforts help make this project better for everyone.
