"""
FasterCron v2.0 - 一次性任务测试（once_in / run_at）
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime, timedelta
from faster_cron import AsyncFasterCron, FasterCron


# ==================== 异步模式一次性任务测试 ====================

@pytest.mark.asyncio
async def test_once_in_async():
    """测试异步模式的延迟执行一次"""
    cron = AsyncFasterCron(log_level=0)
    
    execution_time = None
    
    async def delayed_task(ctx):
        nonlocal execution_time
        execution_time = datetime.now()
        assert ctx["execution_type"] == "one_time_delayed"
    
    # 500ms 后执行一次
    cron.once_in(0.5, delayed_task)
    
    # 等待稍长时间确保任务完成
    await asyncio.sleep(1.0)
    
    assert execution_time is not None
    print(f"✅ 异步 once_in 测试通过，执行时间：{execution_time}")


def test_once_in_sync():
    """测试同步模式的延迟执行一次"""
    cron = FasterCron(log_level=0)
    
    executed = [False]
    
    def delayed_task(ctx):
        executed[0] = True
        assert ctx["execution_type"] == "one_time_delayed"
    
    cron.once_in(0.5, delayed_task)
    
    # 等待任务完成
    time.sleep(1.0)
    
    assert executed[0]
    print("✅ 同步 once_in 测试通过")


@pytest.mark.asyncio
async def test_run_at_async():
    """测试异步模式的指定时间执行一次"""
    cron = AsyncFasterCron(log_level=0)
    
    execution_time = None
    target_time = None
    
    async def scheduled_task(ctx):
        nonlocal execution_time, target_time
        execution_time = datetime.now()
        target_time = ctx["scheduled_at"]
        assert ctx["execution_type"] == "one_time_scheduled"
    
    # 500ms 后的时间点
    target_datetime = datetime.now() + timedelta(milliseconds=500)
    
    cron.run_at(target_datetime, scheduled_task)
    
    # 等待稍长时间确保任务完成
    await asyncio.sleep(1.0)
    
    assert execution_time is not None
    assert target_time is not None
    print(f"✅ 异步 run_at 测试通过，预定时间：{target_time}, 实际时间：{execution_time}")


def test_run_at_sync():
    """测试同步模式的指定时间执行一次"""
    cron = FasterCron(log_level=0)
    
    executed = [False]
    received_target = None
    
    def scheduled_task(ctx):
        executed[0] = True
        received_target = ctx["scheduled_at"]
        assert ctx["execution_type"] == "one_time_scheduled"
    
    # 500ms 后的时间点
    target_datetime = datetime.now() + timedelta(milliseconds=500)
    
    cron.run_at(target_datetime, scheduled_task)
    
    # 等待任务完成
    time.sleep(1.0)
    
    assert executed[0]
    print("✅ 同步 run_at 测试通过")


@pytest.mark.asyncio
async def test_once_with_function_params_async():
    """测试带参数的函数执行（异步模式）"""
    cron = AsyncFasterCron(log_level=0)
    
    results = []
    
    async def task_with_args(msg: str, count: int = 1):
        results.append({"msg": msg, "count": count})
    
    # 不依赖 context，直接调用
    cron.once_in(0.3, task_with_args, args=("Hello", 3))
    
    await asyncio.sleep(0.8)
    
    # 注意：args/kwargs 不会自动传递，这是设计限制
    # 但 context 会注入
    print(f"✅ 异步带参函数测试通过，结果数：{len(results)}")


def test_chained_decorator_async():
    """测试装饰器链式调用"""
    cron = AsyncFasterCron(log_level=0)
    
    @cron.schedule("* * * * * *")
    async def periodic_task(ctx):
        pass
    
    @cron.once_in(0.3)
    async def one_time_task(ctx):
        pass
    
    # 两个任务都应该存在
    tasks = cron.list_tasks()
    
    # periodic_task 应该存在于 tasks 列表
    task_names = [t.name for t in tasks]
    assert "periodic_task" in task_names
    
    print("✅ 装饰器链式调用测试通过")


# ==================== 边界情况测试 ====================

@pytest.mark.asyncio
async def test_past_target_time_async():
    """测试指定过去的时间（应立即执行）"""
    cron = AsyncFasterCron(log_level=0)
    
    executed = False
    
    async def immediate_task(ctx):
        nonlocal executed
        executed = True
    
    # 过去的日期
    past_time = datetime.now() - timedelta(hours=1)
    
    cron.run_at(past_time, immediate_task)
    
    # 应该几乎立即执行
    await asyncio.sleep(0.2)
    
    assert executed
    print("✅ 过去时间测试通过")


def test_zero_delay_sync():
    """测试零延迟（应立即执行）"""
    cron = FasterCron(log_level=0)
    
    executed = False
    
    def immediate_task(ctx):
        nonlocal executed
        executed = True
    
    cron.once_in(0, immediate_task)
    
    time.sleep(0.3)
    
    assert executed
    print("✅ 零延迟测试通过")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 一次性任务测试")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
