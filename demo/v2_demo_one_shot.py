#!/usr/bin/env python3
"""One-shot task demo for sync and async schedulers."""

import asyncio
import time
from datetime import datetime, timedelta

from faster_cron import AsyncFasterCron, FasterCron


async def async_demo():
    cron = AsyncFasterCron(log_level=50)

    @cron.once_in(0.5)
    async def delayed(ctx):
        print(f"[async once_in] {ctx['execution_type']} {ctx['task_name']}")

    async def build_report(name, version=1):
        print(f"[async run_at] report={name} version={version}")

    cron.run_at(datetime.now() + timedelta(seconds=1), build_report, args=("daily",), kwargs={"version": 2})
    await asyncio.sleep(1.5)


def sync_demo():
    cron = FasterCron(log_level=50)

    @cron.once_in(0.5)
    def delayed(ctx):
        print(f"[sync once_in] {ctx['execution_type']} {ctx['task_name']}")

    def build_report(name, version=1):
        print(f"[sync run_at] report={name} version={version}")

    cron.run_at(datetime.now() + timedelta(seconds=1), build_report, args=("daily",), kwargs={"version": 2})
    time.sleep(1.5)


if __name__ == "__main__":
    sync_demo()
    asyncio.run(async_demo())

