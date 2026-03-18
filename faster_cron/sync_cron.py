"""
FasterCron: 同步多线程定时任务调度器 v2.0

完整改进：
- 高精度时间控制
- 优雅状态管理 (stop)
- 灵活日志配置
- 动态任务管理 (add/remove/pause/resume/list)
- 异常处理与重试机制
- 资源管理
"""

import threading
import time
import datetime
from datetime import timedelta
import logging
import inspect
from typing import List, Dict, Any, Callable, Optional

from .models import TaskInfo, TaskState, ExecutionRecord


class FasterCron:
    """同步多线程定时任务调度器 - v2.0"""
    
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
        初始化同步调度器
        
        Args:
            log_level: 日志级别 (默认 INFO)
            log_format: 日志格式字符串
            log_file: 可选的日志文件路径
            custom_logger: 可选的自定义 logger 对象
            max_retries: 最大重试次数 (默认 3)
            retry_delay: 重试间隔秒数 (默认 5.0)
            on_error: 错误回调函数 (func: error, record -> None)
        """
        self.tasks: List[Dict[str, Any]] = []
        
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
            self.logger = logging.getLogger(f"FasterCron.Sync_{instance_id}")
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
        self._monitors: List[threading.Thread] = []

    def schedule(self, expression: str, allow_overlap: bool = True):
        """注册同步任务"""
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
        """动态添加任务"""
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
            "priority": priority,
            "last_worker": None
        })
        self.task_registry[func.__name__] = task_info
        
        if self._running:
            self.logger.info(f"Added task '{func.__name__}' while scheduler running")
        
        return task_info

    def remove_task(self, task_name: str) -> bool:
        """通过任务名移除任务"""
        if task_name not in self.task_registry:
            return False
        
        self.tasks = [t for t in self.tasks if t["name"] != task_name]
        del self.task_registry[task_name]
        
        self.paused_tasks.discard(task_name)
        
        self.logger.info(f"Removed task '{task_name}'")
        return True

    def pause_task(self, task_name: str) -> bool:
        """暂停指定任务"""
        if task_name not in self.task_registry:
            return False
        
        task_info = self.task_registry[task_name]
        task_info.state = TaskState.PAUSED
        self.paused_tasks.add(task_name)
        
        self.logger.info(f"Paused task '{task_name}'")
        return True

    def resume_task(self, task_name: str) -> bool:
        """恢复暂停的任务"""
        if task_name not in self.task_registry:
            return False
        
        task_info = self.task_registry[task_name]
        task_info.state = TaskState.PENDING
        self.paused_tasks.discard(task_name)
        
        self.logger.info(f"Resumed task '{task_name}'")
        return True

    def disable_task(self, task_name: str) -> bool:
        """禁用任务"""
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

    def run(self, wait_on_exit: bool = True):
        """阻塞启动所有任务监控器"""
        self._running = True
        self.logger.info(f"FasterCron (Sync Mode) started with {len(self.tasks)} tasks.")

        for task in self.tasks:
            t = threading.Thread(
                target=self._monitor_loop,
                args=(task,),
                name=f"Monitor-{task['name']}",
                daemon=False
            )
            t.start()
            self._monitors.append(t)

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received SIGINT, shutting down...")
            self._running = False
            
            if wait_on_exit:
                self.logger.info(f"Waiting for {len(self._monitors)} threads to finish...")
                for t in self._monitors:
                    t.join(timeout=5)
                self._monitors.clear()
        
        self.logger.info("FasterCron stopped")

    def stop(self, wait_timeout: float = 30.0) -> None:
        """优雅关闭调度器"""
        self.logger.info("Stopping scheduler...")
        self._running = False
        
        for thread in self._monitors:
            thread.join(timeout=wait_timeout / max(len(self._monitors), 1))
        
        self._monitors.clear()
        self.logger.info("Scheduler stopped")

    def _monitor_loop(self, task: Dict[str, Any]):
        """每个任务独立的监听循环（高精度版本）"""
        last_trigger_ts = 0

        while self._running:
            try:
                # 检查是否暂停
                if task["name"] in self.paused_tasks:
                    time.sleep(1.0)
                    continue
                
                now = datetime.datetime.now()
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                sleep_seconds = (next_trigger - now).total_seconds()
                
                safe_sleep = max(0.01, min(sleep_seconds, 0.5))
                time.sleep(safe_sleep)
                
                if not self._running:
                    break
                
                now = datetime.datetime.now()
                current_ts = int(now.timestamp())

                if current_ts != last_trigger_ts and self._is_time_match(task["expression"], now):
                    last_trigger_ts = current_ts

                    # 并发控制
                    if not task["allow_overlap"]:
                        prev_worker = task.get("last_worker")
                        if prev_worker and prev_worker.is_alive():
                            self.logger.warning(f"Task '{task['name']}' is still running. Skipping this cycle.")
                            continue

                    context = {"scheduled_at": next_trigger, "task_name": task["name"]}
                    worker_thread = threading.Thread(
                        target=self._execute_task,
                        args=(task["func"], context),
                        name=f"Worker-{task['name']}-{current_ts}",
                        daemon=True
                    )
                    task["last_worker"] = worker_thread
                    worker_thread.start()

            except Exception as e:
                self.logger.error(f"Error in monitor loop for {task['name']}: {e}", exc_info=True)
                time.sleep(1)

    def _execute_task(self, func: Callable, context: Dict):
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
                kwargs = {"context": context} if 'context' in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) else {}
                
                func(**kwargs)
                
                # 执行成功
                execution_record.success = True
                execution_record.finished_at = datetime.datetime.now()
                execution_record.duration_seconds = (execution_record.finished_at - execution_record.started_at).total_seconds()
                
                self.execution_history.append(execution_record)
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-1000:]
                
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
                    time.sleep(self.retry_delay)
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
        
        if context["task_name"] in self.task_registry:
            self.task_registry[context["task_name"]].state = TaskState.PENDING
            self.task_registry[context["task_name"]].last_execution = execution_record.started_at
            self.task_registry[context["task_name"]].last_result = (
                "success" if execution_record.success else execution_record.error_message
            )
