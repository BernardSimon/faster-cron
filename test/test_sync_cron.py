"""
Test Suite for Synchronous FasterCron
"""
import pytest
import time
import logging
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from faster_cron import FasterCron
from faster_cron.models import TaskInfo, TaskState


logging.basicConfig(level=logging.WARNING)


class TestFasterCronInit:
    """Test initialization and basic setup"""
    
    def test_init_default(self):
        """Test default initialization"""
        cron = FasterCron()
        assert cron is not None
        assert cron.tasks == []
        assert cron.task_registry == {}
        assert cron._running is False
    
    def test_init_with_params(self):
        """Test initialization with custom parameters"""
        cron = FasterCron(
            log_level=logging.ERROR,
            max_retries=5,
            retry_delay=10.0
        )
        assert cron.max_retries == 5
        assert cron.retry_delay == 10.0
    
    def test_add_task(self):
        """Test adding a task dynamically"""
        cron = FasterCron()
        
        @cron.schedule("* * * * *")
        def my_task(ctx):
            pass
        
        assert len(cron.tasks) == 1
        assert 'my_task' in cron.task_registry
    
    def test_remove_task(self):
        """Test removing a task"""
        cron = FasterCron()
        
        @cron.schedule("* * * * *")
        def my_task(ctx):
            pass
        
        assert cron.remove_task("my_task") is True
        assert len(cron.tasks) == 0
        assert "my_task" not in cron.task_registry
        
        # Removing non-existent task should return False
        assert cron.remove_task("non_existent") is False


class TestTaskManagement:
    """Test task management operations"""
    
    def test_pause_resume_task(self):
        """Test pausing and resuming tasks"""
        cron = FasterCron()
        
        @cron.schedule("* * * * *")
        def my_task(ctx):
            pass
        
        assert cron.pause_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PAUSED
        assert "my_task" in cron.paused_tasks
        
        assert cron.resume_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PENDING
        assert "my_task" not in cron.paused_tasks
    
    def test_disable_enable_task(self):
        """Test disabling and enabling tasks"""
        cron = FasterCron()
        
        @cron.schedule("* * * * *")
        def my_task(ctx):
            pass
        
        assert cron.disable_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.DISABLED
        
        assert cron.enable_task("my_task") is True
        assert cron.task_registry["my_task"].state == TaskState.PENDING
    
    def test_list_tasks(self):
        """Test listing all tasks"""
        cron = FasterCron()
        
        @cron.schedule("* * * * *")
        def task1(ctx):
            pass
        
        @cron.schedule("0 * * * *")
        def task2(ctx):
            pass
        
        tasks = cron.list_tasks()
        assert len(tasks) == 2
        assert task1.__name__ in [t.name for t in tasks]
        assert task2.__name__ in [t.name for t in tasks]


class TestOneShotScheduler:
    """Test one-shot scheduler functionality"""
    
    def test_once_in_decorator(self):
        """Test once_in decorator"""
        cron = FasterCron()
        results = []
        
        @cron.once_in(0.1)
        def delayed_task(ctx):
            results.append(time.time())
        
        # Wait for task to execute
        time.sleep(0.3)
        
        assert len(results) == 1
    
    def test_run_at_decorator(self):
        """Test run_at decorator"""
        cron = FasterCron()
        results = []
        
        target_time = datetime.now() + timedelta(seconds=0.1)
        
        @cron.run_at(target_time)
        def scheduled_task(ctx):
            results.append(time.time())
        
        # Wait for task to execute
        time.sleep(0.3)
        
        assert len(results) == 1
    
    def test_once_in_with_context(self):
        """Test once_in passes context parameter"""
        cron = FasterCron()
        captured_context = {}
        
        @cron.once_in(0.1)
        def task_with_context(ctx):
            captured_context.update(ctx)
        
        # Wait for task to execute
        time.sleep(0.3)
        
        assert 'scheduled_at' in captured_context
        assert 'task_name' in captured_context


class TestExecutionRecords:
    """Test execution record tracking"""
    
    def test_execution_history(self):
        """Test that execution history is tracked"""
        cron = FasterCron()
        
        count = [0]
        
        @cron.schedule("* * * * *")
        def counting_task(ctx):
            count[0] += 1
        
        # Simulate execution
        task_info = cron.task_registry['counting_task']
        context = {"scheduled_at": datetime.now(), "task_name": "counting_task"}
        
        cron._execute_task(counting_task, context)
        
        assert len(cron.execution_history) == 1
        assert cron.execution_history[0].success is True
        assert cron.execution_history[0].task_name == "counting_task"
    
    def test_error_history(self):
        """Test that errors are tracked"""
        cron = FasterCron(max_retries=0)
        
        @cron.schedule("* * * * *")
        def failing_task(ctx):
            raise ValueError("Intentional error")
        
        task_info = cron.task_registry['failing_task']
        context = {"scheduled_at": datetime.now(), "task_name": "failing_task"}
        
        cron._execute_task(failing_task, context)
        
        assert len(cron.error_history) == 1
        assert cron.error_history[0].success is False


class TestRunMethod:
    """Test the run() method"""
    
    def test_run_exists(self):
        """Test that run method exists"""
        cron = FasterCron()
        assert hasattr(cron, 'run')
    
    def test_run_signature(self):
        """Test run method signature"""
        cron = FasterCron()
        import inspect
        sig = inspect.signature(cron.run)
        params = list(sig.parameters.keys())
        assert 'wait_on_exit' in params
    
    def test_stop_method(self):
        """Test stop method exists"""
        cron = FasterCron()
        assert hasattr(cron, 'stop')


class TestConfigLoading:
    """Test configuration loading methods"""
    
    def test_load_from_yaml_method_exists(self):
        """Test that load_from_yaml method exists"""
        cron = FasterCron()
        assert hasattr(cron, 'load_from_yaml')
    
    def test_load_from_json_method_exists(self):
        """Test that load_from_json method exists"""
        cron = FasterCron()
        assert hasattr(cron, 'load_from_json')
    
    def test_load_from_yaml_requires_pyyaml(self):
        """Test that YAML loading requires pyyaml"""
        try:
            import yaml
            has_yaml = True
        except ImportError:
            has_yaml = False
        
        if not has_yaml:
            print("Skipping YAML tests (pyyaml not installed)")
            pytest.skip("pyyaml not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
