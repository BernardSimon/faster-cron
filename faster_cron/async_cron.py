"""
AsyncFasterCron: 异步定时任务调度器
"""

import asyncio
import datetime
import importlib
import inspect
import logging
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .base import SchedulerMixin
from .models import ExecutionRecord, TaskInfo, TaskState


class AsyncFasterCron(SchedulerMixin):
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
        enable_web_ui: bool = False,
        web_host: str = "127.0.0.1",
        web_port: int = 8000,
    ):
        self._init_shared(
            log_level=log_level,
            log_format=log_format,
            log_file=log_file,
            custom_logger=custom_logger,
            max_retries=max_retries,
            retry_delay=retry_delay,
            on_error=on_error,
            enable_web_ui=enable_web_ui,
            web_host=web_host,
            web_port=web_port,
            logger_prefix="Async",
        )

        # 引擎特有字段
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._worker_tasks: Set[asyncio.Task] = set()
        self._one_shot_tasks: Set[asyncio.Task] = set()
        self._active_tasks: Set[asyncio.Task] = set()

    # ── 任务管理（async 特有实现） ─────────────────────────────

    def add_task(
        self,
        expression: str,
        func: Callable,
        allow_overlap: bool = True,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> TaskInfo:
        """动态添加周期性任务。"""
        normalized_args = tuple(args or ())
        normalized_kwargs = dict(kwargs or {})
        task_info = TaskInfo(
            name=func.__name__,
            expression=expression,
            func=func,
            allow_overlap=allow_overlap,
            state=TaskState.PENDING,
            task_args=normalized_args,
            task_kwargs=normalized_kwargs,
            func_module=getattr(func, "__module__", None),
            func_qualname=getattr(func, "__qualname__", func.__name__),
        )

        task_data = {
            "type": "recurring",
            "expression": expression,
            "func": func,
            "allow_overlap": allow_overlap,
            "name": func.__name__,
            "args": normalized_args,
            "kwargs": normalized_kwargs,
        }
        self.tasks.append(task_data)
        self.task_registry[func.__name__] = task_info

        if self._running:
            self._start_monitor(task_data)
            self.logger.info(f"Added task '{func.__name__}' while scheduler running")

        return task_info

    def update_task(
        self,
        task_name: str,
        *,
        expression: Optional[str] = None,
        allow_overlap: Optional[bool] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskInfo]:
        task_info = self.task_registry.get(task_name)
        if task_info is None:
            return None

        task_data = next(
            (
                task
                for task in self.tasks
                if task.get("name") == task_name and task.get("type") == "recurring"
            ),
            None,
        )
        if task_data is None:
            return None

        if expression is not None:
            task_data["expression"] = expression
            task_info.expression = expression
        if allow_overlap is not None:
            task_data["allow_overlap"] = allow_overlap
            task_info.allow_overlap = allow_overlap
        if args is not None:
            normalized_args = tuple(args)
            task_data["args"] = normalized_args
            task_info.task_args = normalized_args
        if kwargs is not None:
            normalized_kwargs = dict(kwargs)
            task_data["kwargs"] = normalized_kwargs
            task_info.task_kwargs = normalized_kwargs

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

    # ── 引擎生命周期 ─────────────────────────────────────────

    async def enable_web(
        self, host: Optional[str] = None, port: Optional[int] = None
    ) -> bool:
        """Enable web admin. Multiple calls won't start multiple servers."""
        if host is not None:
            self.web_host = host
        if port is not None:
            self.web_port = port

        already_running = self._web_admin_server is not None
        self.enable_web_ui = True
        if self._running and not already_running:
            await self._start_web_admin_server()
            return True
        return not already_running

    async def disable_web(self) -> bool:
        """Disable web admin and stop server if it is running."""
        was_running = self._web_admin_server is not None
        self.enable_web_ui = False
        if was_running:
            await self._stop_web_admin_server()
            return True
        return False

    async def enableWeb(
        self, base_url: Optional[str] = None, port: Optional[int] = None
    ) -> bool:
        return await self.enable_web(host=base_url, port=port)

    async def disableWeb(self) -> bool:
        return await self.disable_web()

    # ── 内部辅助 ──────────────────────────────────────────────

    def _refresh_active_tasks(self):
        self._worker_tasks = {task for task in self._worker_tasks if not task.done()}
        self._one_shot_tasks = {
            task for task in self._one_shot_tasks if not task.done()
        }
        self._monitor_tasks = {
            name: task for name, task in self._monitor_tasks.items() if not task.done()
        }
        self._active_tasks = (
            set(self._monitor_tasks.values())
            | self._worker_tasks
            | self._one_shot_tasks
        )

    def _start_monitor(self, task: Dict[str, Any]):
        if task.get("type") != "recurring":
            return

        existing = self._monitor_tasks.get(task["name"])
        if existing and not existing.done():
            return

        monitor = asyncio.create_task(
            self._monitor(task), name=f"monitor:{task['name']}"
        )
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
            self._execute_task(
                task, context, args=args, kwargs=kwargs, execution_type=execution_type
            ),
            name=f"worker:{task['name']}",
        )
        self._worker_tasks.add(worker)
        worker.add_done_callback(lambda _: self._refresh_active_tasks())
        self._refresh_active_tasks()
        return worker

    async def start(self):
        """启动调度器；有周期性任务时会持续运行直到 stop()。"""
        if self._running:
            return None

        self._running = True
        if self.enable_web_ui:
            await self._start_web_admin_server()
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
                if not self._active_tasks and not any(
                    t.get("type") == "recurring" for t in self.tasks
                ):
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
        await self._stop_web_admin_server()
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

                if (
                    not task["allow_overlap"]
                    and current_task
                    and not current_task.done()
                ):
                    self.logger.warning(f"Skip {task['name']}: overlapping blocked.")
                    continue

                context = {
                    "scheduled_at": next_trigger,
                    "task_name": task["name"],
                }
                current_task = self._create_worker(
                    task,
                    context,
                    args=task.get("args", ()),
                    kwargs=task.get("kwargs", {}),
                )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.error(
                    f"Error in monitor for {task['name']}: {exc}", exc_info=True
                )
                await asyncio.sleep(0.5)

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

        try:
            while retry_count <= self.max_retries:
                try:
                    await self._call_func(func, actual_context, args, kwargs)

                    execution_record.success = True
                    execution_record.finished_at = datetime.datetime.now()
                    assert execution_record.started_at is not None
                    execution_record.duration_seconds = (
                        execution_record.finished_at - execution_record.started_at
                    ).total_seconds()
                    self.execution_history.append(execution_record)

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
                        self.logger.error(
                            f"Max retries exceeded for task {func.__name__}"
                        )

            if not execution_record.success:
                execution_record.finished_at = datetime.datetime.now()
                assert execution_record.started_at is not None
                execution_record.duration_seconds = (
                    execution_record.finished_at - execution_record.started_at
                ).total_seconds()
                self.error_history.append(execution_record)

                if self.on_error and last_error is not None:
                    try:
                        self.on_error(last_error, execution_record)
                    except Exception as callback_exc:
                        self.logger.error(f"Error callback failed: {callback_exc}")

            if task_info is not None:
                task_info.state = (
                    TaskState.PENDING
                    if execution_type == "recurring"
                    else TaskState.COMPLETED
                )
                task_info.last_execution = execution_record.started_at
                task_info.last_result = (
                    "success"
                    if execution_record.success
                    else execution_record.error_message
                )

            if execution_type != "recurring":
                self.task_registry.pop(task_name, None)
                self.tasks = [
                    task_data for task_data in self.tasks if task_data is not task
                ]
        finally:
            self._refresh_active_tasks()

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
            task_args=tuple(args),
            task_kwargs=dict(kwargs),
            func_module=getattr(func, "__module__", None),
            func_qualname=getattr(func, "__qualname__", func.__name__),
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

        runtime_task = asyncio.create_task(
            self._execute_one_shot(task_data), name=f"one-shot:{func.__name__}"
        )
        task_data["runtime_task"] = runtime_task
        self._one_shot_tasks.add(runtime_task)
        runtime_task.add_done_callback(lambda _: self._refresh_active_tasks())
        self._refresh_active_tasks()
        self.logger.info(f"One-shot task '{func.__name__}' scheduled at {target_time}")
        return task_info

    async def _execute_one_shot(self, task: Dict[str, Any]):
        try:
            delay_seconds = max(
                0.0, (task["target_time"] - datetime.datetime.now()).total_seconds()
            )
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
            self.tasks = [
                task_data for task_data in self.tasks if task_data is not task
            ]
            raise

    async def _start_web_admin_server(self):
        if self._web_admin_server is not None:
            return

        web_admin_module = importlib.import_module("faster_cron.web_admin")
        WebAdminServer = web_admin_module.WebAdminServer

        self._web_admin_server = WebAdminServer(
            cron=self,
            host=self.web_host,
            port=self.web_port,
            logger=self.logger,
        )
        await self._web_admin_server.start_async()
        self.logger.info(f"Web admin started at http://{self.web_host}:{self.web_port}")

    async def _stop_web_admin_server(self):
        if self._web_admin_server is None:
            return
        await self._web_admin_server.stop_async()
        self._web_admin_server = None
