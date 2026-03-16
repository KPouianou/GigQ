"""
Task decorator for GigQ.

Provides a @task decorator that turns plain functions into submittable jobs,
offering a convenient alternative to explicit Job() instantiation.
"""

import functools
import inspect
from typing import Any, Callable, Optional, Union

from .job import Job

_VALID_OPTIONS = frozenset(
    {"name", "priority", "max_attempts", "timeout", "description"}
)

_JOB_DEFAULTS = {
    "priority": 0,
    "max_attempts": 3,
    "timeout": 300,
    "description": "",
}


class TaskWrapper:
    """
    Wraps a function so it can be submitted as a GigQ job.

    Created by the @task decorator. The wrapped function remains directly
    callable and gains .submit() and .to_job() methods for queue interaction.
    """

    def __init__(self, fn: Callable, **options: Any) -> None:
        unknown = set(options) - _VALID_OPTIONS
        if unknown:
            raise TypeError(
                f"@task got unexpected option(s): {', '.join(sorted(unknown))}. "
                f"Valid options are: {', '.join(sorted(_VALID_OPTIONS))}"
            )

        self._validate(fn)

        self._options = {**_JOB_DEFAULTS, **options}
        if "name" not in self._options:
            self._options["name"] = fn.__name__

        functools.update_wrapper(self, fn)

    def _validate(self, fn: Callable) -> None:
        if isinstance(fn, TaskWrapper):
            raise TypeError("@task cannot be applied twice to the same function")
        if not callable(fn):
            raise TypeError(f"@task expected a callable, got {type(fn).__name__}")
        if not hasattr(fn, "__module__") or not hasattr(fn, "__name__"):
            raise TypeError(
                "@task can only decorate named functions with __module__ and __name__"
            )
        if "<lambda>" in fn.__name__:
            raise TypeError(
                "@task cannot decorate lambdas — use a named function instead"
            )
        if inspect.iscoroutinefunction(fn):
            raise TypeError("@task does not support async functions")
        if inspect.isgeneratorfunction(fn):
            raise TypeError("@task does not support generator functions")

        qualname = getattr(fn, "__qualname__", "")
        if ".<locals>." in qualname:
            raise TypeError(
                "@task cannot decorate closures or nested functions — "
                "the function must be defined at module level so the worker can import it"
            )
        elif "." in qualname:
            raise TypeError(
                "@task cannot decorate methods — "
                "the function must be defined at module level so the worker can import it"
            )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.__wrapped__(*args, **kwargs)

    def to_job(self, **params: Any) -> Job:
        """Create a Job from this decorated function without submitting it."""
        return Job(
            name=self._options["name"],
            function=self.__wrapped__,
            params=params,
            priority=self._options["priority"],
            max_attempts=self._options["max_attempts"],
            timeout=self._options["timeout"],
            description=self._options["description"],
        )

    def submit(self, queue: "Any", /, **params: Any) -> str:
        """Create a Job and submit it to the given queue.

        Args:
            queue: A JobQueue instance.
            **params: Keyword arguments to pass to the wrapped function.

        Returns:
            The job ID.
        """
        job = self.to_job(**params)
        return queue.submit(job)

    def __repr__(self) -> str:
        opts = ", ".join(
            f"{k}={v!r}" for k, v in sorted(self._options.items()) if k != "name"
        )
        return f"<TaskWrapper '{self._options['name']}' ({opts})>"


def task(
    fn: Optional[Callable] = None, **options: Any
) -> Union[TaskWrapper, Callable[[Callable], TaskWrapper]]:
    """Decorator that turns a function into a submittable GigQ task.

    Can be used with or without arguments::

        @task
        def my_job(x):
            return x * 2

        @task(timeout=60, max_attempts=5)
        def my_job(x):
            return x * 2

    Job options (priority, max_attempts, timeout, description, name) are
    fixed at decoration time. Use .submit(queue, **params) to enqueue.
    """
    if fn is not None:
        return TaskWrapper(fn, **options)

    def decorator(fn: Callable) -> TaskWrapper:
        return TaskWrapper(fn, **options)

    return decorator
