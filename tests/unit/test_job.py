"""
Unit tests for the Job class in GigQ.
"""

import unittest
from gigq import Job, JobStatus


def example_job_function(value=0):
    """Example job function for testing."""
    return {"result": value * 2}


def failing_job_function():
    """Example job function that fails."""
    raise ValueError("This job is designed to fail")


class TestJob(unittest.TestCase):
    """Tests for the Job class."""

    def test_job_initialization(self):
        """Test that a job can be initialized with the correct parameters."""
        job = Job(
            name="test_job",
            function=example_job_function,
            params={"value": 42},
            priority=5,
            dependencies=["job1", "job2"],
            max_attempts=2,
            timeout=120,
            description="A test job",
        )

        self.assertEqual(job.name, "test_job")
        self.assertEqual(job.function, example_job_function)
        self.assertEqual(job.params, {"value": 42})
        self.assertEqual(job.priority, 5)
        self.assertEqual(job.dependencies, ["job1", "job2"])
        self.assertEqual(job.max_attempts, 2)
        self.assertEqual(job.timeout, 120)
        self.assertEqual(job.description, "A test job")
        self.assertIsNone(job.pass_parent_results)
        self.assertTrue(job.id)  # ID should be generated

    def test_job_pass_parent_results(self):
        job = Job(
            name="p",
            function=example_job_function,
            pass_parent_results=True,
        )
        self.assertTrue(job.pass_parent_results)

    def test_job_default_values(self):
        """Test default values for job parameters."""
        job = Job(name="simple_job", function=example_job_function)

        self.assertEqual(job.params, {})
        self.assertEqual(job.priority, 0)
        self.assertEqual(job.dependencies, [])
        self.assertEqual(job.max_attempts, 3)
        self.assertEqual(job.timeout, 300)
        self.assertEqual(job.description, "")

    def test_job_unique_id(self):
        """Test that each job gets a unique ID."""
        job1 = Job(name="job1", function=example_job_function)
        job2 = Job(name="job2", function=example_job_function)

        self.assertNotEqual(job1.id, job2.id)


if __name__ == "__main__":
    unittest.main()
