"""
Tests for thread-safety of the sync scheduler.
"""

from __future__ import annotations

import logging
import threading
import time

from faster_cron import FasterCron


def test_add_task_while_running():
    """Adding a task while the scheduler is running should not crash."""
    cron = FasterCron(log_level=logging.CRITICAL, wait_on_exit=False)
    results = []

    def task_a():
        results.append("a")

    def task_b():
        results.append("b")

    cron.add_task("* * * * * *", task_a)
    cron.start(wait_on_exit=False)
    time.sleep(0.3)

    # Add task while running
    cron.add_task("* * * * * *", task_b)
    time.sleep(0.5)
    cron.stop()

    assert "task_a" not in results  # task_a is the function name, not the result
    assert len(results) > 0


def test_remove_task_while_running():
    """Removing a task while the scheduler is running should not crash."""
    cron = FasterCron(log_level=logging.CRITICAL, wait_on_exit=False)
    counter = {"value": 0}

    def my_task():
        counter["value"] += 1

    cron.add_task("* * * * * *", my_task)
    cron.start(wait_on_exit=False)
    time.sleep(1.0)

    assert cron.remove_task("my_task") is True
    time.sleep(0.3)
    cron.stop()

    # Should have run at least once before removal
    assert counter["value"] >= 1


def test_update_task_while_running():
    """Updating a task expression while running should not crash."""
    cron = FasterCron(log_level=logging.CRITICAL, wait_on_exit=False)

    def my_task():
        pass

    cron.add_task("* * * * * *", my_task)
    cron.start(wait_on_exit=False)
    time.sleep(0.2)

    updated = cron.update_task("my_task", expression="*/2 * * * * *")
    assert updated is not None
    assert updated.expression == "*/2 * * * * *"

    cron.stop()


def test_multiple_add_remove_no_deadlock():
    """Rapid add/remove cycles should not deadlock."""
    cron = FasterCron(log_level=logging.CRITICAL, wait_on_exit=False)

    def dummy():
        pass

    cron.start(wait_on_exit=False)

    for i in range(20):
        name = f"task_{i}"
        cron.add_task("* * * * * *", dummy)
        cron.remove_task("dummy")

    cron.stop()


def test_execution_history_is_thread_safe():
    """Multiple concurrent task completions should not corrupt history."""
    cron = FasterCron(log_level=logging.CRITICAL, wait_on_exit=False)
    lock = threading.Lock()
    completed = {"count": 0}

    def concurrent_task():
        with lock:
            completed["count"] += 1

    # Add many tasks that will all fire at once
    for i in range(10):

        def make_task(idx=i):
            def task():
                concurrent_task()

            task.__name__ = f"task_{idx}"
            return task

        cron.add_task("* * * * * *", make_task())

    cron.start(wait_on_exit=False)
    time.sleep(1.0)
    cron.stop()

    # All tasks should have executed
    assert completed["count"] >= 10
    # History should have records for all executions
    assert len(cron.execution_history) >= 10
