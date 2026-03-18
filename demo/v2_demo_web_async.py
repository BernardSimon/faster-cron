#!/usr/bin/env python3
"""Async web admin demo (requires: pip install \"faster-cron[web]\")."""

import asyncio

from faster_cron import AsyncFasterCron


async def main():
    cron = AsyncFasterCron(enable_web_ui=True, web_host="127.0.0.1", web_port=8001)
    flaky_counter = {"count": 0}

    async def async_heartbeat(context, message, source="async-web-demo"):
        print(f"[{source}] {message} @ {context['scheduled_at']}")

    async def async_slow(ctx, wait_seconds=2):
        print(f"[async-slow] start wait={wait_seconds}s at {ctx['scheduled_at']}")
        await asyncio.sleep(wait_seconds)
        print(f"[async-slow] done at {ctx['scheduled_at']}")

    async def async_flaky(ctx):
        flaky_counter["count"] += 1
        # Fail every other run so history and error panels are both populated.
        if flaky_counter["count"] % 2 == 0:
            raise RuntimeError("async demo intermittent failure")
        print(f"[async-flaky] success run={flaky_counter['count']} at {ctx['scheduled_at']}")

    cron.add_task(
        "*/5 * * * * *",
        async_heartbeat,
        args=("hello from async task",),
        kwargs={"source": "async-web-demo"},
    )
    cron.add_task(
        "*/7 * * * * *",
        async_slow,
        allow_overlap=False,
        kwargs={"wait_seconds": 3},
    )
    cron.add_task("*/9 * * * * *", async_flaky)

    runner = asyncio.create_task(cron.run())

    print("Async web admin running at http://127.0.0.1:8001")
    print("Press Ctrl+C to stop")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await cron.stop()
        await runner


if __name__ == "__main__":
    asyncio.run(main())

