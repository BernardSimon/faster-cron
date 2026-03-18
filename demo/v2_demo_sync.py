#!/usr/bin/env python3
"""Sync scheduler demo."""

import logging
import threading
import time
from datetime import datetime, timedelta

from faster_cron import FasterCron


def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    cron = FasterCron(log_level=logging.INFO, max_retries=1, retry_delay=0.2)

    @cron.schedule("*/2 * * * * *")
    def recurring(context):
        print(f"[sync recurring] {context['task_name']} at {context['scheduled_at'].strftime('%H:%M:%S')}")

    @cron.once_in(1)
    def delayed(context):
        print(f"[sync one-shot] {context['execution_type']} -> {context['task_name']}")

    @cron.run_at(datetime.now() + timedelta(seconds=2))
    def scheduled(context):
        print(f"[sync scheduled] target={context['scheduled_at'].strftime('%H:%M:%S')}")

    runner = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    runner.start()
    time.sleep(1)

    def added_later(ctx):
        print(f"[sync added later] {ctx['task_name']}")

    cron.add_task("* * * * * *", added_later, allow_overlap=False)
    time.sleep(4)
    cron.stop(wait_timeout=2)
    runner.join(timeout=2)

    print(f"execution_history={len(cron.execution_history)} error_history={len(cron.error_history)}")


if __name__ == "__main__":
    main()
