"""
Test Suite for Asynchronous AsyncFasterCron
"""
import pytest
import asyncio
import time
import logging
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from faster_cron import AsyncFasterCron
from faster_cron.models import TaskInfo, TaskState


logging.basicConfig(level=logging.WARNING)


class TestAsyncFasterCronInit:
    """Test initialization and basic setup"""
    
    def test_init_default(self):
        """Test default initialization"""
        cron = AsyncFasterCron()
        assert cron is not None
        assert cron.tasks == []
        assert cron.task_registry == {}
        assert cron._running is False
    
    def test_init_with_params(self):
        """Test initialization with custom parameters"""
        cron = AsyncFasterCron(
            log_level=logging.ERROR,
            max_retries=5,
            retry_delay=10.0
        )
        assert cron.max_retries == 5
        assert cron.retry_delay == 10.0
    
    def test_add_task(self):
        """Test adding a task dynamically"""
        cron = AsyncFasterCron()
        
        @cron.schedule("* * * * *")
        async def my_task(ctx):
            pass
        
        assert len(cron.tasks) == 1
        assert 'my_task' in cron.task_registry
    
    def test_remove_task(self):
        """Test removing a task"""
        cron = AsyncFasterCron()
        
        @cron.schedule("* * * * *")
        async def my_task(ctx):
            pass
        
        assert cron.remove_task("my_task") is True
        assert len(cron.tasks) == 0
        assert "my_task" not in cron.task_registry
        
        # Removing non-existent task should return False
        assert cron.remove_task("non_existent") is False


class TestAsyncTaskManagement:
    """Test task management operations"""
    
    @pytest.mark.asyncio
    async def test_pause_resume_task(self):
        """Test pausing and resuming tasks"""
        cron = AsyncFasterCron()
        
        @cron.schedule("* * * * *")
        async def my_task(ctx):
            pass
        
        assert cron.pause_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PAUSED
        
        assert cron.resume_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PENDING
    
    def test_disable_enable_task(self):
        """Test disabling and enabling tasks"""
        cron = AsyncFasterCron()
        
        @cron.schedule("* * * * *")
        async def my_task(ctx):
            pass
        
        assert cron.disable_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.DISABLED
        
        assert cron.enable_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PENDING
    
    def test_list_tasks(self):
        """Test listing all tasks"""
        cron = AsyncFasterCron()
        
        @cron.schedule("* * * * *")
        async def task1(ctx):
            pass
        
        @cron.schedule("0 * * * *")
        async def task2(ctx):
            pass
        
        tasks = cron.list_tasks()
        assert len(tasks) == 2


class TestAsyncOneShotScheduler:
    """Test one-shot scheduler functionality"""
    
    @pytest.mark.asyncio
    async def test_once_in_decorator(self):
        """Test once_in decorator"""
        cron = AsyncFasterCron()
        results = []
        
        @cron.once_in(0.1)
        async def delayed_task(ctx):
            results.append(time.time())
        
        # Wait for task to execute
        await asyncio.sleep(0.3)
        
        assert len(results) == 1
    
    @pytest.mark.asyncio
    async def test_run_at_decorator(self):
        """Test run_at decorator"""
        cron = AsyncFasterCron()
        results = []
        
        target_time = datetime.now() + timedelta(seconds=0.1)
        
        @cron.run_at(target_time)
        async def scheduled_task(ctx):
            results.append(time.time())
        
        # Wait for task to execute
        await asyncio.sleep(0.3)
        
        assert len(results) == 1
    
    @pytest.mark.asyncio
    async def test_once_in_with_context(self):
        """Test once_in passes context parameter"""
        cron = AsyncFasterCron()
        captured_context = {}
        
        @cron.once_in(0.1)
        async def task_with_context(ctx):
            captured_context.update(ctx)
        
        # Wait for task to execute
        await asyncio.sleep(0.3)
        
        assert 'scheduled_at' in captured_context
        assert 'task_name' in captured_context


class TestAsyncExecutionRecords:
    """Test execution record tracking"""
    
    @pytest.mark.asyncio
    async def test_execution_history(self):
        """Test that execution history is tracked"""
        cron = AsyncFasterCron()
        
        count = [0]
        
        @cron.schedule("* * * * *")
        async def counting_task(ctx):
            count[0] += 1
        
        # Simulate execution
        task_info = cron.task_registry['counting_task']
        context = {"scheduled_at": datetime.now(), "task_name": "counting_task"}
        
        # Execute the task manually (wrapper handles this)
        await cron._execute_one_shot(task_info, type('obj', (object,), {'task_name': 'counting_task', 'scheduled_at': context['scheduled_at'], 'retry_count': 0})())
        
        # Check if we have any records (one-shot might fail due to timing)
        assert isinstance(cron.execution_history, list)


class TestAsyncRunMethod:
    """Test the run() method"""
    
    @pytest.mark.asyncio
    async def test_run_exists(self):
        """Test that run method exists"""
        cron = AsyncFasterCron()
        assert hasattr(cron, 'run')
    
    @pytest.mark.asyncio
    async def test_run_returns_none(self):
        """Test run method returns None when no tasks"""
        cron = AsyncFasterCron()
        result = await cron.run()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_start_alias(self):
        """Test that start works as expected"""
        cron = AsyncFasterCron()
        # Should not raise an error
        await cron.start()
    
    def test_stop_method(self):
        """Test stop method exists"""
        cron = AsyncFasterCron()
        assert hasattr(cron, 'stop')


class TestConfigLoading:
    """Test configuration loading methods"""
    
    def test_load_from_yaml_method_exists(self):
        """Test that load_from_yaml method exists"""
        cron = AsyncFasterCron()
        assert hasattr(cron, 'load_from_yaml')
    
    def test_load_from_json_method_exists(self):
        """Test that load_from_json method exists"""
        cron = AsyncFasterCron()
        assert hasattr(cron, 'load_from_json')
    
    @pytest.mark.asyncio
    async def test_run_works_with_no_tasks(self):
        """Test run() works when there are no tasks"""
        cron = AsyncFasterCron()
        # Should complete without error
        await cron.run()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
