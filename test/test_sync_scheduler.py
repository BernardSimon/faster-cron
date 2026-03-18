from __future__ import annotations

import threading
import time
from datetime import datetime

from faster_cron.models import TaskState



def test_sync_public_lifecycle_and_dynamic_tasks(sync_cron):
    executions: list[str] = []

    @sync_cron.schedule("* * * * * *")
    def first_task(ctx):
        executions.append(ctx["task_name"])

    runner = threading.Thread(target=sync_cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    runner.start()

    time.sleep(1.2)

    def added_later(ctx):
        executions.append(ctx["task_name"])

    sync_cron.add_task("* * * * * *", added_later)
    time.sleep(1.2)
    sync_cron.stop(wait_timeout=1)
    runner.join(timeout=1)

    assert "first_task" in executions
    assert "added_later" in executions
    assert hasattr(sync_cron, "run")



def test_sync_pause_resume_disable_enable(sync_cron):
    counter = {"value": 0}

    @sync_cron.schedule("* * * * * *")
    def counted(ctx):
        counter["value"] += 1

    runner = threading.Thread(target=sync_cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    runner.start()

    time.sleep(1.2)
    before_pause = counter["value"]
    assert sync_cron.pause_task("counted") is True
    assert sync_cron.get_task("counted").state == TaskState.PAUSED

    time.sleep(1.2)
    after_pause = counter["value"]
    # A single in-flight execution may finish right after pause is requested.
    assert after_pause <= before_pause + 1

    assert sync_cron.resume_task("counted") is True
    time.sleep(1.2)
    after_resume = counter["value"]
    assert after_resume > after_pause

    assert sync_cron.disable_task("counted") is True
    assert sync_cron.get_task("counted").state == TaskState.DISABLED
    assert sync_cron.enable_task("counted") is True
    assert sync_cron.get_task("counted").state == TaskState.PENDING

    sync_cron.stop(wait_timeout=1)
    runner.join(timeout=1)



def test_sync_context_injection_supports_context_name_and_positional_ctx(sync_cron):
    received = {}

    def named_context(context):
        received["named"] = context

    def positional_ctx(ctx):
        received["positional"] = ctx

    named_task = sync_cron.add_task("* * * * * *", named_context)
    positional_task = sync_cron.add_task("* * * * * *", positional_ctx)

    context = {"scheduled_at": datetime.now(), "task_name": "manual"}
    sync_cron._execute_task(sync_cron.tasks[0], context)
    sync_cron._execute_task(sync_cron.tasks[1], context)

    assert received["named"]["task_name"] == "manual"
    assert received["positional"]["task_name"] == "manual"
    assert named_task.state == TaskState.PENDING
    assert positional_task.state == TaskState.PENDING



def test_sync_non_overlap_blocks_parallel_runs(sync_cron):
    starts: list[float] = []
    finished = threading.Event()

    @sync_cron.schedule("* * * * * *", allow_overlap=False)
    def slow_task(ctx):
        starts.append(time.time())
        time.sleep(1.3)
        finished.set()

    runner = threading.Thread(target=sync_cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    runner.start()

    time.sleep(2.4)
    sync_cron.stop(wait_timeout=2)
    runner.join(timeout=1)

    assert len(starts) <= 2
    assert finished.is_set()



def test_sync_remove_task(sync_cron):
    @sync_cron.schedule("* * * * * *")
    def task_to_remove(ctx):
        pass

    assert sync_cron.remove_task("task_to_remove") is True
    assert sync_cron.get_task("task_to_remove") is None
    assert sync_cron.remove_task("task_to_remove") is False

