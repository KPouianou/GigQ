"""Module-level tasks for MCP smoke tests (importable by path)."""

from gigq import task


def plain_double(x: int) -> int:
    """Plain callable for single-job submit tests."""
    return x * 2


@task(timeout=10)
def smoke_fan_item(i: int) -> dict:
    return {"i": i}


@task(timeout=10)
def smoke_merge(parent_results) -> dict:
    return {"keys": sorted(parent_results.keys())}
