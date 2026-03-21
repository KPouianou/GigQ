# GigQ MCP Server

[Model Context Protocol](https://modelcontextprotocol.io) server that exposes [GigQ](https://github.com/kpouianou/gigq): submit jobs and workflows to a SQLite-backed queue, poll status, and read results—so AI agents can orchestrate work without embedding queue logic in prompts.

**Important:** GigQ only **stores** jobs until a **worker** process runs. This server does not start workers. If you submit jobs and nothing happens, start a worker in a separate terminal (see below).

## What it does

- **Single jobs:** enqueue a callable by import path (`module.submodule.function`) with JSON-serializable parameters.
- **Workflows:** submit a DAG of `@task` functions in one call—fan-out, fan-in, and linear chains—with `depends_on` and optional `pass_parent_results`.
- **Observability:** status, list, aggregate stats (with hints when jobs are pending but nothing is running).

Constraints match GigQ: **single machine**, **synchronous** Python callables, functions must be **importable at module level** (workers load them by path), and return values must be **JSON-serializable**.

## Install

From PyPI (when published):

```bash
pip install gigq-mcp
```

From a GigQ repo checkout (editable):

```bash
pip install -e .
pip install -e mcp_server
```

Requires Python 3.10+ and the `mcp` package (pulled in by `gigq-mcp`).

## Database path

How the SQLite file is chosen (first match wins):

1. **`db_path`** argument on a tool (per-call override).
2. Environment variable **`GIGQ_DB_PATH`** (recommended for Claude Desktop / Cursor: set once in the server config).
3. Default **`./gigq.db`** in the process working directory.

Use the **same path** for workers and for this server.

## Run the server (stdio)

```bash
gigq-mcp
# or
python -m gigq_mcp.server
```

Stdio is the default transport and matches most desktop MCP clients.

### Claude Desktop

1. Install the package (see above) into an environment you can reference from the config.
2. Edit Claude Desktop MCP config (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`) and add a server entry, for example:

```json
{
  "mcpServers": {
    "gigq": {
      "command": "gigq-mcp",
      "env": {
        "GIGQ_DB_PATH": "/absolute/path/to/your/demo.db"
      }
    }
  }
}
```

If `gigq-mcp` is not on `PATH`, use the full path to the interpreter and module form:

```json
{
  "mcpServers": {
    "gigq": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "gigq_mcp.server"],
      "env": {
        "GIGQ_DB_PATH": "/absolute/path/to/your/demo.db"
      }
    }
  }
}
```

Restart Claude Desktop after changes.

### Cursor

Add an MCP server in **Cursor Settings → MCP** with the same `command` / `args` / `env` pattern as above. Point `GIGQ_DB_PATH` at your queue database.

### `uv run` (optional)

If you use [uv](https://docs.astral.sh/uv/):

```bash
cd /path/to/gigq/mcp_server
uv run gigq-mcp
```

You can also use the MCP SDK’s installer when developing:

```bash
uv run mcp install path/to/gigq/mcp_server/gigq_mcp/server.py
```

(Exact `mcp` CLI flags follow the [Python SDK docs](https://github.com/modelcontextprotocol/python-sdk).)

## Tools

| Tool                   | Purpose                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------- |
| `gigq_submit_job`      | Enqueue one job (`function_path`, `name`, `params`, optional priority/timeout/…).  |
| `gigq_get_job_status`  | Full job record (status, error, executions, …).                                    |
| `gigq_get_job_result`  | Deserialized return value when `status == completed`.                              |
| `gigq_list_jobs`       | List jobs, optional status filter.                                                 |
| `gigq_queue_stats`     | Per-status counts + interpretation when pending jobs are not running.              |
| `gigq_cancel_job`      | Cancel a **pending** job.                                                          |
| `gigq_requeue_job`     | Requeue failed / timeout / cancelled jobs.                                         |
| `gigq_submit_workflow` | Multi-step `@task` DAG (`steps` with `id`, `function`, `params`, `depends_on`, …). |

Every successful submit response includes **`worker_command_example`** (e.g. `gigq --db … worker --concurrency 4`). **`gigq_queue_stats`** highlights when **`pending_without_runner`** is likely (pending &gt; 0 and running = 0).

There is **no** “start worker” tool—workers are long-lived CLI processes.

## Workers (required for execution)

After submitting jobs, start one or more workers against the **same** database:

```bash
gigq --db /absolute/path/to/demo.db worker --concurrency 4
```

The worker must be able to **import** the same module paths you used in submissions (same `PYTHONPATH`, installed packages, and repo layout).

## Example agent workflow (manual test)

1. Pick a database path, e.g. `/tmp/gigq-demo.db`, and set `GIGQ_DB_PATH` to it in the MCP config.
2. In a terminal, start a worker:  
   `gigq --db /tmp/gigq-demo.db worker --concurrency 4`
3. In Claude, ask the model to:
   - Submit a job using a function from the repo, e.g. `examples.parallel_tasks.hash_block` with params `{"block_id": 0}` (requires that package on `PYTHONPATH` or an installed `examples` package).
   - Call `gigq_queue_stats` and `gigq_get_job_status` until work completes.
   - Call `gigq_get_job_result` for the job id.
   - Submit a small workflow with `gigq_submit_workflow` (two parallel `@task` steps, then a merge step with `depends_on`).
4. Stop the worker with Ctrl+C when done.

## Automated smoke test

From the repo root (with `gigq` and `gigq-mcp` installed):

```bash
python mcp_server/test_smoke.py -v
```

This exercises each handler with a temporary database—no MCP client required.

## Documentation

Full documentation also lives on the [GigQ docs site](https://kpouianou.github.io/GigQ/) under **Integrations → MCP Server**.
