# Installation

This guide covers various ways to install GigQ and set up your environment.

## Prerequisites

GigQ requires:

- Python 3.9 or newer
- SQLite 3.8.3 or newer (usually included with Python)

## Standard Installation

The simplest way to install GigQ is via pip:

```bash
pip install gigq
```

This will install the latest stable version of GigQ from PyPI with minimal dependencies.

## Installation with Extra Features

GigQ uses "extras" to manage optional dependencies. You can install GigQ with additional dependencies for specific features:

```bash
# Install with dependencies for running examples
pip install "gigq[examples]"

# Install with dependencies for building documentation
pip install "gigq[docs]"

# Install with dependencies for development
pip install "gigq[dev]"

# Install with all extra dependencies
pip install "gigq[examples,docs,dev]"
```

## Installation from Source

To install the latest development version from GitHub:

```bash
git clone https://github.com/kpouianou/gigq.git
cd gigq
pip install -e .
```

The `-e` flag installs the package in "editable" mode, which is useful for development.

For development with all dependencies:

```bash
pip install -e ".[examples,docs,dev]"
```

## Installation in a Virtual Environment

It's a good practice to install GigQ in a virtual environment to avoid conflicts with other packages. Here's how to do it with `venv`:

```bash
# Create a virtual environment
python -m venv gigq-env

# Activate the virtual environment
# On Windows:
gigq-env\Scripts\activate
# On macOS/Linux:
source gigq-env/bin/activate

# Install GigQ
pip install gigq
```

## Docker Installation

You can also run GigQ in a Docker container. Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install GigQ
RUN pip install gigq

# Copy your application code
COPY . .

# Command to run when the container starts
CMD ["python", "your_script.py"]
```

Then build and run the container:

```bash
docker build -t gigq-app .
docker run gigq-app
```

## Verifying the Installation

After installation, you can verify that GigQ is installed correctly by running:

```bash
python -c "import gigq; print(gigq.__version__)"
```

You should see the version number of GigQ printed.

## Dependencies

GigQ has the following dependency categories:

### Build Dependencies

- setuptools (>=42)
- wheel

### Core Dependencies

- Python 3.9+

### Example Dependencies [examples]

- pandas
- requests
- schedule

### Documentation Dependencies [docs]

- mkdocs-material
- pymdown-extensions
- mkdocstrings[python]
- mkdocs-git-revision-date-localized-plugin
- mkdocs-minify-plugin
- mike

### Development Dependencies [dev]

- pytest
- flake8
- coverage
- mypy

## System-specific Notes

### Windows

On Windows, ensure that the SQLite database file is accessible to all processes that need it, especially if you're running workers in separate processes or services.

### macOS

No special configuration is needed for macOS.

### Linux

On Linux, you might need to install the `sqlite3` package if it's not already installed:

```bash
# Debian/Ubuntu
sudo apt-get install sqlite3

# RHEL/CentOS/Fedora
sudo yum install sqlite
```

## Troubleshooting

If you encounter issues during installation:

1. **SQLite version issues**: Ensure your SQLite version is 3.8.3 or newer:

   ```bash
   python -c "import sqlite3; print(sqlite3.sqlite_version)"
   ```

2. **Permission errors**: If you get permission errors, try installing with:

   ```bash
   pip install --user gigq
   ```

3. **Dependency conflicts**: Use a virtual environment as described above.

4. **Import errors after installation**: Make sure your Python path is set correctly:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

## Next Steps

Now that you have GigQ installed, check out the [Quick Start Guide](quick-start.md) to begin using it.
