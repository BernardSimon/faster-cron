#!/usr/bin/env python3
"""Async scheduler demo."""

import asyncio
import logging
from datetime import datetime, timedelta

from faster_cron import AsyncFasterCron


async def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    cron = AsyncFasterCron(log_level=logging.INFO, max_retries=1, retry_delay=0.2)

    @cron.schedule("*/2 * * * * *")
    async def recurring(context):
        print(f"[async recurring] {context['task_name']} at {context['scheduled_at'].strftime('%H:%M:%S')}")

    @cron.once_in(1)
    async def delayed(context):
        print(f"[async one-shot] {context['execution_type']} -> {context['task_name']}")

    @cron.run_at(datetime.now() + timedelta(seconds=2))
    async def scheduled(context):
        print(f"[async scheduled] target={context['scheduled_at'].strftime('%H:%M:%S')}")

    runner = asyncio.create_task(cron.start())
    await asyncio.sleep(1)

    async def added_later(ctx):
        print(f"[async added later] {ctx['task_name']}")

    cron.add_task("* * * * * *", added_later, allow_overlap=False)
    await asyncio.sleep(4)
    await cron.stop()
    await runner

    print(f"execution_history={len(cron.execution_history)} error_history={len(cron.error_history)}")


if __name__ == "__main__":
    asyncio.run(main())
