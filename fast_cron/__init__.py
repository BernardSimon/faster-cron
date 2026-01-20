"""
FastCron: 一个轻量、直观、支持异步与同步双模式的定时任务调度器。
"""

from .async_cron import AsyncFastCron
from .sync_cron import FastCron

__version__ = "0.1.0"
__all__ = ["AsyncFastCron", "FastCron"]