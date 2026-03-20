"""
Smoke-test GigQ MCP handlers without an MCP client.

Uses a temporary SQLite DB and import paths under ``gigq_mcp._smoke_fixtures``.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from gigq_mcp import handlers
from gigq_mcp._smoke_fixtures import plain_double


class TestMcpSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self._fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._fd)
        self.addCleanup(
            lambda: os.unlink(self.db_path) if os.path.exists(self.db_path) else None
        )

    def test_submit_status_list_stats_result_cancel_requeue_path(self) -> None:
        plain_path = f"{plain_double.__module__}.{plain_double.__name__}"

        r = handlers.submit_job(
            plain_path,
            name="smoke",
            params={"x": 21},
            db_path=self.db_path,
        )
        self.assertTrue(r["success"])
        job_id = r["job_id"]
        self.assertIn("worker_command_example", r)

        st = handlers.get_job_status(job_id, db_path=self.db_path)
        self.assertTrue(st["success"])
        self.assertEqual(st["status"]["status"], "pending")

        lj = handlers.list_jobs(db_path=self.db_path, limit=10)
        self.assertTrue(lj["success"])
        self.assertGreaterEqual(lj["count"], 1)

        qs = handlers.queue_stats(db_path=self.db_path)
        self.assertTrue(qs["success"])
        self.assertTrue(qs["signals"]["pending_without_runner"])
        self.assertIn("interpretation", qs)

        gr = handlers.get_job_result(job_id, db_path=self.db_path)
        self.assertTrue(gr["success"])
        self.assertIsNone(gr["result"])

        c = handlers.cancel_job(job_id, db_path=self.db_path)
        self.assertTrue(c["success"])

        rq = handlers.requeue_job(job_id, db_path=self.db_path)
        self.assertTrue(rq["success"])

    def test_workflow_fan_in(self) -> None:
        mod = "gigq_mcp._smoke_fixtures"
        r = handlers.submit_workflow(
            "smoke_wf",
            steps=[
                {
                    "id": "a",
                    "function": f"{mod}.smoke_fan_item",
                    "params": {"i": 1},
                },
                {
                    "id": "b",
                    "function": f"{mod}.smoke_fan_item",
                    "params": {"i": 2},
                },
                {
                    "id": "m",
                    "function": f"{mod}.smoke_merge",
                    "depends_on": ["a", "b"],
                },
            ],
            db_path=self.db_path,
        )
        self.assertTrue(r["success"], r)
        self.assertEqual(len(r["submitted_job_ids"]), 3)
        self.assertEqual(len(r["step_id_to_job_id"]), 3)

    def test_errors(self) -> None:
        r = handlers.get_job_status(
            "00000000-0000-0000-0000-000000000000", db_path=self.db_path
        )
        self.assertFalse(r["success"])

        r2 = handlers.submit_job("not_a_valid_path", name="x", db_path=self.db_path)
        self.assertFalse(r2["success"])


if __name__ == "__main__":
    unittest.main()
