"""
FasterCron: 同步多线程定时任务调度器 v2.0

改进内容：
- 高精度时间控制：动态计算下一触发时刻
- 优雅状态管理：stop() 方法等待线程完成
- 资源管理：非守护线程 + 优雅退出
"""

import threading
import time
import datetime
from datetime import timedelta
import logging
import inspect
from typing import List, Dict, Any, Callable


class FasterCron:
    """同步多线程定时任务调度器 - v2.0"""
    
    def __init__(self, log_level=logging.INFO):
        """
        初始化同步调度器
        
        Args:
            log_level: 日志级别
        """
        self.tasks: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("FasterCron.Sync")
        self.logger.setLevel(log_level)
        self._running = False
        self._monitors: List[threading.Thread] = []

    def schedule(self, expression: str, allow_overlap: bool = True):
        """
        注册同步任务
        
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
                "name": func.__name__,
                "last_worker": None  # 用于追踪此任务的上一个执行线程
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

    def run(self, wait_on_exit: bool = True):
        """
        阻塞启动所有任务监控器
        
        Args:
            wait_on_exit: 程序退出时是否等待所有任务完成
        """
        self._running = True
        self.logger.info(f"FasterCron (Sync Mode) started with {len(self.tasks)} tasks.")

        for task in self.tasks:
            t = threading.Thread(
                target=self._monitor_loop,
                args=(task,),
                name=f"Monitor-{task['name']}",
                daemon=False  # 改为非守护线程，确保等待完成
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
                    t.join(timeout=5)  # 每个线程最多等 5 秒
                self._monitors.clear()
        
        self.logger.info("FasterCron stopped")

    def stop(self, wait_timeout: float = 30.0) -> None:
        """
        优雅关闭调度器
        
        Args:
            wait_timeout: 等待活跃任务完成的超时时间（秒）
        """
        self.logger.info("Stopping scheduler...")
        self._running = False
        
        # 等待所有线程完成
        for thread in self._monitors:
            thread.join(timeout=wait_timeout / max(len(self._monitors), 1))
        
        self._monitors.clear()
        self.logger.info("Scheduler stopped")

    def _monitor_loop(self, task: Dict[str, Any]):
        """每个任务独立的监听循环（高精度版本）"""
        last_trigger_ts = 0

        while self._running:
            try:
                now = datetime.datetime.now()
                
                # 计算下一个触发时间（高精度）
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                sleep_seconds = (next_trigger - now).total_seconds()
                
                # 安全 sleep（支持中断，最多加 0.5 秒保证能响应 stop）
                safe_sleep = max(0.01, min(sleep_seconds, 0.5))  # 至少睡 0.01 秒
                time.sleep(safe_sleep)
                
                if not self._running:
                    break
                
                # 触发时刻检查
                now = datetime.datetime.now()
                current_ts = int(now.timestamp())

                if current_ts != last_trigger_ts and self._is_time_match(task["expression"], now):
                    last_trigger_ts = current_ts

                    # 并发控制
                    if not task["allow_overlap"]:
                        # 单例模式：检查上一个工作线程是否还在跑
                        prev_worker = task.get("last_worker")
                        if prev_worker and prev_worker.is_alive():
                            self.logger.warning(f"Task '{task['name']}' is still running. Skipping this cycle.")
                            continue

                    # 执行任务
                    context = {"scheduled_at": next_trigger, "task_name": task["name"]}
                    worker_thread = threading.Thread(
                        target=self._execute_task,
                        args=(task["func"], context),
                        name=f"Worker-{task['name']}-{current_ts}",
                        daemon=True
                    )
                    task["last_worker"] = worker_thread  # 记录引用以便下次检查
                    worker_thread.start()

            except Exception as e:
                self.logger.error(f"Error in monitor loop for {task['name']}: {e}", exc_info=True)
                time.sleep(1)  # 错误后短暂休息

    def _execute_task(self, func: Callable, context: Dict):
        """具体的任务执行包装器"""
        try:
            # 智能参数注入
            sig = inspect.signature(func)
            if 'context' in sig.parameters:
                func(context=context)
            else:
                func()
        except Exception as e:
            self.logger.error(f"Error in task '{func.__name__}': {e}", exc_info=True)
