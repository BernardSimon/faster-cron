#!/usr/bin/env python3
"""Task management demo."""

import threading
import time

from faster_cron import FasterCron


if __name__ == "__main__":
    cron = FasterCron(log_level=50)
    counter = {"value": 0}

    @cron.schedule("* * * * * *")
    def managed(ctx):
        counter["value"] += 1
        print(f"[managed] count={counter['value']} state={cron.get_task('managed').state}")

    thread = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    thread.start()

    time.sleep(1.2)
    cron.pause_task("managed")
    print("paused")
    time.sleep(1.2)
    cron.resume_task("managed")
    print("resumed")
    time.sleep(1.2)
    cron.disable_task("managed")
    print("disabled")
    time.sleep(1.2)
    cron.enable_task("managed")
    print("enabled")
    time.sleep(1.2)

    cron.stop(wait_timeout=2)
    thread.join(timeout=2)

