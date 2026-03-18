"""
FasterCron: 同步多线程定时任务调度器 v2.0

完整改进：
- 高精度时间控制
- 优雅状态管理 (stop)
- 灵活日志配置
- 动态任务管理 (add/remove/pause/resume/list)
- 异常处理与重试机制
- 资源管理
- 一次性任务支持 (once_in, run_at)
"""

import threading
import time
import datetime
from datetime import timedelta
import logging
import inspect
from typing import List, Dict, Any, Callable, Optional, Set
from functools import partial

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
        """移除指定任务"""
        if task_name not in self.task_registry:
            return False
        
        self.tasks = [t for t in self.tasks if t["name"] != task_name]
        del self.task_registry[task_name]
        
        # 如果正在运行，暂停它
        self.paused_tasks.discard(task_name)
        
        self.logger.info(f"Removed task '{task_name}'")
        return True

    def pause_task(self, task_name: str) -> bool:
        """暂停任务"""
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

    def start(self):
        """启动调度器"""
        self._running = True
        for task in self.tasks:
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(task,),
                daemon=True
            )
            self._monitors.append(monitor_thread)
            monitor_thread.start()
        
        # 等待所有监控线程完成
        for thread in self._monitors:
            thread.join()
        self._monitors.clear()

    def stop(self):
        """优雅关闭调度器"""
        self.logger.info("Stopping scheduler...")
        self._running = False
        self.logger.info("Scheduler stopped")

    def _monitor_loop(self, task):
        """监控单个任务的执行循环"""
        last_trigger_ts = 0
        while self._running:
            try:
                # 检查是否暂停
                if task["name"] in self.paused_tasks:
                    time.sleep(1.0)
                    continue
                
                now = datetime.datetime.now()
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                delay_seconds = (next_trigger - now).total_seconds()
                
                wait_time = min(delay_seconds, 0.5)
                time.sleep(wait_time)
                
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

    # ========== 一次性任务支持 ==========
    
    def once_in(self, seconds: float, func: Optional[Callable] = None):
        """
        延迟 N 秒后执行一次的装饰器
        
        Args:
            seconds: 延迟秒数
            
        Example:
            @cron.once_in(300)  # 5 分钟后
            def send_email(ctx):
                ...
        """
        target_time = datetime.datetime.now() + timedelta(seconds=seconds)
        return self.run_at(target_time)(func)

    def run_at(self, target_time: datetime.datetime, func: Optional[Callable] = None):
        """
        指定时间执行一次的装饰器
        
        Args:
            target_time: 目标执行时间（datetime 对象）
            
        Example:
            @cron.run_at(datetime.now() + timedelta(hours=1))
            def generate_report(ctx):
                ...
        """
        if func is not None:
            # 直接作为装饰器使用 - 立即注册并调度
            sig = inspect.signature(func)
            
            # 创建执行记录
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
            
            # 创建任务信息
            task_info = TaskInfo(
                name=func.__name__,
                expression="",
                func=func,
                allow_overlap=False,
                state=TaskState.PENDING,
                priority=0
            )
            
            # 添加到任务列表（标记为一次性任务）
            self.tasks.append({
                "target_time": target_time,
                "func": func,
                "execution_record": execution_record,
                "max_retries": self.max_retries,
                "retry_delay": self.retry_delay,
                "on_error": self.on_error,
                "logger": self.logger,
                "type": "one_shot"
            })
            
            # 注册到任务管理
            self.task_registry[func.__name__] = task_info
            
            # 立即启动后台线程执行一次性的任务
            if self._running:
                threading.Thread(
                    target=self._execute_one_shot,
                    args=(task_info, execution_record),
                    daemon=True
                ).start()
            
            self.logger.info(f"One-shot task '{func.__name__}' scheduled at {target_time}")
            return execution_record
        
        # 如果只传了 target_time，返回一个部分函数用于链式调用
        return partial(self.run_at, target_time)
    
    def _execute_one_shot(self, task_info: TaskInfo, execution_record: ExecutionRecord):
        """执行一次性任务"""
        func = task_info.func
        target_time = execution_record.scheduled_at
        max_retries = self.max_retries
        retry_delay = self.retry_delay
        on_error = self.on_error
        logger = self.logger
        
        # 等待到指定时间
        now = datetime.datetime.now()
        delay_seconds = (target_time - now).total_seconds()
        
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        
        # 检查是否已被取消
        if not self._running:
            return
        
        # 更新执行记录
        execution_record.started_at = datetime.datetime.now()
        
        # 设置上下文
        context = {"scheduled_at": target_time, "task_name": task_info.name}
        
        # 重试逻辑
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                sig = inspect.signature(func)
                kwargs = {"context": context} if "context" in sig.parameters else {}
                
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
                    f"One-shot task '{func.__name__}' completed in {execution_record.duration_seconds:.2f}s"
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
                    logger.error(f"Max retries exceeded for one-shot task '{func.__name__}'")
        
        # 记录失败
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
        
        # 清理任务
        self.task_registry.pop(task_info.name, None)
        self.tasks = [t for t in self.tasks if t.get("type") != "one_shot" or t.get("func") != func]

    # ========== 配置文件加载支持 ==========
    
    def load_from_yaml(self, filepath: str):
        """从 YAML 文件加载任务配置
        
        Args:
            filepath: YAML 配置文件路径
            
        Example:
            cron = FasterCron()
            cron.load_from_yaml("tasks.yaml")
        """
        import yaml
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return self._load_tasks(config)
    
    def load_from_json(self, filepath: str):
        """从 JSON 文件加载任务配置
        
        Args:
            filepath: JSON 配置文件路径
            
        Example:
            cron = FasterCron()
            cron.load_from_json("tasks.json")
        """
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return self._load_tasks(config)
    
    def _load_tasks(self, config: Dict[str, Any]):
        """通用配置加载逻辑"""
        tasks_config = config.get('tasks', [])
        
        if not tasks_config:
            raise ValueError("No tasks found in configuration")
        
        for task_config in tasks_config:
            try:
                module_name = task_config.get('module')
                function_name = task_config.get('function')
                expression = task_config.get('expression')
                allow_overlap = task_config.get('allow_overlap', True)
                priority = task_config.get('priority', 0)
                
                # 导入模块和函数
                import importlib
                module = importlib.import_module(module_name)
                func = getattr(module, function_name)
                
                # 注册任务
                self.add_task(expression, func, allow_overlap, priority)
                
                self.logger.info(f"Loaded task '{function_name}' from {module_name}")
                
            except ImportError as e:
                self.logger.error(f"Failed to import {module_name}.{function_name}: {e}")
            except Exception as e:
                self.logger.error(f"Error loading task config {task_config}: {e}")
        
        return tasks_config
