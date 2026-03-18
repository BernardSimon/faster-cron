"""
FasterCron: 一个轻量、直观、支持异步与同步双模式的定时任务调度器。
v2.0 - High Precision Timing, Graceful Shutdown, Flexible Logging
"""

from .async_cron import AsyncFasterCron
from .sync_cron import FasterCron

__version__ = "2.0.0"
__all__ = ["AsyncFasterCron", "FasterCron"]
