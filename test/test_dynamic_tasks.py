"""
FasterCron v2.0 - 动态任务管理测试
"""

import pytest
import asyncio
import time
import threading
from faster_cron import AsyncFasterCron, FasterCron


# ==================== 异步模式动态任务测试 ====================

@pytest.mark.asyncio
async def test_add_task_async():
    """测试异步模式下动态添加任务"""
    cron = AsyncFasterCron(log_level=0)
    
    # 初始应该没有任务
    assert len(cron.list_tasks()) == 0
    
    async def new_task(ctx):
        pass
    
    task_info = cron.add_task("*/5 * * * * *", new_task, allow_overlap=False)
    
    assert task_info is not None
    assert task_info.name == "new_task"
    assert task_info.expression == "*/5 * * * * *"
    assert task_info.allow_overlap == False
    assert len(cron.list_tasks()) == 1
    
    print("✅ 异步动态添加任务测试通过")


def test_add_task_sync():
    """测试同步模式下动态添加任务"""
    cron = FasterCron(log_level=0)
    
    assert len(cron.list_tasks()) == 0
    
    def new_task(ctx):
        pass
    
    task_info = cron.add_task("* * * * * *", new_task)
    
    assert task_info.name == "new_task"
    assert len(cron.list_tasks()) == 1
    
    print("✅ 同步动态添加任务测试通过")


@pytest.mark.asyncio
async def test_remove_task_async():
    """测试异步模式下移除任务"""
    cron = AsyncFasterCron(log_level=0)
    
    @cron.schedule("* * * * * *")
    async def my_task(ctx):
        pass
    
    assert len(cron.list_tasks()) == 1
    
    removed = cron.remove_task("my_task")
    
    assert removed == True
    assert len(cron.list_tasks()) == 0
    assert cron.get_task("my_task") is None
    
    print("✅ 异步移除任务测试通过")


def test_remove_task_sync():
    """测试同步模式下移除任务"""
    cron = FasterCron(log_level=0)
    
    @cron.schedule("* * * * * *")
    def my_task(ctx):
        pass
    
    assert len(cron.list_tasks()) == 1
    
    removed = cron.remove_task("my_task")
    assert removed == True
    assert len(cron.list_tasks()) == 0
    
    print("✅ 同步移除任务测试通过")


@pytest.mark.asyncio
async def test_pause_resume_async():
    """测试异步模式下的暂停和恢复"""
    cron = AsyncFasterCron(log_level=0)
    
    execution_count = [0]
    
    @cron.schedule("* * * * * *")
    async def counting_task(ctx):
        execution_count[0] += 1
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    
    initial_count = execution_count[0]
    
    # 暂停任务
    paused = cron.pause_task("counting_task")
    assert paused == True
    
    await asyncio.sleep(1.5)
    after_pause_count = execution_count[0]
    
    # 暂停后不应该执行
    assert after_pause_count == initial_count
    
    # 恢复任务
    resumed = cron.resume_task("counting_task")
    assert resumed == True
    
    await asyncio.sleep(1.5)
    after_resume_count = execution_count[0]
    
    # 恢复后应该继续执行
    assert after_resume_count > initial_count
    
    await cron.stop()
    
    print(f"✅ 异步暂停/恢复测试通过 (执行次数：{initial_count} -> {after_pause_count} -> {after_resume_count})")


def test_pause_resume_sync():
    """测试同步模式下的暂停和恢复"""
    cron = FasterCron(log_level=0)
    
    execution_count = [0]
    lock = threading.Lock()
    
    @cron.schedule("* * * * * *")
    def counting_task(ctx):
        with lock:
            execution_count[0] += 1
    
    thread = threading.Thread(target=cron.run, daemon=True)
    thread.start()
    
    time.sleep(1.5)
    initial_count = execution_count[0]
    
    cron.pause_task("counting_task")
    time.sleep(1.5)
    after_pause_count = execution_count[0]
    
    cron.resume_task("counting_task")
    time.sleep(1.5)
    after_resume_count = execution_count[0]
    
    cron.stop()
    
    assert after_pause_count <= initial_count + 1  # 容忍一次延迟
    assert after_resume_count > initial_count
    
    print(f"✅ 同步暂停/恢复测试通过 (执行次数：{initial_count} -> {after_pause_count} -> {after_resume_count})")


@pytest.mark.asyncio
async def test_list_and_get_task_async():
    """测试异步模式的查询任务功能"""
    cron = AsyncFasterCron(log_level=0)
    
    @cron.schedule("*/5 * * * * *")
    async def task1(ctx):
        pass
    
    @cron.schedule("* * * * * *")
    async def task2(ctx):
        pass
    
    tasks = cron.list_tasks()
    assert len(tasks) == 2
    
    task1_info = cron.get_task("task1")
    assert task1_info is not None
    assert task1_info.name == "task1"
    assert task1_info.expression == "*/5 * * * * *"
    
    non_existent = cron.get_task("nonexistent")
    assert non_existent is None
    
    print("✅ 异步列表/获取任务测试通过")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 动态任务管理测试")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
