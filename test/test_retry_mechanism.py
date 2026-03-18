"""
FasterCron v2.0 - 异常处理与重试机制测试
"""

import pytest
import asyncio
from unittest.mock import Mock
from faster_cron import AsyncFasterCron, FasterCron
from faster_cron.models import ExecutionRecord


# ==================== 异步模式重试测试 ====================

@pytest.mark.asyncio
async def test_retry_on_failure_async():
    """测试异步模式下任务失败时的重试机制"""
    cron = AsyncFasterCron(log_level=0, max_retries=2, retry_delay=0.1)
    
    execution_count = [0]
    
    async def flaky_task(ctx):
        execution_count[0] += 1
        if execution_count[0] < 3:
            raise Exception("临时错误")
        # 第三次执行成功
    
    @cron.schedule("* * * * * *")
    async def my_task(ctx):
        await flaky_task(ctx)
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(2)
    await cron.stop()
    
    # 应该尝试了 3 次（初始 + 2 次重试）
    assert execution_count[0] == 3, f"Expected 3 executions, got {execution_count[0]}"
    
    print(f"✅ 异步重试测试通过 (尝试次数：{execution_count[0]})")


def test_retry_on_failure_sync():
    """测试同步模式下任务失败时的重试机制"""
    cron = FasterCron(log_level=0, max_retries=2, retry_delay=0.1)
    
    execution_count = [0]
    
    def flaky_task(ctx):
        execution_count[0] += 1
        if execution_count[0] < 3:
            raise Exception("临时错误")
    
    @cron.schedule("* * * * * *")
    def my_task(ctx):
        flaky_task(ctx)
    
    thread = threading.Thread(target=cron.run, daemon=True)
    thread.start()
    
    time.sleep(2)
    cron.stop()
    
    assert execution_count[0] == 3
    
    print(f"✅ 同步重试测试通过 (尝试次数：{execution_count[0]})")


@pytest.mark.asyncio
async def test_max_retries_exceeded_async():
    """测试超过最大重试次数后记录到错误历史"""
    cron = AsyncFasterCron(
        log_level=0,
        max_retries=2,
        retry_delay=0.1,
        on_error=None  # 不需要回调
    )
    
    async def always_fail_task(ctx):
        raise Exception("总是失败")
    
    @cron.schedule("* * * * * *")
    async def my_task(ctx):
        await always_fail_task(ctx)
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    await cron.stop()
    
    # 应该至少有 1 条错误记录
    assert len(cron.error_history) >= 1, "应该有至少 1 条错误记录"
    
    # 检查错误记录的字段
    error_record = cron.error_history[0]
    assert isinstance(error_record, ExecutionRecord)
    assert error_record.task_name == "my_task"
    assert error_record.success == False
    assert error_record.retry_count == 2  # max_retries
    assert error_record.error_message == "总是失败"
    
    print(f"✅ 最大重试超限测试通过")


def test_max_retries_exceeded_sync():
    """测试同步模式最大重试超限"""
    cron = FasterCron(
        log_level=0,
        max_retries=2,
        retry_delay=0.1,
    )
    
    def always_fail_task(ctx):
        raise Exception("总是失败")
    
    @cron.schedule("* * * * * *")
    def my_task(ctx):
        always_fail_task(ctx)
    
    thread = threading.Thread(target=cron.run, daemon=True)
    thread.start()
    
    time.sleep(1.5)
    cron.stop()
    
    assert len(cron.error_history) >= 1
    
    print(f"✅ 同步最大重试超限测试通过")


@pytest.mark.asyncio
async def test_on_error_callback_async():
    """测试异步模式的错误回调功能"""
    errors_received = []
    
    def error_handler(error: Exception, record: ExecutionRecord):
        errors_received.append((error, record))
    
    cron = AsyncFasterCron(
        log_level=0,
        max_retries=1,
        retry_delay=0.1,
        on_error=error_handler
    )
    
    async def failing_task(ctx):
        raise ValueError("模拟错误")
    
    @cron.schedule("* * * * * *")
    async def my_task(ctx):
        await failing_task(ctx)
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1)
    await cron.stop()
    
    # 应该有回调被调用
    assert len(errors_received) >= 1, "on_error 回调应该被调用"
    
    error, record = errors_received[0]
    assert isinstance(error, ValueError)
    assert str(error) == "模拟错误"
    assert record.task_name == "my_task"
    
    print(f"✅ 异步错误回调测试通过")


# ==================== 上下文注入和状态管理测试 ====================

@pytest.mark.asyncio
async def test_context_injection_with_retry_async():
    """测试重试机制中 context 的正确注入"""
    contexts_received = []
    
    async def task_with_context(ctx):
        contexts_received.append(ctx)
    
    cron = AsyncFasterCron(log_level=0, max_retries=0)
    
    @cron.schedule("* * * * * *")
    async def my_task(ctx):
        await task_with_context(ctx)
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.2)
    await cron.stop()
    
    assert len(contexts_received) >= 1
    ctx = contexts_received[0]
    assert "scheduled_at" in ctx
    assert "task_name" in ctx
    assert ctx["task_name"] == "my_task"
    
    print("✅ 异步 Context 注入测试通过")


if __name__ == "__main__":
    import asyncio
    import time
    import threading
    
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 重试机制测试")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
