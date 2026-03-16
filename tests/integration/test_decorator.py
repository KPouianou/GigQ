"""Integration tests for the @task decorator — end-to-end through queue and worker."""

import os
import tempfile
import time

from gigq import JobStatus, Workflow
from tests.integration.base import IntegrationTestBase
from tests.job_functions import (
    decorated_simple_job,
    decorated_step_one,
    decorated_step_two,
    decorated_step_three,
    decorated_retry_job,
)


class TestDecoratorBasic(IntegrationTestBase):
    """Test submitting and processing decorated tasks."""

    def test_submit_and_process(self):
        job_id = decorated_simple_job.submit(self.queue, value=42)

        self.worker.process_one()

        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)

        result = self.queue.get_result(job_id)
        self.assertEqual(result["result"], 84)

    def test_submit_with_defaults(self):
        job_id = decorated_simple_job.submit(self.queue, value=0)

        self.worker.process_one()

        status = self.queue.get_status(job_id)
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)
        self.assertEqual(self.queue.get_result(job_id)["result"], 0)


class TestDecoratorWorkflow(IntegrationTestBase):
    """Test workflows built with add_task."""

    def test_workflow_with_dependencies(self):
        wf = Workflow(name="decorator_pipeline")
        s1 = wf.add_task(decorated_step_one)
        s2 = wf.add_task(decorated_step_two, depends_on=[s1])
        s3 = wf.add_task(decorated_step_three, depends_on=[s2])

        job_ids = wf.submit_all(self.queue)
        self.assertEqual(len(job_ids), 3)

        self.worker.process_one()
        self.assertEqual(
            self.queue.get_status(job_ids[0])["status"], JobStatus.COMPLETED.value
        )
        self.assertEqual(
            self.queue.get_status(job_ids[1])["status"], JobStatus.PENDING.value
        )

        self.worker.process_one()
        self.assertEqual(
            self.queue.get_status(job_ids[1])["status"], JobStatus.COMPLETED.value
        )

        self.worker.process_one()
        self.assertEqual(
            self.queue.get_status(job_ids[2])["status"], JobStatus.COMPLETED.value
        )

        self.assertEqual(self.queue.get_result(job_ids[0])["step"], 1)
        self.assertEqual(self.queue.get_result(job_ids[1])["step"], 2)
        self.assertEqual(self.queue.get_result(job_ids[2])["step"], 3)


class TestDecoratorRetry(IntegrationTestBase):
    """Test retry behavior with decorated tasks."""

    def test_retry_succeeds_on_second_attempt(self):
        state_fd, state_db = tempfile.mkstemp(suffix=".db")
        try:
            job_id = decorated_retry_job.submit(
                self.queue, state_db=state_db, fail_times=1
            )

            # First attempt — should fail
            self.worker.process_one()
            status = self.queue.get_status(job_id)
            self.assertEqual(status["status"], JobStatus.PENDING.value)
            self.assertEqual(status["attempts"], 1)

            # Second attempt — should succeed
            self.worker.process_one()
            status = self.queue.get_status(job_id)
            self.assertEqual(status["status"], JobStatus.COMPLETED.value)

            result = self.queue.get_result(job_id)
            self.assertTrue(result["success"])
            self.assertEqual(result["attempts"], 2)
        finally:
            os.close(state_fd)
            os.unlink(state_db)
