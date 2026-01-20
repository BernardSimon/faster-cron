import threading
import time
import datetime
import logging
import inspect
from typing import List, Dict, Any, Callable
from .base import CronBase


class FasterCron:
    def __init__(self, log_level=logging.INFO):
        self.tasks: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("FasterCron.Sync")
        self.logger.setLevel(log_level)
        self._running = False
        self._monitors: List[threading.Thread] = []

    def schedule(self, expression: str, allow_overlap: bool = True):
        """
        注册同步任务。
        allow_overlap 为 True 时，会通过开启新线程来实现并发执行。
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

    def run(self):
        """阻塞启动所有任务监控器"""
        self._running = True
        self.logger.info(f"FasterCron (Sync Mode) started with {len(self.tasks)} tasks.")

        for task in self.tasks:
            t = threading.Thread(
                target=self._monitor_loop,
                args=(task,),
                name=f"Monitor-{task['name']}",
                daemon=True
            )
            t.start()
            self._monitors.append(t)

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("FasterCron stopping...")
            self._running = False

    def _monitor_loop(self, task: Dict[str, Any]):
        """每个任务独立的监听循环"""
        last_trigger_ts = 0

        while self._running:
            now = datetime.datetime.now()
            current_ts = int(now.timestamp())

            # 1. 时间匹配检查 (确保每秒只触发一次)
            if current_ts != last_trigger_ts and CronBase.is_time_match(task["expression"], now):
                last_trigger_ts = current_ts

                # 2. 并发控制
                if not task["allow_overlap"]:
                    # 单例模式：检查上一个工作线程是否还在跑
                    prev_worker = task.get("last_worker")
                    if prev_worker and prev_worker.is_alive():
                        self.logger.warning(f"Task '{task['name']}' is still running. Skipping this cycle.")
                        continue

                # 3. 执行任务
                # 无论是并发还是单例，都开启新线程执行工作函数，避免阻塞监控循环
                context = {"scheduled_at": now, "task_name": task["name"]}
                worker_thread = threading.Thread(
                    target=self._execute_task,
                    args=(task["func"], context),
                    name=f"Worker-{task['name']}-{current_ts}",
                    daemon=True
                )
                task["last_worker"] = worker_thread  # 记录引用以便下次检查
                worker_thread.start()

            # 4. 精确对齐到下一秒
            sleep_time = 1.0 - (now.microsecond / 1_000_000) + 0.01
            time.sleep(sleep_time)

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