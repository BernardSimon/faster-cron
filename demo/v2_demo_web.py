#!/usr/bin/env python3
"""Web admin demo (requires: pip install \"faster-cron[web]\")."""

import threading
import time

from faster_cron import FasterCron


if __name__ == "__main__":
    cron = FasterCron(enable_web_ui=True, web_host="127.0.0.1", web_port=8000)
    flaky_counter = {"count": 0}

    def heartbeat(context, message, source="unknown"):
        print(f"[{source}] {message} @ {context['scheduled_at']}")

    def slow_report(ctx, wait_seconds=2):
        print(f"[slow] start wait={wait_seconds}s at {ctx['scheduled_at']}")
        time.sleep(wait_seconds)
        print(f"[slow] done at {ctx['scheduled_at']}")

    def flaky_task(ctx):
        flaky_counter["count"] += 1
        # Fail every other run so history and error panels are both populated.
        if flaky_counter["count"] % 2 == 0:
            raise RuntimeError("demo intermittent failure")
        print(f"[flaky] success run={flaky_counter['count']} at {ctx['scheduled_at']}")

    def always_error(ctx):
        raise RuntimeError("demo always-fail task")

    cron.add_task("*/5 * * * * *", heartbeat, args=("demo",), kwargs={"source": "web-demo"})
    cron.add_task("*/7 * * * * *", slow_report, allow_overlap=False, kwargs={"wait_seconds": 3})
    cron.add_task("*/9 * * * * *", flaky_task)
    cron.add_task("*/11 * * * * *", always_error)

    runner = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    runner.start()

    print("Web admin running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cron.stop(wait_timeout=2)
        runner.join(timeout=2)


