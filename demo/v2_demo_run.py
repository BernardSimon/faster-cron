#!/usr/bin/env python3
"""Lifecycle and run-alias demo."""

import asyncio
import threading
import time

from faster_cron import AsyncFasterCron, FasterCron


async def async_demo():
    cron = AsyncFasterCron(log_level=50)

    @cron.schedule("* * * * * *")
    async def async_tick(ctx):
        print(f"[async.run] {ctx['task_name']}")

    runner = asyncio.create_task(cron.run())
    await asyncio.sleep(2)
    await cron.stop()
    await runner


def sync_demo():
    cron = FasterCron(log_level=50)

    @cron.schedule("* * * * * *")
    def sync_tick(ctx):
        print(f"[sync.run] {ctx['task_name']}")

    thread = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    thread.start()
    time.sleep(2)
    cron.stop(wait_timeout=2)
    thread.join(timeout=2)


if __name__ == "__main__":
    sync_demo()
    asyncio.run(async_demo())
