"""Integration tests for passing parent job results into dependent jobs."""

import time
import unittest

from gigq import Job, JobStatus, Workflow

from tests.integration.base import IntegrationTestBase
from tests.job_functions import (
    no_parent_results_child,
    workflow_fetch_tag,
    workflow_merge_parent_results,
)


class TestWorkflowParentResults(IntegrationTestBase):
    """Fan-in workflows receive parent outputs via ``parent_results``."""

    def test_fan_in_parent_results_injected(self):
        wf = Workflow("fan_in")
        j1 = wf.add_task(workflow_fetch_tag, params={"tag": "a"})
        j2 = wf.add_task(workflow_fetch_tag, params={"tag": "b"})
        j3 = wf.add_task(
            workflow_merge_parent_results,
            depends_on=[j1, j2],
        )
        wf.submit_all(self.queue)

        self.start_worker()

        timeout = time.time() + 15
        while time.time() < timeout:
            st = self.queue.get_status(j3.id)
            if st.get("status") == JobStatus.COMPLETED.value:
                break
            time.sleep(0.05)
        self.stop_worker()

        merge_status = self.queue.get_status(j3.id)
        self.assertEqual(merge_status["status"], JobStatus.COMPLETED.value)
        self.assertEqual(merge_status["result"]["tags"], ["a", "b"])

    def test_explicit_pass_parent_results_false_skips_injection(self):
        """Job with ``pass_parent_results=False`` does not receive ``parent_results``."""
        wf = Workflow("no_inject")
        parent = wf.add_task(workflow_fetch_tag, params={"tag": "x"})
        child = Job(
            name="child",
            function=no_parent_results_child,
            params={},
            pass_parent_results=False,
        )
        wf.add_job(child, depends_on=[parent])
        wf.submit_all(self.queue)

        self.start_worker()
        timeout = time.time() + 15
        while time.time() < timeout:
            st = self.queue.get_status(child.id)
            if st.get("status") == JobStatus.COMPLETED.value:
                break
            time.sleep(0.05)
        self.stop_worker()

        self.assertEqual(
            self.queue.get_status(child.id)["status"], JobStatus.COMPLETED.value
        )


if __name__ == "__main__":
    unittest.main()
