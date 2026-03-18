"""
AsyncFasterCron: 异步定时任务调度器 v2.0

改进内容：
- 高精度时间控制：动态计算下一触发时刻
- 优雅状态管理：stop() 方法等待任务完成
- 资源管理：追踪活跃任务
- 灵活日志配置：可自定义 logger、格式、文件输出
"""

import asyncio
import inspect
import datetime
from datetime import timedelta
import logging
from typing import Callable, Optional, Set, Dict, Any


class AsyncFasterCron:
    """异步定时任务调度器 - v2.0"""
    
    def __init__(
        self,
        log_level: int = logging.INFO,
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_file: Optional[str] = None,
        custom_logger: Optional[logging.Logger] = None
    ):
        """
        初始化异步调度器
        
        Args:
            log_level: 日志级别 (默认 INFO)
            log_format: 日志格式字符串
            log_file: 可选的日志文件路径
            custom_logger: 可选的自定义 logger 对象
        """
        self.tasks = []
        self._active_tasks: Set[asyncio.Task] = set()
        
        if custom_logger:
            self.logger = custom_logger
        else:
            # 使用 unique name 避免多个实例冲突
            instance_id = id(self)
            self.logger = logging.getLogger(f"FasterCron.Async_{instance_id}")
            self.logger.setLevel(log_level)
            
            # 避免重复添加 handler
            if not self.logger.handlers:
                # 控制台 handler
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(logging.Formatter(log_format))
                self.logger.addHandler(console_handler)
                
                # 文件 handler（可选）
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
        """
        装饰器：注册定时任务
        
        Args:
            expression: Cron 表达式（5 位或 6 位）
            allow_overlap: 是否允许重叠执行
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable):
            self.tasks.append({
                "expression": expression,
                "func": func,
                "allow_overlap": allow_overlap,
                "name": func.__name__
            })
            return func

        return decorator

    def _calculate_next_trigger(self, expression: str, from_time: datetime.datetime = None) -> datetime.datetime:
        """计算表达式在 from_time 之后的下一个触发时间
        
        Args:
            expression: Cron 表达式
            from_time: 起始时间，默认为当前时间
            
        Returns:
            datetime.datetime: 下一个触发时间点
        """
        if from_time is None:
            from_time = datetime.datetime.now()
        
        # 从下一秒开始逐秒检查
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(seconds=1)
        max_iterations = 366 * 24 * 60 * 60  # 1 年内的最大秒数
        
        for _ in range(max_iterations):
            if self._is_time_match(expression, candidate):
                return candidate
            candidate += timedelta(seconds=1)
        
        raise ValueError(f"No trigger time found within 1 year for expression: {expression}")
    
    @staticmethod
    def _is_time_match(expression: str, now: datetime.datetime) -> bool:
        """辅助方法：判断时间是否匹配（避免重复代码）"""
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
        
        # 取消所有监控任务
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
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
                now = datetime.datetime.now()
                
                # 计算下一个触发时间（高精度）
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                delay_seconds = (next_trigger - now).total_seconds()
                
                # 安全 sleep（支持中断，最多加 0.5 秒保证能响应 stop）
                wait_time = min(delay_seconds, 0.5)
                await asyncio.sleep(wait_time)
                
                if not self._running:
                    break
                
                # 触发时刻检查
                now = datetime.datetime.now()
                ts = int(now.timestamp())

                if ts != last_ts and self._is_time_match(task["expression"], now):
                    last_ts = ts
                    
                    # 并发控制检查
                    if not task["allow_overlap"] and current_task and not current_task.done():
                        self.logger.warning(f"Skip {task['name']}: overlapping blocked.")
                        continue

                    context = {"scheduled_at": next_trigger, "task_name": task["name"]}
                    current_task = asyncio.create_task(self._wrapper(task["func"], context))

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitor for {task['name']}: {e}", exc_info=True)
                await asyncio.sleep(1)  # 错误后短暂休息

    async def _wrapper(self, func, context):
        """任务执行包装器，捕获异常"""
        try:
            sig = inspect.signature(func)
            kwargs = {"context": context} if "context" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) else {}
            await func(**kwargs)
        except Exception as e:
            self.logger.error(f"Task {func.__name__} failed: {e}", exc_info=True)
