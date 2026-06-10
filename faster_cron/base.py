"""
FasterCron v2.3.0 - 核心基础模块

提供 CronBase（Cron 表达式解析）和 SchedulerMixin（调度器共享逻辑）
"""

import datetime
import importlib
import inspect
import logging
from datetime import timedelta
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import ExecutionRecord, SchedulerStats, TaskInfo, TaskState


class CronBase:
    """提供符合标准 Cron 规范的解析逻辑"""

    @staticmethod
    def is_time_match(expression: str, now: datetime.datetime) -> bool:
        """
        判断当前时间是否匹配 Cron 表达式
        逻辑参考标准 Unix Cron：当日期和星期同时被指定时，采用 OR 关系。
        """
        parts = expression.split()
        if len(parts) == 5:
            # 分 时 日 月 周 -> 补齐秒为 0
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = "0", *parts
        elif len(parts) == 6:
            sec_part, min_part, hour_part, day_part, month_part, weekday_part = parts
        else:
            return False

        # 1. 转换星期逻辑 (Python 0=Mon, 6=Sun -> Cron 0或7=Sun, 1=Mon...)
        # 转换公式：(now.weekday() + 1) % 7 -> 结果 0=Sun, 1=Mon, ..., 6=Sat
        cron_weekday = (now.weekday() + 1) % 7

        try:
            # 2. 基础字段匹配
            sec_match = CronBase._match_field(sec_part, now.second)
            min_match = CronBase._match_field(min_part, now.minute)
            hour_match = CronBase._match_field(hour_part, now.hour)
            month_match = CronBase._match_field(month_part, now.month)

            day_matches = CronBase._match_field(day_part, now.day)
            weekday_matches = CronBase._match_field(weekday_part, cron_weekday)

            # 3. 处理 Day 和 Weekday 的特殊关系 (Standard Cron Logic)
            # 如果两个字段都有限制（不是 *），则为 OR 关系；否则为 AND 关系。
            day_is_star = (day_part == "*")
            weekday_is_star = (weekday_part == "*")

            if not day_is_star and not weekday_is_star:
                day_weekday_ok = (day_matches or weekday_matches)
            else:
                day_weekday_ok = (day_matches and weekday_matches)

            return (
                    sec_match and
                    min_match and
                    hour_match and
                    month_match and
                    day_weekday_ok
            )
        except Exception:
            # 如果表达式解析失败（如格式错误），返回 False 避免程序崩溃
            return False

    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        """解析单个 Cron 字段"""
        if pattern == "*":
            return True

        # 处理列表: "1,2,3"
        if "," in pattern:
            return any(CronBase._match_field(p, value) for p in pattern.split(","))

        # 处理步长: "*/5" 或 "1-10/2"
        if "/" in pattern:
            r, s = pattern.split("/")
            step = int(s)
            if r in ["*", ""]:
                return value % step == 0
            if "-" in r:
                start, end = map(int, r.split("-"))
                return start <= value <= end and (value - start) % step == 0
            # 固定点开始的步长: "5/10"
            return value >= int(r) and (value - int(r)) % step == 0

        # 处理范围: "10-20"
        if "-" in pattern:
            start, end = map(int, pattern.split("-"))
            return start <= value <= end

        # 处理精确数值: "5"
        try:
            target_val = int(pattern)
            # 兼容性处理：Cron 中 7 经常作为周日的另一种写法
            if target_val == 7:
                target_val = 0
            return target_val == value
        except ValueError:
            return False

    @staticmethod
    def _expand_field(pattern: str, min_val: int, max_val: int) -> List[int]:
        """将 Cron 字段展开为所有有效值的有序列表。无效模式返回空列表。"""
        if pattern == "*":
            return list(range(min_val, max_val + 1))

        result = set()

        try:
            for part in pattern.split(","):
                part = part.strip()
                if not part:
                    continue

                step = 1
                if "/" in part:
                    range_part, step_str = part.split("/", 1)
                    step = int(step_str)
                else:
                    range_part = part

                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start_str, end_str = range_part.split("-", 1)
                    start, end = int(start_str), int(end_str)
                else:
                    val = int(range_part)
                    # 兼容性处理：Cron 中 7 经常作为周日的另一种写法
                    if val == 7 and min_val == 0 and max_val <= 7:
                        val = 0
                    start = val
                    end = val

                if step > 0:
                    v = start
                    while v <= end:
                        if min_val <= v <= max_val:
                            result.add(v)
                        v += step
        except (ValueError, TypeError):
            return []

        return sorted(result)

    @staticmethod
    def calculate_next_trigger(
        expression: str,
        from_time: datetime.datetime,
    ) -> datetime.datetime:
        """使用字段约束跳跃算法查找下一个触发时间。"""
        parts = expression.split()
        if len(parts) == 5:
            # 5-field: min hour day month weekday (秒默认为 0)
            sec_field = "0"
            min_f = parts[0]
            hour_f = parts[1]
            day_f = parts[2]
            month_f = parts[3]
            weekday_f = parts[4]
        elif len(parts) == 6:
            sec_field, min_f, hour_f, day_f, month_f, weekday_f = parts
        else:
            raise ValueError(f"Invalid cron expression: {expression}")

        sec_values = CronBase._expand_field(sec_field, 0, 59)
        min_values = CronBase._expand_field(min_f, 0, 59)
        hour_values = CronBase._expand_field(hour_f, 0, 23)
        day_values = CronBase._expand_field(day_f, 1, 31)
        month_values = CronBase._expand_field(month_f, 1, 12)

        if not sec_values or not min_values or not hour_values or not day_values or not month_values:
            raise ValueError(f"Invalid cron expression: {expression}")

        day_is_star = (day_f == "*")
        weekday_is_star = (weekday_f == "*")

        import bisect

        candidate = from_time.replace(microsecond=0) + timedelta(seconds=1)
        max_iterations = 366 * 24 + 1  # hours in a year + margin

        for _ in range(max_iterations):
            # 月：跳到下一个有效月
            if candidate.month not in month_values:
                idx = bisect.bisect_left(month_values, candidate.month)
                if idx >= len(month_values):
                    # 跳到下一年
                    candidate = candidate.replace(
                        year=candidate.year + 1,
                        month=month_values[0],
                        day=1, hour=0, minute=0, second=0,
                    )
                    continue
                else:
                    candidate = candidate.replace(
                        month=month_values[idx],
                        day=1, hour=0, minute=0, second=0,
                    )
                    continue

            # 日：跳到下一个有效日
            cron_weekday = (candidate.weekday() + 1) % 7
            day_ok = candidate.day in day_values
            weekday_ok = CronBase._match_field(weekday_f, cron_weekday)

            if not day_is_star and not weekday_is_star:
                day_match = day_ok or weekday_ok
            else:
                day_match = day_ok and weekday_ok

            if not day_match:
                # 尝试下一天
                candidate = candidate.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                # 检查是否跨月
                if candidate.day == 1:
                    continue  # 重新从月开始检查
                continue

            # 时：跳到下一个有效小时
            if candidate.hour not in hour_values:
                idx = bisect.bisect_left(hour_values, candidate.hour)
                if idx >= len(hour_values):
                    candidate = candidate.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                    continue
                else:
                    candidate = candidate.replace(hour=hour_values[idx], minute=0, second=0)
                    continue

            # 分：跳到下一个有效分钟
            if candidate.minute not in min_values:
                idx = bisect.bisect_left(min_values, candidate.minute)
                if idx >= len(min_values):
                    candidate = candidate.replace(minute=0, second=0) + timedelta(hours=1)
                    continue
                else:
                    candidate = candidate.replace(minute=min_values[idx], second=0)
                    continue

            # 秒：跳到下一个有效秒
            if candidate.second not in sec_values:
                idx = bisect.bisect_left(sec_values, candidate.second)
                if idx >= len(sec_values):
                    candidate = candidate.replace(second=0) + timedelta(minutes=1)
                    continue
                else:
                    candidate = candidate.replace(second=sec_values[idx])
                    continue

            # 所有字段都匹配
            return candidate

        raise ValueError(f"No trigger time found within 1 year for expression: {expression}")


class SchedulerMixin:
    """
    调度器共享逻辑 Mixin

    包含 AsyncFasterCron 和 FasterCron 共有的所有方法。
    子类需实现：start(), stop(), add_task(), update_task(), remove_task(),
    _start_monitor(), _call_func(), _execute_task(), _schedule_one_shot(),
    _execute_one_shot(), enable_web(), disable_web()
    """

    # 子类必须定义的类型提示（供类型检查使用）
    tasks: List[Dict[str, Any]]
    task_registry: Dict[str, TaskInfo]
    paused_tasks: Set[str]
    max_retries: int
    retry_delay: float
    on_error: Optional[Callable[[Exception, ExecutionRecord], None]]
    execution_history: Any  # deque or list
    error_history: Any
    enable_web_ui: bool
    web_host: str
    web_port: int
    _running: bool
    _web_admin_server: Any
    logger: logging.Logger

    def _init_shared(
        self,
        log_level: int,
        log_format: str,
        log_file: Optional[str],
        custom_logger: Optional[logging.Logger],
        max_retries: int,
        retry_delay: float,
        on_error: Optional[Callable[[Exception, ExecutionRecord], None]],
        enable_web_ui: bool,
        web_host: str,
        web_port: int,
        logger_prefix: str,
    ):
        """初始化所有引擎共享的字段。"""
        self.tasks: List[Dict[str, Any]] = []
        self.task_registry: Dict[str, TaskInfo] = {}
        self.paused_tasks: Set[str] = set()

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error = on_error
        self.enable_web_ui = enable_web_ui
        self.web_host = web_host
        self.web_port = web_port

        self._running = False
        self._web_admin_server = None

        # 使用 deque 提升性能（Phase 3 优化在此生效）
        from collections import deque
        self.execution_history: Any = deque(maxlen=1000)
        self.error_history: Any = deque(maxlen=100)

        self._setup_logger(log_level, log_format, log_file, custom_logger, logger_prefix)

    def _setup_logger(
        self,
        log_level: int,
        log_format: str,
        log_file: Optional[str],
        custom_logger: Optional[logging.Logger],
        prefix: str,
    ):
        """配置日志记录器。"""
        if custom_logger is not None:
            self.logger = custom_logger
        else:
            instance_id = id(self)
            self.logger = logging.getLogger(f"FasterCron.{prefix}_{instance_id}")
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

    # ── 任务管理（纯逻辑，无并发依赖） ──────────────────────────

    def schedule(self, expression: str, allow_overlap: bool = True):
        """装饰器：注册周期性任务。"""

        def decorator(func: Callable):
            self.add_task(expression, func, allow_overlap=allow_overlap)
            return func

        return decorator

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

    # ── 一次性任务（纯逻辑） ──────────────────────────────────

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

    # ── 配置加载 ─────────────────────────────────────────────

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
            args = task_config.get("args", [])
            kwargs = task_config.get("kwargs", {})

            if not module_name or not function_name or not expression:
                self.logger.error(f"Invalid task config, missing required fields: {task_config}")
                continue

            try:
                module = importlib.import_module(module_name)
                func = getattr(module, function_name)
            except (ImportError, AttributeError) as exc:
                self.logger.error(f"Failed to import {module_name}.{function_name}: {exc}")
                continue

            self.add_task(
                expression,
                func,
                allow_overlap=allow_overlap,
                args=tuple(args or ()),
                kwargs=dict(kwargs or {}),
            )
            loaded_count += 1
            self.logger.info(f"Loaded task '{function_name}' from {module_name}")

        return loaded_count

    # ── 上下文注入 ────────────────────────────────────────────

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
            context_param = signature.parameters["context"]
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            if (
                context_param.kind
                in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and positional
                and positional[0].name == "context"
                and "context" not in call_kwargs
            ):
                args_list.insert(0, context)
            else:
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

    # ── 下次触发时间计算 ──────────────────────────────────────

    def _calculate_next_trigger(
        self,
        expression: str,
        from_time: Optional[datetime.datetime] = None,
    ) -> datetime.datetime:
        if from_time is None:
            from_time = datetime.datetime.now()

        return CronBase.calculate_next_trigger(expression, from_time)

    @staticmethod
    def _is_time_match(expression: str, now: datetime.datetime) -> bool:
        return CronBase.is_time_match(expression, now)

    # ── 统计信息 ──────────────────────────────────────────────

    def get_stats(self) -> SchedulerStats:
        """获取调度器运行统计信息。"""
        tasks = list(self.task_registry.values())
        return SchedulerStats(
            total_tasks=len(tasks),
            active_tasks=sum(
                1 for t in tasks if t.state in (TaskState.PENDING, TaskState.RUNNING)
            ),
            paused_tasks=sum(1 for t in tasks if t.state == TaskState.PAUSED),
            disabled_tasks=sum(1 for t in tasks if t.state == TaskState.DISABLED),
            total_executions=len(self.execution_history),
            successful_executions=sum(1 for r in self.execution_history if r.success),
            failed_executions=len(self.error_history),
            error_history_size=len(self.error_history),
        )

    # ── 子类必须实现的抽象方法 ────────────────────────────────
    # 以下方法由子类定义，此处仅作为类型提示

    def add_task(
        self,
        expression: str,
        func: Callable,
        allow_overlap: bool = True,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> TaskInfo:
        raise NotImplementedError

    def update_task(
        self,
        task_name: str,
        *,
        expression: Optional[str] = None,
        allow_overlap: Optional[bool] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskInfo]:
        raise NotImplementedError

    def remove_task(self, task_name: str) -> bool:
        raise NotImplementedError

    def _schedule_one_shot(
        self,
        target_time: datetime.datetime,
        func: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        execution_type: str,
    ) -> TaskInfo:
        raise NotImplementedError
