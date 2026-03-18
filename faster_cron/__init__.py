"""
FasterCron: 一个轻量、直观、支持异步与同步双模式的定时任务调度器。
v2.0 - High Precision Timing, Graceful Shutdown, Flexible Logging, One-Shot Tasks
"""

from .async_cron import AsyncFasterCron
from .sync_cron import FasterCron
from .one_shot import OneShotScheduler, AsyncOneShotScheduler, once_in, run_at

__version__ = "2.1.0"
__all__ = [
    "AsyncFasterCron",
    "FasterCron", 
    "OneShotScheduler",
    "AsyncOneShotScheduler",
    "once_in",
    "run_at"
]
