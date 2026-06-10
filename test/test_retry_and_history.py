from __future__ import annotations

from datetime import datetime

import pytest

from faster_cron import AsyncFasterCron, FasterCron
from faster_cron.models import ExecutionRecord, TaskState


def test_sync_retry_error_history_and_callback():
    callback_records = []
    attempts = {"value": 0}

    def on_error(error: Exception, record: ExecutionRecord):
        callback_records.append((error, record))

    cron = FasterCron(log_level=50, max_retries=2, retry_delay=0.01, on_error=on_error)

    @cron.schedule("* * * * * *")
    def flaky(ctx):
        attempts["value"] += 1
        raise ValueError("boom")

    task = cron.tasks[0]
    cron._execute_task(task, {"scheduled_at": datetime.now(), "task_name": "flaky"})

    assert attempts["value"] == 3
    assert len(cron.error_history) == 1
    assert cron.error_history[0].retry_count == 2
    assert cron.get_task("flaky").last_result == "boom"
    assert isinstance(callback_records[0][1], ExecutionRecord)
    assert cron.get_task("flaky").state == TaskState.PENDING


@pytest.mark.asyncio
async def test_async_retry_success_history_and_last_result():
    attempts = {"value": 0}
    cron = AsyncFasterCron(log_level=50, max_retries=2, retry_delay=0.01)

    @cron.schedule("* * * * * *")
    async def flaky(ctx):
        attempts["value"] += 1
        if attempts["value"] < 3:
            raise ValueError("temporary")

    task = cron.tasks[0]
    await cron._execute_task(
        task, {"scheduled_at": datetime.now(), "task_name": "flaky"}
    )

    assert attempts["value"] == 3
    assert len(cron.execution_history) == 1
    assert cron.execution_history[0].success is True
    assert cron.get_task("flaky").last_result == "success"
    assert cron.get_task("flaky").retry_count == 0


@pytest.mark.asyncio
async def test_async_error_callback_on_final_failure():
    callback_records = []

    def on_error(error: Exception, record: ExecutionRecord):
        callback_records.append((error, record))

    cron = AsyncFasterCron(
        log_level=50, max_retries=1, retry_delay=0.01, on_error=on_error
    )

    @cron.schedule("* * * * * *")
    async def always_fail(ctx):
        raise RuntimeError("fatal")

    task = cron.tasks[0]
    await cron._execute_task(
        task, {"scheduled_at": datetime.now(), "task_name": "always_fail"}
    )

    assert len(callback_records) == 1
    error, record = callback_records[0]
    assert str(error) == "fatal"
    assert record.retry_count == 1
    assert len(cron.error_history) == 1
