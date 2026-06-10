#!/usr/bin/env python3
"""Quick smoke test for FasterCron."""

import asyncio
import threading
import time

from faster_cron import AsyncFasterCron, FasterCron


async def async_smoke():
    cron = AsyncFasterCron(log_level=50)
    seen = []

    @cron.schedule("* * * * * *")
    async def tick(ctx):
        seen.append(ctx["task_name"])

    runner = asyncio.create_task(cron.run())
    await asyncio.sleep(1.2)
    await cron.stop()
    await runner
    assert seen, "async scheduler did not run"


def sync_smoke():
    cron = FasterCron(log_level=50)
    seen = []

    @cron.schedule("* * * * * *")
    def tick(ctx):
        seen.append(ctx["task_name"])

    thread = threading.Thread(
        target=cron.run, kwargs={"wait_on_exit": False}, daemon=True
    )
    thread.start()
    time.sleep(1.2)
    cron.stop(wait_timeout=2)
    thread.join(timeout=2)
    assert seen, "sync scheduler did not run"


if __name__ == "__main__":
    sync_smoke()
    asyncio.run(async_smoke())
    print("quick smoke test passed")
