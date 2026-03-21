"""Tests for retry delay functionality."""

import os
import tempfile
import sqlite3
from datetime import datetime, timedelta
from gigq import Job, JobStatus
from tests.integration.base import IntegrationTestBase
from tests.job_functions import retry_job, failing_job


class TestRetryDelay(IntegrationTestBase):
    """Test that retry_delay prevents immediate re-pickup of failed jobs."""

    def test_retry_delay_sets_retry_after(self):
        """When a job with retry_delay fails, retry_after is set in the DB."""
        job = Job(
            name="delayed_retry",
            function=failing_job,
            max_attempts=3,
            retry_delay=60,
        )
        job_id = self.queue.submit(job)

        # Process once — job fails, should be reset to pending with retry_after
        self.worker.process_one()

        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 1)

        # Check retry_after is set in the DB
        from gigq.db_utils import get_connection

        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT retry_after FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row["retry_after"])

        # retry_after should be roughly 60 seconds in the future
        retry_after = datetime.fromisoformat(row["retry_after"])
        now = datetime.now()
        self.assertGreater(retry_after, now)
        self.assertLess(retry_after, now + timedelta(seconds=120))

    def test_retry_delay_prevents_immediate_pickup(self):
        """A job with retry_delay>0 should NOT be claimable immediately after failure."""
        job = Job(
            name="delayed_retry",
            function=failing_job,
            max_attempts=3,
            retry_delay=300,  # 5 minutes — way longer than the test
        )
        job_id = self.queue.submit(job)

        # First attempt — job fails
        self.worker.process_one()

        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 1)

        # Second attempt — should NOT be picked up because retry_after is in the future
        processed = self.worker.process_one()
        self.assertFalse(processed)

        # Status should still be pending with 1 attempt
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 1)

    def test_zero_retry_delay_allows_immediate_pickup(self):
        """A job with retry_delay=0 (default) is claimable immediately after failure."""
        _, tracker_db_path = tempfile.mkstemp(suffix=".db")
        os.close(_)
        self.addCleanup(
            lambda: os.path.exists(tracker_db_path) and os.unlink(tracker_db_path)
        )

        conn = sqlite3.connect(tracker_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS attempts (job_id TEXT PRIMARY KEY, count INTEGER)"
        )
        conn.commit()
        conn.close()

        job = Job(
            name="immediate_retry",
            function=retry_job,
            params={"job_id": "test1", "fail_times": 1, "state_db": tracker_db_path},
            max_attempts=3,
            retry_delay=0,
        )
        job_id = self.queue.submit(job)

        # First attempt — fails
        self.worker.process_one()
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)

        # Second attempt — should succeed immediately (no delay)
        self.worker.process_one()
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)

    def test_retry_delay_claimable_after_wait(self):
        """After retry_after passes, the job becomes claimable again."""
        job = Job(
            name="short_delay_retry",
            function=failing_job,
            max_attempts=3,
            retry_delay=1,  # 1 second delay
        )
        job_id = self.queue.submit(job)

        # First attempt — fails
        self.worker.process_one()
        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.PENDING.value)
        self.assertEqual(status["attempts"], 1)

        # Immediately — should NOT pick up
        processed = self.worker.process_one()
        self.assertFalse(processed)

        # Wait for the delay to pass
        import time

        time.sleep(1.1)

        # Now the job should be claimable
        processed = self.worker.process_one()
        self.assertTrue(processed)

        status = self.queue.get_status(job_id)
        self.assertEqual(status["attempts"], 2)

    def test_retry_delay_stored_in_db(self):
        """retry_delay value is persisted in the database."""
        job = Job(
            name="stored_delay",
            function=failing_job,
            max_attempts=1,
            retry_delay=45,
        )
        job_id = self.queue.submit(job)

        from gigq.db_utils import get_connection

        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT retry_delay FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        self.assertEqual(row["retry_delay"], 45)

    def test_default_retry_delay_zero(self):
        """Jobs without retry_delay default to 0."""
        job = Job(
            name="default_delay",
            function=failing_job,
            max_attempts=1,
        )
        job_id = self.queue.submit(job)

        from gigq.db_utils import get_connection

        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT retry_delay FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        self.assertEqual(row["retry_delay"], 0)
