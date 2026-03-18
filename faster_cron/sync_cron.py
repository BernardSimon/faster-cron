"""
jFasterCron: 同步多线程定时任务调度器
"""

import datetime
import importlib
import inspect
import json
import logging
import threading
import time
from datetime import timedelta
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import ExecutionRecord, TaskInfo, TaskState


class FasterCron:
    """同步多线程定时任务调度器。"""

    def __init__(
        self,
        log_level: int = logging.INFO,
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_file: Optional[str] = None,
        custom_logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        on_error: Optional[Callable[[Exception, ExecutionRecord], None]] = None,
        wait_on_exit: bool = True,
    ):
        self.tasks: List[Dict[str, Any]] = []
        self.task_registry: Dict[str, TaskInfo] = {}
        self.paused_tasks: Set[str] = set()

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error = on_error
        self.execution_history: List[ExecutionRecord] = []
        self.error_history: List[ExecutionRecord] = []
        self.wait_on_exit = wait_on_exit

        if custom_logger is not None:
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
                        file_handler = logging.FileHandler(log_file, encoding="utf-8")
                        file_handler.setFormatter(logging.Formatter(log_format))
                        self.logger.addHandler(file_handler)
                    except Exception as exc:
                        print(f"⚠️ 无法创建日志文件 {log_file}: {exc}")

        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._monitors: Dict[str, threading.Thread] = {}
        self._workers: Set[threading.Thread] = set()
        self._timers: Set[threading.Thread] = set()

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
            "last_worker": None,
            "cancel_event": threading.Event(),
        }

        with self._lock:
            self.tasks.append(task_data)
            self.task_registry[func.__name__] = task_info

        if self._running:
            self._start_monitor(task_data)
            self.logger.info(f"Added task '{func.__name__}' while scheduler running")

        return task_info

    def remove_task(self, task_name: str) -> bool:
        if task_name not in self.task_registry:
            return False

        with self._lock:
            for task in list(self.tasks):
                if task.get("name") != task_name:
                    continue
                cancel_event = task.get("cancel_event")
                if cancel_event is not None:
                    cancel_event.set()
                self.tasks.remove(task)

            self.task_registry.pop(task_name, None)
            self.paused_tasks.discard(task_name)
            self._monitors.pop(task_name, None)

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

    def _start_monitor(self, task: Dict[str, Any]):
        if task.get("type") != "recurring":
            return

        existing = self._monitors.get(task["name"])
        if existing and existing.is_alive():
            return

        monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(task,),
            name=f"Monitor-{task['name']}",
            daemon=True,
        )
        self._monitors[task["name"]] = monitor_thread
        monitor_thread.start()

    def start(self, wait_on_exit: Optional[bool] = None):
        """启动调度器。"""
        if self._running:
            return None

        effective_wait = self.wait_on_exit if wait_on_exit is None else wait_on_exit
        self._running = True
        self._stop_event.clear()

        for task in list(self.tasks):
            if task.get("type") == "recurring":
                self._start_monitor(task)

        if effective_wait:
            try:
                while self._running:
                    time.sleep(0.1)
            finally:
                self._join_threads()

        return None

    def run(self, wait_on_exit: Optional[bool] = None):
        """兼容入口：等同于 start()。"""
        return self.start(wait_on_exit=wait_on_exit)

    def stop(self, wait_timeout: Optional[float] = None):
        """优雅停止调度器和待执行的一次性任务。"""
        self.logger.info("Stopping scheduler...")
        self._running = False
        self._stop_event.set()

        with self._lock:
            for task in self.tasks:
                cancel_event = task.get("cancel_event")
                if cancel_event is not None:
                    cancel_event.set()

        self._join_threads(wait_timeout=wait_timeout)
        self.logger.info("Scheduler stopped")

    def _join_threads(self, wait_timeout: Optional[float] = None):
        deadline = time.time() + wait_timeout if wait_timeout is not None else None

        for name, monitor in list(self._monitors.items()):
            timeout = None if deadline is None else max(0.0, deadline - time.time())
            monitor.join(timeout=timeout)
            if not monitor.is_alive():
                self._monitors.pop(name, None)

        if self.wait_on_exit or wait_timeout is not None:
            for thread_set in (self._timers, self._workers):
                for thread in list(thread_set):
                    timeout = None if deadline is None else max(0.0, deadline - time.time())
                    thread.join(timeout=timeout)
                    if not thread.is_alive():
                        thread_set.discard(thread)

    def _monitor_loop(self, task: Dict[str, Any]):
        last_trigger_ts = -1

        while self._running and not task["cancel_event"].is_set():
            try:
                if task["name"] not in self.task_registry:
                    break

                if task["name"] in self.paused_tasks:
                    if task["cancel_event"].wait(0.2):
                        break
                    continue

                now = datetime.datetime.now()
                next_trigger = self._calculate_next_trigger(task["expression"], now)
                delay_seconds = max(0.0, (next_trigger - now).total_seconds())
                if self._stop_event.wait(timeout=min(delay_seconds, 0.5)):
                    break
                if task["cancel_event"].is_set() or not self._running:
                    break

                now = datetime.datetime.now()
                current_ts = int(now.timestamp())
                if current_ts == last_trigger_ts:
                    continue

                if not self._is_time_match(task["expression"], now):
                    continue

                last_trigger_ts = current_ts

                if not task["allow_overlap"]:
                    previous_worker = task.get("last_worker")
                    if previous_worker and previous_worker.is_alive():
                        self.logger.warning(
                            f"Task '{task['name']}' is still running. Skipping this cycle."
                        )
                        continue

                context = {
                    "scheduled_at": next_trigger,
                    "task_name": task["name"],
                }
                worker = threading.Thread(
                    target=self._execute_task,
                    args=(task, context),
                    name=f"Worker-{task['name']}-{current_ts}",
                    daemon=True,
                )
                task["last_worker"] = worker
                self._workers.add(worker)
                worker.start()

            except Exception as exc:
                self.logger.error(f"Error in monitor loop for {task['name']}: {exc}", exc_info=True)
                if self._stop_event.wait(timeout=0.5):
                    break

        self._monitors.pop(task["name"], None)

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

    def _call_func(
        self,
        func: Callable,
        context: Dict[str, Any],
        args: Tuple[Any, ...],
        kwargs: Optional[Dict[str, Any]],
    ):
        call_args, call_kwargs = self._prepare_invocation(func, context, args, kwargs)
        return func(*call_args, **call_kwargs)

    def _execute_task(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any],
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        execution_type: str = "recurring",
    ):
        current_thread = threading.current_thread()
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

        try:
            while retry_count <= self.max_retries:
                try:
                    self._call_func(func, actual_context, args, kwargs)

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
                        if self._stop_event.wait(self.retry_delay):
                            break
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
                with self._lock:
                    self.tasks = [task_data for task_data in self.tasks if task_data is not task]
        finally:
            self._workers.discard(current_thread)

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
            "cancel_event": threading.Event(),
        }

        with self._lock:
            self.tasks.append(task_data)
            self.task_registry[func.__name__] = task_info

        timer_thread = threading.Thread(
            target=self._execute_one_shot,
            args=(task_data,),
            name=f"OneShot-{func.__name__}",
            daemon=True,
        )
        task_data["timer_thread"] = timer_thread
        self._timers.add(timer_thread)
        timer_thread.start()
        self.logger.info(f"One-shot task '{func.__name__}' scheduled at {target_time}")
        return task_info

    def _execute_one_shot(self, task: Dict[str, Any]):
        current_thread = threading.current_thread()
        try:
            while True:
                if task["cancel_event"].is_set() or self._stop_event.is_set():
                    self.task_registry.pop(task["name"], None)
                    with self._lock:
                        self.tasks = [task_data for task_data in self.tasks if task_data is not task]
                    return

                remaining = (task["target_time"] - datetime.datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                task["cancel_event"].wait(timeout=min(remaining, 0.2))

            context = {
                "scheduled_at": task["target_time"],
                "task_name": task["name"],
            }
            self._execute_task(
                task,
                context,
                args=task.get("args", ()),
                kwargs=task.get("kwargs", {}),
                execution_type=task["execution_type"],
            )
        finally:
            self._timers.discard(current_thread)

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
