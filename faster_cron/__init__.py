"""
FasterCron: 一个轻量、直观、支持异步与同步双模式的定时任务调度器。
v2.3.0 - Architecture Refactoring, Performance Improvements, SchedulerStats
"""

from .async_cron import AsyncFasterCron
from .models import ExecutionRecord, SchedulerStats, TaskInfo, TaskState
from .sync_cron import FasterCron

__version__ = "2.3.0"
__all__ = [
    "AsyncFasterCron",
    "FasterCron",
    "ExecutionRecord",
    "SchedulerStats",
    "TaskInfo",
    "TaskState",
]
