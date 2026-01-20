import asyncio
import pytest
from datetime import datetime
from faster_cron.async_cron import AsyncFastCron

@pytest.mark.asyncio
async def test_async_overlap_prevention():
    """
    测试异步模式下的重叠控制：
    注册一个每秒触发一次的任务，但任务耗时 1.5 秒且 allow_overlap=False。
    在运行 3 秒的时间内，该任务应该只执行 2 次（第 1 秒触发，第 2 秒因为第 1 秒的没跑完被跳过）。
    """
    cron = AsyncFastCron()
    execution_counter = 0

    @cron.schedule("* * * * * *", allow_overlap=False)
    async def slow_task():
        nonlocal execution_counter
        execution_counter += 1
        await asyncio.sleep(1.5)

    # 启动调度器并运行 3.2 秒后停止
    cron_task = asyncio.create_task(cron.start())
    await asyncio.sleep(3.2)
    cron._running = False
    cron_task.cancel()

    # 预期执行次数应为 2 (触发点: T+1, T+3)
    # 如果允许重叠，3.2秒内会触发 3 次
    assert execution_counter == 2, f"预期执行 2 次，实际执行了 {execution_counter} 次"

@pytest.mark.asyncio
async def test_async_context_injection():
    """测试上下文参数是否能正确注入"""
    cron = AsyncFastCron()
    received_context = None

    @cron.schedule("* * * * * *")
    async def task_with_ctx(context):
        nonlocal received_context
        received_context = context

    cron_task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.1)
    cron._running = False
    cron_task.cancel()

    assert received_context is not None
    assert "task_name" in received_context
    assert received_context["task_name"] == "task_with_ctx"