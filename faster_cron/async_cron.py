"""
AsyncFasterCron: 异步定时任务调度器
"""

import asyncio
import datetime
import importlib
import inspect
import logging
from datetime import timedelta
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import ExecutionRecord, TaskInfo, TaskState


class AsyncFasterCron:
    """异步定时任务调度器。"""

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
        self.tasks: List[Dict[str, Any]] = []
        self.task_registry: Dict[str, TaskInfo] = {}
        self.paused_tasks: Set[str] = set()

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error = on_error
        self.execution_history: List[ExecutionRecord] = []
        self.error_history: List[ExecutionRecord] = []

        if custom_logger is not None:
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
                        file_handler = logging.FileHandler(log_file, encoding="utf-8")
                        file_handler.setFormatter(logging.Formatter(log_format))
                        self.logger.addHandler(file_handler)
                    except Exception as exc:
                        print(f"⚠️ 无法创建日志文件 {log_file}: {exc}")

        self._running = False
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._worker_tasks: Set[asyncio.Task] = set()
        self._one_shot_tasks: Set[asyncio.Task] = set()
        self._active_tasks: Set[asyncio.Task] = set()

    def schedule(self, expression: str, allow_overlap: bool = True):
        """装饰器：注册周期性任务。"""

        def decorator(func: Callable):
            self.add_task(expression, func, allow_overlap=allow_overlap)
            return func

        return decorator

    def add_task(
        self,
        expression: str,
        func: Callable,
        allow_overlap: bool = True,
    ) -> TaskInfo:
        """动态添加周期性任务。"""
        task_info = TaskInfo(
            name=func.__name__,
            expression=expression,
            func=func,
            allow_overlap=allow_overlap,
            state=TaskState.PENDING,
        )

        task_data = {
            "type": "recurring",
            "expression": expression,
            "func": func,
            "allow_overlap": allow_overlap,
            "name": func.__name__,
        }
        self.tasks.append(task_data)
        self.task_registry[func.__name__] = task_info

        if self._running:
            self._start_monitor(task_data)
            self.logger.info(f"Added task '{func.__name__}' while scheduler running")

        return task_info

    def remove_task(self, task_name: str) -> bool:
        """移除指定任务。"""
        if task_name not in self.task_registry:
            return False

        for task in list(self.tasks):
            if task.get("name") != task_name:
                continue

            runtime_task = task.get("runtime_task")
            if runtime_task and not runtime_task.done():
                runtime_task.cancel()

            monitor_task = self._monitor_tasks.pop(task_name, None)
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()

            self.tasks.remove(task)

        self.task_registry.pop(task_name, None)
        self.paused_tasks.discard(task_name)
        self._refresh_active_tasks()
        self.logger.info(f"Removed task '{task_name}'")
        return True

    def pause_task(self, task_name: str) -> bool:
        if task_name not in self.task_registry:
            return False

        self.task_registry[task_name].state = TaskState.PAUSED
        self.paused_tasks.add(task_name)
        self.logger.info(f"Paused task '{task_name}'")
        return True

    def resume_task(self, task_name: str) -> bool:
        if task_name not in self.task_registry:
            return False

        self.task_registry[task_name].state = TaskState.PENDING
        self.paused_tasks.discard(task_name)
        self.logger.info(f"Resumed task '{task_name}'")
        return True

    def disable_task(self, task_name: str) -> bool:
        if task_name not in self.task_registry:
            return False

        self.task_registry[task_name].state = TaskState.DISABLED
        self.paused_tasks.add(task_name)
        self.logger.info(f"Disabled task '{task_name}'")
        return True

    def enable_task(self, task_name: str) -> bool:
        if task_name not in self.task_registry:
            return False

        self.task_registry[task_name].state = TaskState.PENDING
        self.paused_tasks.discard(task_name)
        self.logger.info(f"Enabled task '{task_name}'")
        return True

    def list_tasks(self) -> List[TaskInfo]:
        return list(self.task_registry.values())

    def get_task(self, task_name: str) -> Optional[TaskInfo]:
        return self.task_registry.get(task_name)

    def _refresh_active_tasks(self):
        self._worker_tasks = {task for task in self._worker_tasks if not task.done()}
        self._one_shot_tasks = {task for task in self._one_shot_tasks if not task.done()}
        self._monitor_tasks = {
            name: task for name, task in self._monitor_tasks.items() if not task.done()
        }
        self._active_tasks = set(self._monitor_tasks.values()) | self._worker_tasks | self._one_shot_tasks

    def _start_monitor(self, task: Dict[str, Any]):
        if task.get("type") != "recurring":
            return

        existing = self._monitor_tasks.get(task["name"])
        if existing and not existing.done():
            return

        monitor = asyncio.create_task(self._monitor(task), name=f"monitor:{task['name']}")
        self._monitor_tasks[task["name"]] = monitor
        self._refresh_active_tasks()

    def _create_worker(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any],
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        execution_type: str = "recurring",
    ) -> asyncio.Task:
        worker = asyncio.create_task(
            self._execute_task(task, context, args=args, kwargs=kwargs, execution_type=execution_type),
            name=f"worker:{task['name']}",
        )
        self._worker_tasks.add(worker)
        worker.add_done_callback(lambda _: self._refresh_active_tasks())
        self._refresh_active_tasks()
        return worker

    def _calculate_next_trigger(
        self,
        expression: str,
        from_time: Optional[datetime.datetime] = None,
    ) -> datetime.datetime:
        if from_time is None:
            from_time = datetime.datetime.now()

        candidate = from_time.replace(microsecond=0) + timedelta(seconds=1)
        max_iterations = 366 * 24 * 60 * 60

        for _ in range(max_iterations):
            if self._is_time_match(expression, candidate):
                return candidate
            candidate += timedelta(seconds=1)

        raise ValueError(f"No trigger time found within 1 year for expression: {expression}")

    @staticmethod
    def _is_time_match(expression: str, now: datetime.datetime) -> bool:
        from .base import CronBase

        return CronBase.is_time_match(expression, now)

    async def start(self):
        """启动调度器；有周期性任务时会持续运行直到 stop()。"""
        if self._running:
            return None

        self._running = True
        for task in list(self.tasks):
            if task.get("type") == "recurring":
                self._start_monitor(task)

        self._refresh_active_tasks()
        if not self._active_tasks:
            self._running = False
            return None

        try:
            while self._running:
                self._refresh_active_tasks()
                if not self._active_tasks and not any(t.get("type") == "recurring" for t in self.tasks):
                    break
                await asyncio.sleep(0.1)
        finally:
            self._refresh_active_tasks()

        return None

    async def run(self):
        """兼容别名：等同于 start()。"""
        return await self.start()

    async def stop(self):
        """优雅停止调度器。"""
        self.logger.info("Stopping scheduler...")
        self._running = False

        for monitor in list(self._monitor_tasks.values()):
            if not monitor.done():
                monitor.cancel()

        for one_shot in list(self._one_shot_tasks):
            if not one_shot.done():
                one_shot.cancel()

        if self._monitor_tasks:
            await asyncio.gather(*self._monitor_tasks.values(), return_exceptions=True)
        if self._one_shot_tasks:
            await asyncio.gather(*self._one_shot_tasks, return_exceptions=True)
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        self._monitor_tasks.clear()
        self._worker_tasks.clear()
        self._one_shot_tasks.clear()
        self._refresh_active_tasks()
        self.logger.info("Scheduler stopped")

    async def _monitor(self, task: Dict[str, Any]):
        last_trigger_ts = -1
        current_task: Optional[asyncio.Task] = None

        while self._running:
            try:
                if task["name"] not in self.task_registry:
                    break

                if task["name"] in self.paused_tasks:
                    await asyncio.sleep(0.2)
                    continue

                now = datetime.datetime.now()
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                delay_seconds = max(0.0, (next_trigger - now).total_seconds())
                await asyncio.sleep(min(delay_seconds, 0.5))

                if not self._running or task["name"] in self.paused_tasks:
                    continue

                now = datetime.datetime.now()
                current_ts = int(now.timestamp())
                if current_ts == last_trigger_ts:
                    continue

                if not self._is_time_match(task["expression"], now):
                    continue

                last_trigger_ts = current_ts

                if not task["allow_overlap"] and current_task and not current_task.done():
                    self.logger.warning(f"Skip {task['name']}: overlapping blocked.")
                    continue

                context = {
                    "scheduled_at": next_trigger,
                    "task_name": task["name"],
                }
                current_task = self._create_worker(task, context)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.error(f"Error in monitor for {task['name']}: {exc}", exc_info=True)
                await asyncio.sleep(0.5)

    def _prepare_invocation(
        self,
        func: Callable,
        context: Dict[str, Any],
        args: Tuple[Any, ...],
        kwargs: Optional[Dict[str, Any]],
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        args_list = list(args)
        call_kwargs = dict(kwargs or {})
        signature = inspect.signature(func)
        parameters = list(signature.parameters.values())

        if "context" in signature.parameters:
            call_kwargs.setdefault("context", context)
        elif any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
            call_kwargs.setdefault("context", context)
        elif not args_list:
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            if positional and positional[0].name not in call_kwargs:
                args_list.insert(0, context)

        return tuple(args_list), call_kwargs

    async def _call_func(
        self,
        func: Callable,
        context: Dict[str, Any],
        args: Tuple[Any, ...],
        kwargs: Optional[Dict[str, Any]],
    ):
        call_args, call_kwargs = self._prepare_invocation(func, context, args, kwargs)
        result = func(*call_args, **call_kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _execute_task(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any],
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        execution_type: str = "recurring",
    ):
        task_name = task["name"]
        func = task["func"]
        actual_context = dict(context)
        if execution_type != "recurring":
            actual_context["execution_type"] = execution_type

        execution_record = ExecutionRecord(
            task_name=task_name,
            scheduled_at=actual_context["scheduled_at"],
            started_at=datetime.datetime.now(),
        )

        task_info = self.task_registry.get(task_name)
        if task_info is not None:
            task_info.state = TaskState.RUNNING

        retry_count = 0
        last_error: Optional[Exception] = None

        while retry_count <= self.max_retries:
            try:
                await self._call_func(func, actual_context, args, kwargs)

                execution_record.success = True
                execution_record.finished_at = datetime.datetime.now()
                execution_record.duration_seconds = (
                    execution_record.finished_at - execution_record.started_at
                ).total_seconds()
                self.execution_history.append(execution_record)
                self.execution_history = self.execution_history[-1000:]

                if task_info is not None:
                    task_info.retry_count = 0
                break
            except Exception as exc:
                last_error = exc
                execution_record.error_message = str(exc)
                execution_record.retry_count = retry_count
                if task_info is not None:
                    task_info.retry_count = retry_count + 1

                self.logger.error(
                    f"Task {func.__name__} failed (attempt {retry_count + 1}/{self.max_retries + 1}): {exc}",
                    exc_info=True,
                )

                retry_count += 1
                if retry_count <= self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Max retries exceeded for task {func.__name__}")

        if not execution_record.success:
            execution_record.finished_at = datetime.datetime.now()
            execution_record.duration_seconds = (
                execution_record.finished_at - execution_record.started_at
            ).total_seconds()
            self.error_history.append(execution_record)
            self.error_history = self.error_history[-100:]

            if self.on_error and last_error is not None:
                try:
                    self.on_error(last_error, execution_record)
                except Exception as callback_exc:
                    self.logger.error(f"Error callback failed: {callback_exc}")

        if task_info is not None:
            task_info.state = TaskState.PENDING if execution_type == "recurring" else TaskState.COMPLETED
            task_info.last_execution = execution_record.started_at
            task_info.last_result = "success" if execution_record.success else execution_record.error_message

        if execution_type != "recurring":
            self.task_registry.pop(task_name, None)
            self.tasks = [task_data for task_data in self.tasks if task_data is not task]

    def once_in(
        self,
        seconds: float,
        func: Optional[Callable] = None,
        *,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ):
        target_time = datetime.datetime.now() + timedelta(seconds=seconds)
        return self.run_at(
            target_time,
            func,
            args=args,
            kwargs=kwargs,
            execution_type="one_time_delayed",
        )

    def run_at(
        self,
        target_time: datetime.datetime,
        func: Optional[Callable] = None,
        *,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        execution_type: str = "one_time_scheduled",
    ):
        if func is not None:
            self._schedule_one_shot(
                target_time,
                func,
                args=args or (),
                kwargs=kwargs or {},
                execution_type=execution_type,
            )
            return func

        return partial(
            self.run_at,
            target_time,
            args=args,
            kwargs=kwargs,
            execution_type=execution_type,
        )

    def _schedule_one_shot(
        self,
        target_time: datetime.datetime,
        func: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        execution_type: str,
    ) -> TaskInfo:
        task_info = TaskInfo(
            name=func.__name__,
            expression="",
            func=func,
            allow_overlap=False,
            state=TaskState.PENDING,
        )
        task_data = {
            "type": "one_shot",
            "name": func.__name__,
            "func": func,
            "target_time": target_time,
            "args": tuple(args),
            "kwargs": dict(kwargs),
            "execution_type": execution_type,
        }
        self.tasks.append(task_data)
        self.task_registry[func.__name__] = task_info

        runtime_task = asyncio.create_task(self._execute_one_shot(task_data), name=f"one-shot:{func.__name__}")
        task_data["runtime_task"] = runtime_task
        self._one_shot_tasks.add(runtime_task)
        runtime_task.add_done_callback(lambda _: self._refresh_active_tasks())
        self._refresh_active_tasks()
        self.logger.info(f"One-shot task '{func.__name__}' scheduled at {target_time}")
        return task_info

    async def _execute_one_shot(self, task: Dict[str, Any]):
        try:
            delay_seconds = max(0.0, (task["target_time"] - datetime.datetime.now()).total_seconds())
            if delay_seconds:
                await asyncio.sleep(delay_seconds)

            context = {
                "scheduled_at": task["target_time"],
                "task_name": task["name"],
            }
            await self._execute_task(
                task,
                context,
                args=task.get("args", ()),
                kwargs=task.get("kwargs", {}),
                execution_type=task["execution_type"],
            )
        except asyncio.CancelledError:
            self.task_registry.pop(task["name"], None)
            self.tasks = [task_data for task_data in self.tasks if task_data is not task]
            raise

    def load_from_yaml(self, filepath: str) -> int:
        try:
            yaml = importlib.import_module("yaml")
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for load_from_yaml(). Install 'pyyaml' or 'faster-cron[yaml]'."
            ) from exc

        with open(filepath, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        return self._load_tasks(config)

    def load_from_json(self, filepath: str) -> int:
        import json

        with open(filepath, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        return self._load_tasks(config)

    def _load_tasks(self, config: Dict[str, Any]) -> int:
        tasks_config = config.get("tasks", [])
        if not isinstance(tasks_config, list):
            raise ValueError("'tasks' must be a list in configuration")

        loaded_count = 0
        for task_config in tasks_config:
            module_name = task_config.get("module")
            function_name = task_config.get("function")
            expression = task_config.get("expression")
            allow_overlap = task_config.get("allow_overlap", True)

            if not module_name or not function_name or not expression:
                self.logger.error(f"Invalid task config, missing required fields: {task_config}")
                continue

            try:
                module = importlib.import_module(module_name)
                func = getattr(module, function_name)
            except (ImportError, AttributeError) as exc:
                self.logger.error(f"Failed to import {module_name}.{function_name}: {exc}")
                continue

            self.add_task(expression, func, allow_overlap=allow_overlap)
            loaded_count += 1
            self.logger.info(f"Loaded task '{function_name}' from {module_name}")

        return loaded_count
