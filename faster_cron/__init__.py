"""
FasterCron: 一个轻量、直观、支持异步与同步双模式的定时任务调度器。
v2.2.0 - Optional Web Admin UI, i18n, Runtime Web Toggle, Paginated History
"""

from .async_cron import AsyncFasterCron
from .sync_cron import FasterCron
from .models import TaskInfo, TaskState, ExecutionRecord

__version__ = "2.2.0"
__all__ = [
    "AsyncFasterCron",
    "FasterCron",
    "TaskInfo",
    "TaskState",
    "ExecutionRecord"
]
