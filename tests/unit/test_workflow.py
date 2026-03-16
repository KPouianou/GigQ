"""
Unit tests for the Workflow class in GigQ.
"""

import os
import tempfile
import unittest
from gigq import Job, JobQueue, Worker, Workflow, JobStatus, task


def example_job_function(value=0):
    """Example job function for testing."""
    return {"result": value * 2}


@task(timeout=30)
def decorated_example(value=0):
    """Decorated example for add_task tests."""
    return {"result": value * 2}


@task
def decorated_step_a():
    return "a_done"


@task
def decorated_step_b():
    return "b_done"


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
        workflow = Workflow("test_workflow")

        job1 = Job(name="job1", function=example_job_function)
        job2 = Job(name="job2", function=example_job_function)
        job3 = Job(name="job3", function=example_job_function)

        workflow.add_job(job1)
        workflow.add_job(job2, depends_on=[job1])
        workflow.add_job(job3, depends_on=[job1, job2])

        self.assertEqual(len(job1.dependencies), 0)
        self.assertEqual(len(job2.dependencies), 1)
        self.assertEqual(len(job3.dependencies), 2)
        self.assertEqual(job2.dependencies[0], job1.id)
        self.assertTrue(job1.id in job3.dependencies)
        self.assertTrue(job2.id in job3.dependencies)

    def test_workflow_submission(self):
        """Test that a workflow can be submitted."""
        workflow = Workflow("test_workflow")

        job1 = Job(name="job1", function=example_job_function)
        job2 = Job(name="job2", function=example_job_function, params={"value": 1})
        job3 = Job(name="job3", function=example_job_function, params={"value": 2})

        workflow.add_job(job1)
        workflow.add_job(job2, depends_on=[job1])
        workflow.add_job(job3, depends_on=[job2])

        job_ids = workflow.submit_all(self.queue)

        self.assertEqual(len(job_ids), 3)

        # Check that all jobs are in the queue
        for job_id in job_ids:
            status = self.queue.get_status(job_id)
            self.assertTrue(status["exists"])
            self.assertEqual(status["status"], JobStatus.PENDING.value)

        # Process first job
        worker = Worker(self.db_path)
        worker.process_one()

        # Check that first job is completed
        status = self.queue.get_status(job_ids[0])
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)

        # Process second job
        worker.process_one()

        # Check that second job is completed
        status = self.queue.get_status(job_ids[1])
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)

        # Process third job
        worker.process_one()

        # Check that third job is completed
        status = self.queue.get_status(job_ids[2])
        self.assertEqual(status["status"], JobStatus.COMPLETED.value)
        self.assertEqual(status["result"]["result"], 4)  # 2 * 2

    def test_complex_workflow(self):
        """Test a more complex workflow with multiple dependency relationships."""
        workflow = Workflow("complex_workflow")

        # Create jobs
        job_a = Job(name="job_a", function=example_job_function)
        job_b = Job(name="job_b", function=example_job_function)
        job_c = Job(name="job_c", function=example_job_function)
        job_d = Job(name="job_d", function=example_job_function)
        job_e = Job(name="job_e", function=example_job_function)

        # Set up dependencies: A -> B, C; B -> D; C -> D; D -> E
        workflow.add_job(job_a)
        workflow.add_job(job_b, depends_on=[job_a])
        workflow.add_job(job_c, depends_on=[job_a])
        workflow.add_job(job_d, depends_on=[job_b, job_c])
        workflow.add_job(job_e, depends_on=[job_d])

        # Submit all jobs
        job_ids = workflow.submit_all(self.queue)
        self.assertEqual(len(job_ids), 5)

        # Check that dependencies are correctly set in the database
        for i, job in enumerate([job_a, job_b, job_c, job_d, job_e]):
            status = self.queue.get_status(job_ids[i])
            if job.dependencies:
                self.assertEqual(len(status["dependencies"]), len(job.dependencies))
            else:
                self.assertEqual(status["dependencies"], [])

    def test_empty_workflow(self):
        """Test submitting an empty workflow."""
        workflow = Workflow("empty_workflow")
        job_ids = workflow.submit_all(self.queue)
        self.assertEqual(len(job_ids), 0)

    def test_workflow_name(self):
        """Test that workflow name is set correctly."""
        workflow = Workflow("test_name_workflow")
        self.assertEqual(workflow.name, "test_name_workflow")

    # In tests/unit/test_workflow.py
    def test_job_in_multiple_workflows(self):
        """Test adding the same job to multiple workflows."""
        workflow1 = Workflow("workflow1")
        workflow2 = Workflow("workflow2")

        # Create two separate job objects with same parameters but different IDs
        job1 = Job(name="shared_job", function=example_job_function)
        job2 = Job(name="shared_job", function=example_job_function)

        workflow1.add_job(job1)
        workflow2.add_job(job2)

        # Submit to both queues
        job_ids1 = workflow1.submit_all(self.queue)
        self.assertEqual(len(job_ids1), 1)

        # Submit second workflow
        job_ids2 = workflow2.submit_all(self.queue)
        self.assertEqual(len(job_ids2), 1)

        # The job IDs should be different
        self.assertNotEqual(job_ids1[0], job_ids2[0])


class TestWorkflowAddTask(unittest.TestCase):
    """Tests for the Workflow.add_task() method."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.queue = JobQueue(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_add_task_creates_job(self):
        wf = Workflow("test")
        job = wf.add_task(decorated_example, params={"value": 42})
        self.assertIsInstance(job, Job)
        self.assertEqual(job.name, "decorated_example")
        self.assertEqual(job.params, {"value": 42})
        self.assertEqual(job.timeout, 30)

    def test_add_task_dependencies(self):
        wf = Workflow("test")
        a = wf.add_task(decorated_step_a)
        b = wf.add_task(decorated_step_b, depends_on=[a])
        self.assertEqual(b.dependencies, [a.id])

    def test_add_task_no_params(self):
        wf = Workflow("test")
        job = wf.add_task(decorated_step_a)
        self.assertEqual(job.params, {})

    def test_add_task_rejects_plain_function(self):
        wf = Workflow("test")
        with self.assertRaises(TypeError) as ctx:
            wf.add_task(example_job_function)
        self.assertIn("@task", str(ctx.exception))

    def test_add_task_submit_all(self):
        wf = Workflow("test")
        a = wf.add_task(decorated_step_a)
        b = wf.add_task(decorated_step_b, depends_on=[a])
        job_ids = wf.submit_all(self.queue)
        self.assertEqual(len(job_ids), 2)
        for job_id in job_ids:
            status = self.queue.get_status(job_id)
            self.assertTrue(status["exists"])
            self.assertEqual(status["status"], JobStatus.PENDING.value)


if __name__ == "__main__":
    unittest.main()
