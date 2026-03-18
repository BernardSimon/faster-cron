"""
OneShot Scheduler: 一次性定时任务调度器

支持：
- 延迟 N 秒后执行一次 (once_in)
- 指定时间点执行一次 (run_at)
- 自动清理已执行任务
- 异常处理与重试
"""

import asyncio
import threading
import time
import datetime
from datetime import timedelta
import logging
from typing import Callable, Optional, Dict, Any, List, Union

from .models import TaskInfo, TaskState, ExecutionRecord


class OneShotScheduler:
    """同步一次性任务调度器"""
    
    def __init__(
        self,
        log_level: int = logging.INFO,
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_file: Optional[str] = None,
        custom_logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        on_error: Optional[Callable[[Exception, ExecutionRecord], None]] = None,
    ):
        """
        初始化一次性任务调度器
        
        Args:
            log_level: 日志级别 (默认 INFO)
            log_format: 日志格式字符串
            log_file: 可选的日志文件路径
            custom_logger: 可选的自定义 logger 对象
            max_retries: 最大重试次数 (默认 3)
            retry_delay: 重试间隔秒数 (默认 5.0)
            on_error: 错误回调函数 (func: error, record -> None)
        """
        self._pending_tasks: List[Dict[str, Any]] = []
        self._running = False
        self._threads: List[threading.Thread] = []
        
        # 执行记录
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error = on_error
        self.execution_history: List[ExecutionRecord] = []
        self.error_history: List[ExecutionRecord] = []
        
        if custom_logger:
            self.logger = custom_logger
        else:
            instance_id = id(self)
            self.logger = logging.getLogger(f"FasterCron.OneShot_{instance_id}")
            self.logger.setLevel(log_level)
            
            if not self.logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(logging.Formatter(log_format))
                self.logger.addHandler(console_handler)
                
                if log_file:
                    try:
                        file_handler = logging.FileHandler(log_file, encoding='utf-8')
                        file_handler.setFormatter(logging.Formatter(log_format))
                        self.logger.addHandler(file_handler)
                        print(f"✅ 日志已配置到文件：{log_file}")
                    except Exception as e:
                        print(f"⚠️ 无法创建日志文件 {log_file}: {e}")

    def once_in(self, seconds: float, func: Callable) -> ExecutionRecord:
        """
        延迟 N 秒后执行一次
        
        Args:
            seconds: 延迟秒数
            func: 要执行的函数
            
        Returns:
            ExecutionRecord: 执行记录
            
        Example:
            cron.once_in(300, send_email)  # 5 分钟后发送邮件
        """
        target_time = datetime.datetime.now() + timedelta(seconds=seconds)
        return self.run_at(target_time, func)

    def run_at(self, target_time: datetime.datetime, func: Callable) -> ExecutionRecord:
        """
        在指定时间执行一次
        
        Args:
            target_time: 目标执行时间
            func: 要执行的函数
            
        Returns:
            ExecutionRecord: 执行记录
            
        Example:
            from datetime import datetime, timedelta
            target_time = datetime.now() + timedelta(hours=1)
            cron.run_at(target_time, generate_report)
        """
        execution_record = ExecutionRecord(
            task_name=func.__name__,
            scheduled_at=target_time,
            started_at=None,
            finished_at=None,
            success=False,
            duration_seconds=0.0,
            retry_count=0,
            error_message=None
        )
        
        task_info = {
            "target_time": target_time,
            "func": func,
            "execution_record": execution_record,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "on_error": self.on_error,
            "logger": self.logger
        }
        
        self._pending_tasks.append(task_info)
        
        # 如果调度器未运行，启动后台线程
        if not self._running:
            self._start_monitor_thread()
        
        self.logger.info(f"Schedule one-shot task '{func.__name__}' at {target_time}")
        return execution_record

    def _start_monitor_thread(self):
        """启动监控所有待执行任务的后台线程"""
        if self._running:
            return
        
        self._running = True
        
        while self._running:
            now = datetime.datetime.now()
            tasks_to_execute = [t for t in self._pending_tasks if t["target_time"] <= now]
            
            for task in tasks_to_execute[:]:  # Copy to avoid modification during iteration
                self._pending_tasks.remove(task)
                thread = threading.Thread(
                    target=self._execute_task,
                    args=(task,),
                    name=f"OneShot-{task['func'].__name__}",
                    daemon=True
                )
                thread.start()
                self._threads.append(thread)
            
            # 检查是否还有待执行任务
            if not self._pending_tasks:
                break
            
            time.sleep(0.1)  # 高频检查短时间内的任务
        
        # 等待所有线程完成
        for thread in self._threads:
            thread.join(timeout=5.0)
        self._threads.clear()
        self._running = False

    def _execute_task(self, task: Dict[str, Any]):
        """执行单次任务"""
        func = task["func"]
        target_time = task["target_time"]
        execution_record = task["execution_record"]
        max_retries = task["max_retries"]
        retry_delay = task["retry_delay"]
        on_error = task["on_error"]
        logger = task["logger"]
        
        # 更新执行记录
        execution_record.started_at = datetime.datetime.now()
        if execution_record.scheduled_at.tzinfo is None:
            execution_record.scheduled_at = execution_record.scheduled_at.replace(tzinfo=datetime.timezone.utc)
        
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # 执行任务
                sig = __import__("inspect").signature(func)
                kwargs = {"context": {}} if 'context' in sig.parameters else {}
                func(**kwargs)
                
                # 成功
                execution_record.success = True
                execution_record.finished_at = datetime.datetime.now()
                execution_record.duration_seconds = (
                    execution_record.finished_at - execution_record.started_at
                ).total_seconds()
                
                self.execution_history.append(execution_record)
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-1000:]
                
                logger.info(
                    f"One-shot task '{func.__name__}' completed successfully "
                    f"in {execution_record.duration_seconds:.2f}s"
                )
                break
                
            except Exception as e:
                last_error = e
                execution_record.error_message = str(e)
                execution_record.retry_count = retry_count
                
                logger.error(
                    f"One-shot task '{func.__name__}' failed (attempt {retry_count + 1}/{max_retries + 1}): {e}",
                    exc_info=True
                )
                
                retry_count += 1
                
                if retry_count <= max_retries:
                    logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Max retries exceeded for task '{func.__name__}'")
        
        if not execution_record.success:
            execution_record.finished_at = datetime.datetime.now()
            execution_record.duration_seconds = (
                execution_record.finished_at - execution_record.started_at
            ).total_seconds()
            self.error_history.append(execution_record)
            
            if len(self.error_history) > 100:
                self.error_history = self.error_history[-100:]
            
            if on_error:
                try:
                    on_error(last_error, execution_record)
                except Exception as callback_err:
                    logger.error(f"Error callback failed: {callback_err}")


class AsyncOneShotScheduler:
    """异步一次性任务调度器"""
    
    def __init__(
        self,
        log_level: int = logging.INFO,
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_file: Optional[str] = None,
        custom_logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        on_error: Optional[Callable[[Exception, ExecutionRecord], None]] = None,
    ):
        """
        初始化异步一次性任务调度器
        
        Args:
            log_level: 日志级别 (默认 INFO)
            log_format: 日志格式字符串
            log_file: 可选的日志文件路径
            custom_logger: 可选的自定义 logger 对象
            max_retries: 最大重试次数 (默认 3)
            retry_delay: 重试间隔秒数 (默认 5.0)
            on_error: 错误回调函数 (func: error, record -> None)
        """
        self._pending_tasks: List[Dict[str, Any]] = []
        self._running = False
        self._background_task: Optional[asyncio.Task] = None
        
        # 执行记录
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error = on_error
        self.execution_history: List[ExecutionRecord] = []
        self.error_history: List[ExecutionRecord] = []
        
        if custom_logger:
            self.logger = custom_logger
        else:
            instance_id = id(self)
            self.logger = logging.getLogger(f"FasterCron.AsyncOneShot_{instance_id}")
            self.logger.setLevel(log_level)
            
            if not self.logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(logging.Formatter(log_format))
                self.logger.addHandler(console_handler)
                
                if log_file:
                    try:
                        file_handler = logging.FileHandler(log_file, encoding='utf-8')
                        file_handler.setFormatter(logging.Formatter(log_format))
                        self.logger.addHandler(file_handler)
                        print(f"✅ 日志已配置到文件：{log_file}")
                    except Exception as e:
                        print(f"⚠️ 无法创建日志文件 {log_file}: {e}")

    async def once_in(self, seconds: float, func: Callable) -> ExecutionRecord:
        """
        延迟 N 秒后执行一次
        
        Args:
            seconds: 延迟秒数
            func: 要执行的函数
            
        Returns:
            ExecutionRecord: 执行记录
            
        Example:
            await cron.once_in(300, send_email)  # 5 分钟后发送邮件
        """
        target_time = datetime.datetime.now() + timedelta(seconds=seconds)
        return await self.run_at(target_time, func)

    async def run_at(self, target_time: datetime.datetime, func: Callable) -> ExecutionRecord:
        """
        在指定时间执行一次
        
        Args:
            target_time: 目标执行时间
            func: 要执行的函数
            
        Returns:
            ExecutionRecord: 执行记录
            
        Example:
            from datetime import datetime, timedelta
            target_time = datetime.now() + timedelta(hours=1)
            await cron.run_at(target_time, generate_report)
        """
        execution_record = ExecutionRecord(
            task_name=func.__name__,
            scheduled_at=target_time,
            started_at=None,
            finished_at=None,
            success=False,
            duration_seconds=0.0,
            retry_count=0,
            error_message=None
        )
        
        task_info = {
            "target_time": target_time,
            "func": func,
            "execution_record": execution_record,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "on_error": self.on_error,
            "logger": self.logger
        }
        
        self._pending_tasks.append(task_info)
        
        # 如果后台任务未运行，启动它
        if self._background_task is None or self._background_task.done():
            self._running = True
            self._background_task = asyncio.create_task(self._monitor_loop())
        
        self.logger.info(f"Schedule one-shot task '{func.__name__}' at {target_time}")
        return execution_record

    async def _monitor_loop(self):
        """后台监控循环"""
        while self._running:
            now = datetime.datetime.now()
            tasks_to_execute = [t for t in self._pending_tasks if t["target_time"] <= now]
            
            for task in tasks_to_execute[:]:  # Copy to avoid modification
                self._pending_tasks.remove(task)
                asyncio.create_task(self._execute_task_async(task))
            
            # 检查是否还有待执行任务
            if not self._pending_tasks:
                break
            
            await asyncio.sleep(0.1)  # 高频检查短时间内的任务
        
        self._running = False

    async def _execute_task_async(self, task: Dict[str, Any]):
        """执行单次任务（异步）"""
        func = task["func"]
        target_time = task["target_time"]
        execution_record = task["execution_record"]
        max_retries = task["max_retries"]
        retry_delay = task["retry_delay"]
        on_error = task["on_error"]
        logger = task["logger"]
        
        # 更新执行记录
        execution_record.started_at = datetime.datetime.now()
        if execution_record.scheduled_at.tzinfo is None:
            execution_record.scheduled_at = execution_record.scheduled_at.replace(tzinfo=datetime.timezone.utc)
        
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # 执行任务
                import inspect
                sig = inspect.signature(func)
                kwargs = {"context": {}} if 'context' in sig.parameters else {}
                
                result = func(**kwargs)
                if asyncio.iscoroutine(result):
                    await result
                
                # 成功
                execution_record.success = True
                execution_record.finished_at = datetime.datetime.now()
                execution_record.duration_seconds = (
                    execution_record.finished_at - execution_record.started_at
                ).total_seconds()
                
                self.execution_history.append(execution_record)
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-1000:]
                
                logger.info(
                    f"One-shot task '{func.__name__}' completed successfully "
                    f"in {execution_record.duration_seconds:.2f}s"
                )
                break
                
            except Exception as e:
                last_error = e
                execution_record.error_message = str(e)
                execution_record.retry_count = retry_count
                
                logger.error(
                    f"One-shot task '{func.__name__}' failed (attempt {retry_count + 1}/{max_retries + 1}): {e}",
                    exc_info=True
                )
                
                retry_count += 1
                
                if retry_count <= max_retries:
                    logger.info(f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Max retries exceeded for task '{func.__name__}'")
        
        if not execution_record.success:
            execution_record.finished_at = datetime.datetime.now()
            execution_record.duration_seconds = (
                execution_record.finished_at - execution_record.started_at
            ).total_seconds()
            self.error_history.append(execution_record)
            
            if len(self.error_history) > 100:
                self.error_history = self.error_history[-100:]
            
            if on_error:
                try:
                    on_error(last_error, execution_record)
                except Exception as callback_err:
                    logger.error(f"Error callback failed: {callback_err}")

    async def cancel_all(self):
        """取消所有待执行任务"""
        self._pending_tasks.clear()
        self.logger.info("All pending one-shot tasks cancelled")


# 快捷函数（兼容旧版本 API）
def once_in(scheduler: Union[OneShotScheduler, AsyncOneShotScheduler], 
           seconds: float, func: Callable) -> ExecutionRecord:
    """一次性延迟任务（通用接口）"""
    if isinstance(scheduler, AsyncOneShotScheduler):
        raise RuntimeError("使用 async/await: await scheduler.once_in(...)")
    return scheduler.once_in(seconds, func)

def run_at(scheduler: Union[OneShotScheduler, AsyncOneShotScheduler],
          target_time: datetime.datetime, func: Callable) -> ExecutionRecord:
    """一次性定时任务（通用接口）"""
    if isinstance(scheduler, AsyncOneShotScheduler):
        raise RuntimeError("使用 async/await: await scheduler.run_at(...)")
    return scheduler.run_at(target_time, func)
