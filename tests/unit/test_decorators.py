"""
Unit tests for the @task decorator and TaskWrapper class.
"""

import unittest
from unittest.mock import MagicMock

from gigq import task
from gigq.decorators import TaskWrapper
from gigq.job import Job

# --- Module-level functions for decoration tests ---


def sample_function(x, y=10):
    """A sample function for testing."""
    return x + y


def another_function(value):
    return {"result": value * 2}


@task
def bare_decorated(x):
    """Bare decorated docstring."""
    return x


@task()
def empty_parens_decorated(x):
    return x


@task(max_attempts=5, timeout=60, priority=10, description="test task")
def options_decorated(x):
    return x


@task(name="custom_name")
def named_decorated():
    pass


@task
def failing_decorated():
    raise ValueError("boom")


@task(priority=7, timeout=60, max_attempts=2)
def submit_test_func(url, format="json"):
    pass


@task(priority=3, timeout=120, max_attempts=5, description="desc")
def job_attrs_func(a, b):
    pass


@task(max_attempts=3, retry_delay=30)
def retry_delay_func(x):
    pass


class MyClass:
    @staticmethod
    def my_static():
        pass

    def my_method(self):
        pass


# --- Test classes ---


class TestTaskWrapping(unittest.TestCase):
    """Tests for decorator wrapping behavior."""

    def test_bare_decorator(self):
        self.assertIsInstance(bare_decorated, TaskWrapper)
        self.assertEqual(bare_decorated.__name__, "bare_decorated")
        self.assertEqual(bare_decorated.__doc__, "Bare decorated docstring.")
        self.assertEqual(bare_decorated.__module__, __name__)

    def test_empty_parens_decorator(self):
        self.assertIsInstance(empty_parens_decorated, TaskWrapper)
        self.assertEqual(empty_parens_decorated.__name__, "empty_parens_decorated")

    def test_decorator_with_options(self):
        self.assertIsInstance(options_decorated, TaskWrapper)
        self.assertEqual(options_decorated._options["max_attempts"], 5)
        self.assertEqual(options_decorated._options["timeout"], 60)
        self.assertEqual(options_decorated._options["priority"], 10)
        self.assertEqual(options_decorated._options["description"], "test task")

    def test_wrapped_attribute(self):
        self.assertTrue(hasattr(bare_decorated, "__wrapped__"))
        self.assertTrue(callable(bare_decorated.__wrapped__))
        self.assertEqual(bare_decorated.__wrapped__.__name__, "bare_decorated")
        self.assertNotIsInstance(bare_decorated.__wrapped__, TaskWrapper)

    def test_qualname_preserved(self):
        self.assertEqual(bare_decorated.__qualname__, "bare_decorated")

    def test_retry_delay_option(self):
        self.assertEqual(retry_delay_func._options["retry_delay"], 30)

    def test_default_options_match_job_defaults(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped._options["priority"], 0)
        self.assertEqual(wrapped._options["max_attempts"], 3)
        self.assertEqual(wrapped._options["timeout"], 300)
        self.assertEqual(wrapped._options["description"], "")
        self.assertEqual(wrapped._options["retry_delay"], 0)

    def test_default_name_from_function(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped._options["name"], "sample_function")

    def test_explicit_name(self):
        self.assertEqual(named_decorated._options["name"], "custom_name")

    def test_repr(self):
        wrapped = task(sample_function)
        r = repr(wrapped)
        self.assertIn("TaskWrapper", r)
        self.assertIn("sample_function", r)
        self.assertIn("priority", r)


class TestTaskCallPassthrough(unittest.TestCase):
    """Tests for direct call delegation."""

    def test_returns_result(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped(5, y=20), 25)

    def test_positional_args(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped(3, 7), 10)

    def test_keyword_args(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped(x=2, y=3), 5)

    def test_default_args(self):
        wrapped = task(sample_function)
        self.assertEqual(wrapped(5), 15)

    def test_exception_propagates(self):
        with self.assertRaises(ValueError) as ctx:
            failing_decorated()
        self.assertEqual(str(ctx.exception), "boom")


class TestTaskSubmit(unittest.TestCase):
    """Tests for .submit() behavior."""

    def test_returns_string_job_id(self):
        wrapped = task(sample_function)
        mock_queue = MagicMock()
        mock_queue.submit.return_value = "job-123"

        result = wrapped.submit(mock_queue, x=5)
        self.assertEqual(result, "job-123")

    def test_submit_creates_correct_job(self):
        mock_queue = MagicMock()
        mock_queue.submit.return_value = "job-456"

        submit_test_func.submit(mock_queue, url="https://example.com", format="csv")

        call_args = mock_queue.submit.call_args
        job = call_args[0][0]
        self.assertIsInstance(job, Job)
        self.assertEqual(job.name, "submit_test_func")
        self.assertEqual(job.params, {"url": "https://example.com", "format": "csv"})
        self.assertEqual(job.priority, 7)
        self.assertEqual(job.timeout, 60)
        self.assertEqual(job.max_attempts, 2)

    def test_submit_passes_unwrapped_function(self):
        wrapped = task(sample_function)
        mock_queue = MagicMock()
        mock_queue.submit.return_value = "id"

        wrapped.submit(mock_queue, x=1)

        job = mock_queue.submit.call_args[0][0]
        self.assertIs(job.function, sample_function)
        self.assertNotIsInstance(job.function, TaskWrapper)

    def test_two_submits_produce_different_ids(self):
        wrapped = task(sample_function)
        mock_queue = MagicMock()
        mock_queue.submit.side_effect = ["id-1", "id-2"]

        id1 = wrapped.submit(mock_queue, x=1)
        id2 = wrapped.submit(mock_queue, x=2)

        self.assertNotEqual(id1, id2)
        self.assertEqual(mock_queue.submit.call_count, 2)

        job1 = mock_queue.submit.call_args_list[0][0][0]
        job2 = mock_queue.submit.call_args_list[1][0][0]
        self.assertNotEqual(job1.id, job2.id)


class TestTaskToJob(unittest.TestCase):
    """Tests for .to_job() behavior."""

    def test_returns_job_instance(self):
        wrapped = task(sample_function)
        job = wrapped.to_job(x=5)
        self.assertIsInstance(job, Job)

    def test_job_attributes(self):
        job = job_attrs_func.to_job(a=1, b=2)
        self.assertEqual(job.name, "job_attrs_func")
        self.assertEqual(job.params, {"a": 1, "b": 2})
        self.assertEqual(job.priority, 3)
        self.assertEqual(job.timeout, 120)
        self.assertEqual(job.max_attempts, 5)
        self.assertEqual(job.description, "desc")
        self.assertIs(job.function, job_attrs_func.__wrapped__)

    def test_to_job_no_params(self):
        wrapped = task(sample_function)
        job = wrapped.to_job()
        self.assertEqual(job.params, {})

    def test_to_job_retry_delay(self):
        job = retry_delay_func.to_job(x=1)
        self.assertEqual(job.retry_delay, 30)

    def test_defaults_match_job_defaults(self):
        wrapped = task(sample_function)
        job = wrapped.to_job()
        self.assertEqual(job.priority, 0)
        self.assertEqual(job.max_attempts, 3)
        self.assertEqual(job.timeout, 300)
        self.assertEqual(job.description, "")
        self.assertEqual(job.retry_delay, 0)


class TestTaskValidation(unittest.TestCase):
    """Tests for decoration-time validation."""

    def test_rejects_lambda(self):
        with self.assertRaises(TypeError) as ctx:
            task(lambda x: x)
        self.assertIn("lambda", str(ctx.exception))

    def test_rejects_closure(self):
        def outer():
            def inner():
                pass

            return inner

        with self.assertRaises(TypeError) as ctx:
            task(outer())
        self.assertIn("closures or nested", str(ctx.exception))

    def test_rejects_non_callable(self):
        with self.assertRaises(TypeError) as ctx:
            task("not a function")
        self.assertIn("callable", str(ctx.exception))

    def test_rejects_object_missing_attributes(self):
        obj = MagicMock(spec=[])
        with self.assertRaises(TypeError):
            task(obj)

    def test_rejects_class_method_via_qualname(self):
        with self.assertRaises(TypeError) as ctx:
            task(MyClass.my_static)
        msg = str(ctx.exception)
        self.assertTrue("method" in msg or "closures" in msg)

    def test_rejects_double_wrapping(self):
        wrapped = task(sample_function)
        with self.assertRaises(TypeError) as ctx:
            task(wrapped)
        self.assertIn("twice", str(ctx.exception))

    def test_rejects_async_function(self):
        async def async_fn():
            pass

        with self.assertRaises(TypeError) as ctx:
            task(async_fn)
        self.assertIn("async", str(ctx.exception))

    def test_rejects_generator_function(self):
        def gen_fn():
            yield 1

        with self.assertRaises(TypeError) as ctx:
            task(gen_fn)
        self.assertIn("generator", str(ctx.exception))

    def test_rejects_unknown_option(self):
        with self.assertRaises(TypeError) as ctx:
            task(sample_function, max_attempt=5)
        self.assertIn("max_attempt", str(ctx.exception))
        self.assertIn("unexpected", str(ctx.exception))

    def test_rejects_multiple_unknown_options(self):
        with self.assertRaises(TypeError) as ctx:
            task(sample_function, foo=1, bar=2)
        self.assertIn("unexpected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
