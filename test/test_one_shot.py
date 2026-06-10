from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

import pytest


def test_sync_once_in_supports_decorator_and_execution_context(sync_cron):
    captured = {}

    @sync_cron.once_in(0.1)
    def send_email(ctx):
        captured.update(ctx)

    time.sleep(0.35)

    assert captured["task_name"] == "send_email"
    assert captured["execution_type"] == "one_time_delayed"
    assert isinstance(captured["scheduled_at"], datetime)
    assert sync_cron.get_task("send_email") is None


def test_sync_run_at_with_args_and_kwargs(sync_cron):
    result = {}

    def job(message, *, count=1):
        result["message"] = message
        result["count"] = count

    sync_cron.run_at(
        datetime.now() + timedelta(milliseconds=100),
        job,
        args=("hello",),
        kwargs={"count": 3},
    )
    time.sleep(0.35)

    assert result == {"message": "hello", "count": 3}
    assert sync_cron.get_task("job") is None


@pytest.mark.asyncio
async def test_async_once_in_supports_decorator_and_execution_context(async_cron):
    captured = {}

    @async_cron.once_in(0.1)
    async def send_async_email(ctx):
        captured.update(ctx)

    await asyncio.sleep(0.35)

    assert captured["task_name"] == "send_async_email"
    assert captured["execution_type"] == "one_time_delayed"
    assert isinstance(captured["scheduled_at"], datetime)
    assert async_cron.get_task("send_async_email") is None


@pytest.mark.asyncio
async def test_async_run_at_supports_args_kwargs_and_past_times(async_cron):
    result = {}

    async def job(message, count=1):
        result["message"] = message
        result["count"] = count

    async_cron.run_at(
        datetime.now() - timedelta(milliseconds=10),
        job,
        args=("ready",),
        kwargs={"count": 2},
    )
    await asyncio.sleep(0.2)

    assert result == {"message": "ready", "count": 2}
    assert async_cron.get_task("job") is None
