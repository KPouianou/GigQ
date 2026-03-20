# MCP Server

[GigQ](../index.md) can be driven through the [Model Context Protocol](https://modelcontextprotocol.io) via the **`gigq-mcp`** package in the repository (`mcp_server/`). It exposes tools for submitting jobs and workflows, inspecting queue state, and reading results—intended for AI agents in Claude Desktop, Cursor, and other MCP hosts.

!!! warning "Workers are separate processes"

    This server only talks to SQLite. **Jobs do not run until a GigQ worker** is started against the same database file, e.g. `gigq --db /path/to/db worker --concurrency 4`. Tool responses remind you of this and include an example command.

## Install

```bash
pip install gigq-mcp
```

From a source checkout:

```bash
pip install -e .
pip install -e mcp_server
```

## Configuration

**Database path** (first match):

1. `db_path` on an individual tool call  
2. Environment variable **`GIGQ_DB_PATH`**  
3. Default **`gigq.db`** in the server process working directory  

Workers and the MCP server must use the **same** database path.

## Run

```bash
gigq-mcp
# or: python -m gigq_mcp.server
```

Default transport is **stdio**, which matches typical desktop MCP clients.

### Claude Desktop

Add a server entry (macOS config path: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gigq": {
      "command": "gigq-mcp",
      "env": {
        "GIGQ_DB_PATH": "/absolute/path/to/demo.db"
      }
    }
  }
}
```

Use `python` + `-m gigq_mcp.server` if `gigq-mcp` is not on `PATH`. Restart Claude Desktop after editing.

### Cursor

Configure the same `command` / `args` / `env` under **Settings → MCP**.

## Tools

| Tool | Role |
|------|------|
| `gigq_submit_job` | Submit a single job by import path and parameters. |
| `gigq_get_job_status` | Full status payload for one job. |
| `gigq_get_job_result` | Result value when completed. |
| `gigq_list_jobs` | List jobs with optional status filter. |
| `gigq_queue_stats` | Counts plus hints when pending jobs are not being run. |
| `gigq_cancel_job` | Cancel a pending job. |
| `gigq_requeue_job` | Requeue failed / timeout / cancelled jobs. |
| `gigq_submit_workflow` | Multi-step `@task` DAG (fan-out, fan-in, chains). |

There is **no** tool to start a worker; start workers from the shell or your process manager.

## Limitations (same as GigQ)

- Single-machine queue; not a distributed broker.  
- Synchronous Python callables only; workers import functions by module path.  
- Return values must be JSON-serializable.  

## Further reading

- Package README: [`mcp_server/README.md`](https://github.com/kpouianou/gigq/blob/main/mcp_server/README.md)  
- Smoke test: `python mcp_server/test_smoke.py -v`  
