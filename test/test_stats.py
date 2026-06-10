"""
Tests for SchedulerStats via get_stats().
"""

from __future__ import annotations

import datetime
import logging

from faster_cron import AsyncFasterCron, FasterCron, SchedulerStats, TaskState
from faster_cron.models import ExecutionRecord


def test_stats_empty_scheduler():
    """Empty scheduler should have zero stats."""
    cron = FasterCron(log_level=logging.CRITICAL)
    stats = cron.get_stats()

    assert stats.total_tasks == 0
    assert stats.active_tasks == 0
    assert stats.paused_tasks == 0
    assert stats.disabled_tasks == 0
    assert stats.total_executions == 0
    assert stats.successful_executions == 0
    assert stats.failed_executions == 0
    assert stats.error_history_size == 0
    assert stats.success_rate == 100.0


def test_stats_with_mixed_task_states():
    """Stats should correctly count tasks in different states."""
    cron = FasterCron(log_level=logging.CRITICAL)

    def task_a():
        pass

    def task_b():
        pass

    def task_c():
        pass

    cron.add_task("* * * * * *", task_a)
    cron.add_task("* * * * * *", task_b)
    cron.add_task("* * * * * *", task_c)

    cron.pause_task("task_b")
    cron.disable_task("task_c")

    stats = cron.get_stats()
    assert stats.total_tasks == 3
    assert stats.active_tasks == 1  # task_a is PENDING
    assert stats.paused_tasks == 1  # task_b
    assert stats.disabled_tasks == 1  # task_c


def test_stats_success_rate_calculation():
    """Success rate should be correctly computed."""
    cron = FasterCron(log_level=logging.CRITICAL)

    now = datetime.datetime.now()
    # Simulate 3 successful and 1 failed execution
    for _ in range(3):
        record = ExecutionRecord(
            task_name="test",
            scheduled_at=now,
            started_at=now,
            finished_at=now,
            success=True,
        )
        cron.execution_history.append(record)

    failed = ExecutionRecord(
        task_name="test",
        scheduled_at=now,
        started_at=now,
        finished_at=now,
        success=False,
        error_message="boom",
    )
    cron.execution_history.append(failed)
    cron.error_history.append(failed)

    stats = cron.get_stats()
    assert stats.total_executions == 4
    assert stats.successful_executions == 3
    assert stats.failed_executions == 1
    assert stats.success_rate == 75.0


def test_stats_success_rate_zero_executions():
    """Success rate should be 100% when there are no executions."""
    cron = FasterCron(log_level=logging.CRITICAL)
    stats = cron.get_stats()
    assert stats.success_rate == 100.0


def test_stats_to_dict():
    """to_dict() should return a proper dictionary."""
    cron = FasterCron(log_level=logging.CRITICAL)

    def my_task():
        pass

    cron.add_task("* * * * * *", my_task)

    stats = cron.get_stats()
    d = stats.to_dict()

    assert isinstance(d, dict)
    assert d["total_tasks"] == 1
    assert d["active_tasks"] == 1
    assert d["paused_tasks"] == 0
    assert d["disabled_tasks"] == 0
    assert d["total_executions"] == 0
    assert d["successful_executions"] == 0
    assert d["failed_executions"] == 0
    assert d["success_rate"] == 100.0


def test_async_stats_works():
    """AsyncFasterCron should also support get_stats()."""
    cron = AsyncFasterCron(log_level=logging.CRITICAL)
    stats = cron.get_stats()
    assert stats.total_tasks == 0
    assert stats.success_rate == 100.0
