"""
测试一次性任务调度器（OneShot Scheduler）
"""

import pytest
import time
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from faster_cron.one_shot import OneShotScheduler, AsyncOneShotScheduler
from faster_cron.models import ExecutionRecord


class TestOneShotScheduler:
    """同步一次性任务测试"""
    
    def test_once_in_basic(self):
        """测试基本延迟执行"""
        results = []
        
        def dummy_task():
            results.append(time.time())
        
        scheduler = OneShotScheduler(log_level=logging.WARNING)
        record = scheduler.once_in(1.0, dummy_task)
        
        # 等待任务完成
        time.sleep(2.0)
        
        assert len(results) == 1
        assert record.success is True
        assert record.task_name == "dummy_task"
        print("✅ 测试通过：once_in 基本功能")
    
    def test_run_at_basic(self):
        """测试指定时间执行"""
        results = []
        
        def dummy_task():
            results.append(time.time())
        
        scheduler = OneShotScheduler(log_level=logging.WARNING)
        target_time = datetime.now() + timedelta(seconds=1)
        record = scheduler.run_at(target_time, dummy_task)
        
        # 等待任务完成
        time.sleep(2.0)
        
        assert len(results) == 1
        assert record.success is True
        print("✅ 测试通过：run_at 基本功能")
    
    def test_multiple_oneshots(self):
        """测试多个一次性任务"""
        results = []
        
        def task1():
            results.append("task1")
        
        def task2():
            results.append("task2")
        
        def task3():
            results.append("task3")
        
        scheduler = OneShotScheduler(log_level=logging.WARNING)
        
        # 依次添加不同延迟的任务
        scheduler.once_in(0.5, task1)
        scheduler.once_in(1.0, task2)
        scheduler.once_in(1.5, task3)
        
        # 等待所有任务完成
        time.sleep(2.5)
        
        assert len(results) == 3
        assert results == ["task1", "task2", "task3"]
        print("✅ 测试通过：多次一次性任务")
    
    def test_error_handling(self):
        """测试错误处理"""
        error_callback_called = False
        
        def error_handler(error, record):
            nonlocal error_callback_called
            error_callback_called = True
        
        def failing_task():
            raise ValueError("Test error")
        
        scheduler = OneShotScheduler(
            log_level=logging.WARNING,
            max_retries=0,
            on_error=error_handler
        )
        
        record = scheduler.once_in(0.5, failing_task)
        time.sleep(1.5)
        
        assert record.success is False
        assert "Test error" in record.error_message
        assert error_callback_called
        print("✅ 测试通过：错误处理")


class TestAsyncOneShotScheduler:
    """异步一次性任务测试"""
    
    @pytest.mark.asyncio
    async def test_once_in_basic_async(self):
        """测试基本异步延迟执行"""
        results = []
        
        async def dummy_task():
            results.append(time.time())
        
        scheduler = AsyncOneShotScheduler(log_level=logging.WARNING)
        record = await scheduler.once_in(1.0, dummy_task)
        
        # 等待任务完成
        await asyncio.sleep(2.0)
        
        assert len(results) == 1
        assert record.success is True
        print("✅ 测试通过：异步 once_in 基本功能")
    
    @pytest.mark.asyncio
    async def test_run_at_basic_async(self):
        """测试异步指定时间执行"""
        results = []
        
        async def dummy_task():
            results.append(time.time())
        
        scheduler = AsyncOneShotScheduler(log_level=logging.WARNING)
        target_time = datetime.now() + timedelta(seconds=1)
        record = await scheduler.run_at(target_time, dummy_task)
        
        # 等待任务完成
        await asyncio.sleep(2.0)
        
        assert len(results) == 1
        assert record.success is True
        print("✅ 测试通过：异步 run_at 基本功能")
    
    @pytest.mark.asyncio
    async def test_context_support(self):
        """测试 context 参数支持"""
        captured_context = {}
        
        async def task_with_context(context):
            captured_context.update(context)
        
        scheduler = AsyncOneShotScheduler(log_level=logging.WARNING)
        await scheduler.once_in(0.5, task_with_context)
        await asyncio.sleep(1.5)
        
        # context 应该包含 scheduled_at 和 task_name
        assert 'scheduled_at' in captured_context
        assert captured_context['task_name'] == 'task_with_context'
        print("✅ 测试通过：context 参数支持")


# 运行测试时自动执行
if __name__ == "__main__":
    import logging
    
    # 启用日志查看测试结果
    logging.basicConfig(level=logging.INFO)
    
    print("运行同步测试...")
    sync_tests = TestOneShotScheduler()
    sync_tests.test_once_in_basic()
    sync_tests.test_run_at_basic()
    sync_tests.test_multiple_oneshots()
    sync_tests.test_error_handling()
    
    print("\n运行异步测试...")
    import asyncio
    async_tests = TestAsyncOneShotScheduler()
    asyncio.run(async_tests.test_once_in_basic_async())
    asyncio.run(async_tests.test_run_at_basic_async())
    asyncio.run(async_tests.test_context_support())
    
    print("\n🎉 所有测试通过！")
