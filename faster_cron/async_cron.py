import asyncio
import inspect
import datetime
import logging
from typing import Callable, Optional
from .base import CronBase


class AsyncFasterCron:
    def __init__(self, log_level=logging.INFO):
        self.tasks = []
        self.logger = logging.getLogger("FasterCron.Async")
        self.logger.setLevel(log_level)
        self._running = False

    def schedule(self, expression: str, allow_overlap: bool = True):
        def decorator(func: Callable):
            self.tasks.append({
                "expression": expression,
                "func": func,
                "allow_overlap": allow_overlap,
                "name": func.__name__
            })
            return func

        return decorator

    async def start(self):
        self._running = True
        listeners = [self._monitor(task) for task in self.tasks]
        await asyncio.gather(*listeners)

    async def _monitor(self, task):
        last_ts = 0
        current_task: Optional[asyncio.Task] = None

        while self._running:
            now = datetime.datetime.now()
            ts = int(now.timestamp())

            if ts != last_ts and CronBase.is_time_match(task["expression"], now):
                last_ts = ts
                if not task["allow_overlap"] and current_task and not current_task.done():
                    self.logger.warning(f"Skip {task['name']}: overlapping blocked.")
                    continue

                context = {"scheduled_at": now, "task_name": task["name"]}
                current_task = asyncio.create_task(self._wrapper(task["func"], context))

            await asyncio.sleep(1.0 - (now.microsecond / 1_000_000) + 0.01)

    async def _wrapper(self, func, context):
        try:
            sig = inspect.signature(func)
            kwargs = {"context": context} if "context" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()) else {}
            await func(**kwargs)
        except Exception as e:
            self.logger.error(f"Task {func.__name__} failed: {e}", exc_info=True)