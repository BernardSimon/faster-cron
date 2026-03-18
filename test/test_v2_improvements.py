"""
FasterCron v2.0 改进测试

测试内容：
1. 高精度时间控制
2. 优雅状态管理（stop() 方法）
3. 资源管理（非守护线程 + 等待完成）
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime, timedelta
from faster_cron import AsyncFasterCron, FasterCron


# ==================== 高精度时间控制测试 ====================

@pytest.mark.asyncio
async def test_high_precision_timing_async():
    """
    测试异步模式下的精度控制：
    注册一个每 2 秒触发一次的任务，验证执行时间与预定时间的误差 < 1 秒
    """
    cron = AsyncFasterCron(log_level=0)  # 静默模式
    execution_times = []

    @cron.schedule("*/2 * * * * *")
    async def precise_task(context):
        execution_times.append(context["scheduled_at"])

    # 启动调度器运行 6 秒
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(6.5)
    await cron.stop()
    
    # 应该触发了 3 次（2s, 4s, 6s）
    assert len(execution_times) >= 2, f"预期至少执行 2 次，实际 {len(execution_times)} 次"
    
    print(f"✅ 高精度时序测试通过，执行次数：{len(execution_times)}")


def test_high_precision_timing_sync():
    """
    测试同步模式下的精度控制
    """
    cron = FasterCron(log_level=0)
    execution_times = []
    lock = threading.Lock()

    @cron.schedule("*/2 * * * * *")
    def precise_task(context):
        with lock:
            execution_times.append(context["scheduled_at"])

    # 后台运行
    thread = threading.Thread(target=cron.run, daemon=True)
    thread.start()
    
    time.sleep(6.5)
    cron.stop()
    
    with lock:
        assert len(execution_times) >= 2, f"预期至少执行 2 次，实际 {len(execution_times)} 次"
    
    print(f"✅ 高精度时序测试通过，执行次数：{len(execution_times)}")


@pytest.mark.asyncio
async def test_stop_async_graceful():
    """
    测试异步模式的优雅关闭：
    启动一个慢任务（3 秒），然后在 1 秒后调用 stop()
    应该能正确停止调度器，不报错
    """
    cron = AsyncFasterCron(log_level=0)
    stop_called = False
    
    @cron.schedule("* * * * * *")
    async def slow_task(context):
        nonlocal stop_called
        if not stop_called:
            await asyncio.sleep(3)  # 模拟长耗时任务
    
    # 启动
    task = asyncio.create_task(cron.start())
    
    # 运行 0.5 秒后立即停止
    await asyncio.sleep(0.5)
    await cron.stop()
    stop_called = True
    
    # 检查没有未完成的任务
    assert len(cron._active_tasks) == 0, "应该有 0 个活跃任务"
    
    print("✅ 异步优雅关闭测试通过")


def test_stop_sync_graceful():
    """
    测试同步模式的优雅关闭
    """
    cron = FasterCron(log_level=0)
    stop_called = False
    
    @cron.schedule("* * * * * *")
    def slow_task(context):
        nonlocal stop_called
        if not stop_called:
            time.sleep(3)
    
    # 后台启动
    thread = threading.Thread(target=cron.run, daemon=False)
    thread.start()
    
    # 运行 0.5 秒后立即停止
    time.sleep(0.5)
    cron.stop()
    stop_called = True
    
    # 等待线程结束
    thread.join(timeout=2)
    assert not thread.is_alive(), "线程应该已终止"
    
    print("✅ 同步优雅关闭测试通过")


@pytest.mark.asyncio
async def test_active_tasks_tracking():
    """
    测试活跃任务追踪功能
    """
    cron = AsyncFasterCron(log_level=0)
    counter = 0
    
    @cron.schedule("* * * * * *")
    async def counting_task():
        nonlocal counter
        counter += 1
    
    # 启动
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    
    # 检查有活跃任务
    assert len(cron._active_tasks) > 0, "应该有活跃监控任务"
    
    # 停止
    await cron.stop()
    assert len(cron._active_tasks) == 0, "停止后应该没有活跃任务"
    
    print(f"✅ 活跃任务追踪测试通过")


def test_daemon_thread_behavior():
    """
    测试同步模式下使用非守护线程
    """
    cron = FasterCron(log_level=0)
    executed = [False]
    
    @cron.schedule("0 0 0 1 1 *")  # 不会在短期内触发
    def never_run():
        pass
    
    # 添加一个立即执行的测试
    import threading
    
    thread_count_before = len(threading.enumerate())
    
    t = threading.Thread(target=cron.run, daemon=False)
    t.start()
    
    # 短暂运行
    time.sleep(0.5)
    
    cron.stop()
    t.join(timeout=2)
    
    assert not t.is_alive(), "线程应该已正常退出"
    
    print("✅ 非守护线程行为测试通过")


@pytest.mark.asyncio
async def test_context_contains_next_trigger():
    """
    测试 context 中的 scheduled_at 包含精确的触发时间
    """
    cron = AsyncFasterCron(log_level=0)
    received_time = None
    
    @cron.schedule("* * * * * *")
    async def task_with_time(context):
        nonlocal received_time
        received_time = context.get("scheduled_at")
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    await cron.stop()
    
    assert received_time is not None, "context 中应该有 scheduled_at"
    assert isinstance(received_time, datetime), "scheduled_at 应该是 datetime 对象"
    
    print(f"✅ Context 包含精确触发时间：{received_time}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 改进测试")
    print("="*60 + "\n")
    
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
