"""
AsyncFasterCron: 异步定时任务调度器 v2.0

完整改进：
- 高精度时间控制
- 优雅状态管理 (stop)
- 灵活日志配置
- 动态任务管理 (add/remove/pause/resume/list)
- 异常处理与重试机制
- 资源管理
"""

import asyncio
import inspect
import datetime
from datetime import timedelta
import logging
from typing import Callable, Optional, Set, Dict, Any

from .models import TaskInfo, TaskState, ExecutionRecord


class AsyncFasterCron:
    """异步定时任务调度器 - v2.0"""
    
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
        初始化异步调度器
        
        Args:
            log_level: 日志级别 (默认 INFO)
            log_format: 日志格式字符串
            log_file: 可选的日志文件路径
            custom_logger: 可选的自定义 logger 对象
            max_retries: 最大重试次数 (默认 3)
            retry_delay: 重试间隔秒数 (默认 5.0)
            on_error: 错误回调函数 (func: error, record -> None)
        """
        self.tasks = []
        self._active_tasks: Set[asyncio.Task] = set()
        
        # 动态任务管理
        self.task_registry: Dict[str, TaskInfo] = {}
        self.paused_tasks: set = set()
        
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
            self.logger = logging.getLogger(f"FasterCron.Async_{instance_id}")
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
        
        self._running = False

    def schedule(self, expression: str, allow_overlap: bool = True):
        """装饰器：注册定时任务"""
        def decorator(func: Callable):
            self.add_task(expression, func, allow_overlap)
            return func

        return decorator

    def add_task(
        self,
        expression: str,
        func: Callable,
        allow_overlap: bool = True,
        priority: int = 0
    ) -> TaskInfo:
        """
        动态添加任务
        
        Args:
            expression: Cron 表达式
            func: 任务函数
            allow_overlap: 是否允许重叠执行
            priority: 任务优先级
            
        Returns:
            TaskInfo: 任务信息对象
        """
        task_info = TaskInfo(
            name=func.__name__,
            expression=expression,
            func=func,
            allow_overlap=allow_overlap,
            state=TaskState.PENDING,
            priority=priority
        )
        
        self.tasks.append({
            "expression": expression,
            "func": func,
            "allow_overlap": allow_overlap,
            "name": func.__name__,
            "priority": priority
        })
        self.task_registry[func.__name__] = task_info
        
        if self._running:
            self.logger.info(f"Added task '{func.__name__}' while scheduler running")
        
        return task_info

    def remove_task(self, task_name: str) -> bool:
        """
        移除指定任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            bool: 是否成功移除
        """
        if task_name not in self.task_registry:
            return False
        
        self.tasks = [t for t in self.tasks if t["name"] != task_name]
        del self.task_registry[task_name]
        
        # 如果正在运行，暂停它
        self.paused_tasks.discard(task_name)
        
        self.logger.info(f"Removed task '{task_name}'")
        return True

    def pause_task(self, task_name: str) -> bool:
        """
        暂停任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            bool: 是否成功暂停
        """
        if task_name not in self.task_registry:
            return False
        
        task_info = self.task_registry[task_name]
        task_info.state = TaskState.PAUSED
        self.paused_tasks.add(task_name)
        
        self.logger.info(f"Paused task '{task_name}'")
        return True

    def resume_task(self, task_name: str) -> bool:
        """
        恢复暂停的任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            bool: 是否成功恢复
        """
        if task_name not in self.task_registry:
            return False
        
        task_info = self.task_registry[task_name]
        task_info.state = TaskState.PENDING
        self.paused_tasks.discard(task_name)
        
        self.logger.info(f"Resumed task '{task_name}'")
        return True

    def disable_task(self, task_name: str) -> bool:
        """禁用任务（不调度但保留配置）"""
        if task_name not in self.task_registry:
            return False
        
        self.task_registry[task_name].state = TaskState.DISABLED
        self.paused_tasks.add(task_name)
        return True

    def enable_task(self, task_name: str) -> bool:
        """启用被禁用的任务"""
        if task_name not in self.task_registry:
            return False
        
        self.task_registry[task_name].state = TaskState.PENDING
        self.paused_tasks.discard(task_name)
        return True

    def list_tasks(self) -> list:
        """获取所有任务列表"""
        return list(self.task_registry.values())

    def get_task(self, task_name: str) -> Optional[TaskInfo]:
        """获取指定任务信息"""
        return self.task_registry.get(task_name)

    def _calculate_next_trigger(self, expression: str, from_time: datetime.datetime = None) -> datetime.datetime:
        """计算表达式在 from_time 之后的下一个触发时间"""
        if from_time is None:
            from_time = datetime.datetime.now()
        
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(seconds=1)
        max_iterations = 366 * 24 * 60 * 60
        
        for _ in range(max_iterations):
            if self._is_time_match(expression, candidate):
                return candidate
            candidate += timedelta(seconds=1)
        
        raise ValueError(f"No trigger time found within 1 year for expression: {expression}")
    
    @staticmethod
    def _is_time_match(expression: str, now: datetime.datetime) -> bool:
        """辅助方法：判断时间是否匹配"""
        from .base import CronBase
        return CronBase.is_time_match(expression, now)

    async def start(self):
        """启动调度器"""
        self._running = True
        listeners = [asyncio.create_task(self._monitor(task)) for task in self.tasks]
        self._active_tasks.update(listeners)
        
        try:
            await asyncio.gather(*listeners)
        finally:
            self._active_tasks.clear()

    async def stop(self):
        """优雅关闭调度器"""
        self.logger.info("Stopping scheduler...")
        self._running = False
        
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
        
        self._active_tasks.clear()
        self.logger.info("Scheduler stopped")

    async def _monitor(self, task):
        """监控单个任务的执行循环"""
        last_ts = 0
        current_task: Optional[asyncio.Task] = None

        while self._running:
            try:
                # 检查是否暂停
                if task["name"] in self.paused_tasks:
                    await asyncio.sleep(1.0)
                    continue
                
                now = datetime.datetime.now()
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                delay_seconds = (next_trigger - now).total_seconds()
                
                wait_time = min(delay_seconds, 0.5)
                await asyncio.sleep(wait_time)
                
                if not self._running:
                    break
                
                now = datetime.datetime.now()
                ts = int(now.timestamp())

                if ts != last_ts and self._is_time_match(task["expression"], now):
                    last_ts = ts
                    
                    if not task["allow_overlap"] and current_task and not current_task.done():
                        self.logger.warning(f"Skip {task['name']}: overlapping blocked.")
                        continue

                    context = {"scheduled_at": next_trigger, "task_name": task["name"]}
                    current_task = asyncio.create_task(self._wrapper(task["func"], context))

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitor for {task['name']}: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _wrapper(self, func, context):
        """任务执行包装器，包含重试逻辑"""
        execution_record = ExecutionRecord(
            task_name=context["task_name"],
            scheduled_at=context["scheduled_at"],
            started_at=datetime.datetime.now()
        )
        
        # 更新任务状态为运行中
        if context["task_name"] in self.task_registry:
            self.task_registry[context["task_name"]].state = TaskState.RUNNING
        
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                sig = inspect.signature(func)
                kwargs = {"context": context} if "context" in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) else {}
                
                await func(**kwargs)
                
                # 执行成功
                execution_record.success = True
                execution_record.finished_at = datetime.datetime.now()
                execution_record.duration_seconds = (execution_record.finished_at - execution_record.started_at).total_seconds()
                
                self.execution_history.append(execution_record)
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-1000:]
                
                # 重置重试计数
                if context["task_name"] in self.task_registry:
                    self.task_registry[context["task_name"]].retry_count = 0
                
                break
                
            except Exception as e:
                last_error = e
                execution_record.error_message = str(e)
                execution_record.retry_count = retry_count
                
                self.logger.error(
                    f"Task {func.__name__} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}",
                    exc_info=True
                )
                
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    self.logger.info(f"Retrying in {self.retry_delay}s...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Max retries exceeded for task {func.__name__}")
        
        if not execution_record.success:
            execution_record.finished_at = datetime.datetime.now()
            execution_record.duration_seconds = (execution_record.finished_at - execution_record.started_at).total_seconds()
            self.error_history.append(execution_record)
            
            if len(self.error_history) > 100:
                self.error_history = self.error_history[-100:]
            
            if self.on_error:
                try:
                    self.on_error(last_error, execution_record)
                except Exception as callback_err:
                    self.logger.error(f"Error callback failed: {callback_err}")
        
        # 更新任务状态
        if context["task_name"] in self.task_registry:
            self.task_registry[context["task_name"]].state = TaskState.PENDING
            self.task_registry[context["task_name"]].last_execution = execution_record.started_at
            self.task_registry[context["task_name"]].last_result = (
                "success" if execution_record.success else execution_record.error_message
            )
