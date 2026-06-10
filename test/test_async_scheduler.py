from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from faster_cron.models import TaskState


@pytest.mark.asyncio
async def test_async_run_alias_and_dynamic_task_addition(async_cron):
    executions: list[str] = []

    @async_cron.schedule("* * * * * *")
    async def first_task(ctx):
        executions.append(ctx["task_name"])

    runner = asyncio.create_task(async_cron.run())
    await asyncio.sleep(1.2)

    async def added_later(ctx):
        executions.append(ctx["task_name"])

    async_cron.add_task("* * * * * *", added_later)
    await asyncio.sleep(1.2)
    await async_cron.stop()
    await runner

    assert "first_task" in executions
    assert "added_later" in executions


@pytest.mark.asyncio
async def test_async_pause_resume_disable_enable(async_cron):
    counter = {"value": 0}

    @async_cron.schedule("* * * * * *")
    async def counted(ctx):
        counter["value"] += 1

    runner = asyncio.create_task(async_cron.start())
    await asyncio.sleep(1.2)
    before_pause = counter["value"]

    assert async_cron.pause_task("counted") is True
    assert async_cron.get_task("counted").state == TaskState.PAUSED
    await asyncio.sleep(1.2)
    after_pause = counter["value"]
    assert after_pause == before_pause

    assert async_cron.resume_task("counted") is True
    await asyncio.sleep(1.2)
    after_resume = counter["value"]
    assert after_resume > after_pause

    assert async_cron.disable_task("counted") is True
    assert async_cron.get_task("counted").state == TaskState.DISABLED
    assert async_cron.enable_task("counted") is True
    assert async_cron.get_task("counted").state == TaskState.PENDING

    await async_cron.stop()
    await runner


@pytest.mark.asyncio
async def test_async_context_injection_supports_positional_ctx_and_sync_callables(
    async_cron,
):
    received = {}

    async def positional_ctx(ctx):
        received["async"] = ctx

    def sync_callable(ctx):
        received["sync"] = ctx

    async_cron.add_task("* * * * * *", positional_ctx)
    async_cron.add_task("* * * * * *", sync_callable)
    context = {"scheduled_at": datetime.now(), "task_name": "manual"}

    await async_cron._execute_task(async_cron.tasks[0], context)
    await async_cron._execute_task(async_cron.tasks[1], context)

    assert received["async"]["task_name"] == "manual"
    assert received["sync"]["task_name"] == "manual"


@pytest.mark.asyncio
async def test_async_context_injection_supports_named_context_with_extra_args(
    async_cron,
):
    received = {}

    async def with_args(context, message):
        received["task"] = (context["task_name"], message)

    async_cron.add_task("* * * * * *", with_args, args=("hello",))
    context = {"scheduled_at": datetime.now(), "task_name": "manual"}
    await async_cron._execute_task(
        async_cron.tasks[0], context, args=("hello",), kwargs={}
    )

    assert received["task"] == ("manual", "hello")


@pytest.mark.asyncio
async def test_async_non_overlap_blocks_parallel_runs(async_cron):
    starts: list[float] = []

    @async_cron.schedule("* * * * * *", allow_overlap=False)
    async def slow_task(ctx):
        starts.append(asyncio.get_running_loop().time())
        await asyncio.sleep(1.3)

    runner = asyncio.create_task(async_cron.start())
    await asyncio.sleep(2.4)
    await async_cron.stop()
    await runner

    assert len(starts) <= 2


@pytest.mark.asyncio
async def test_async_remove_task(async_cron):
    @async_cron.schedule("* * * * * *")
    async def task_to_remove(ctx):
        pass

    assert async_cron.remove_task("task_to_remove") is True
    assert async_cron.get_task("task_to_remove") is None
    assert async_cron.remove_task("task_to_remove") is False


@pytest.mark.asyncio
async def test_async_start_without_tasks_returns_cleanly(async_cron):
    assert await async_cron.start() is None
    assert async_cron._running is False
