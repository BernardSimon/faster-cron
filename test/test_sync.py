import time
import threading
import pytest
from faster_cron.sync_cron import FastCron


def test_sync_overlap_prevention():
    """
    测试同步模式下的重叠控制：
    任务耗时 1.2 秒，触发间隔 1 秒，禁止重叠。
    """
    cron = FastCron()
    execution_counter = 0
    lock = threading.Lock()

    @cron.schedule("* * * * * *", allow_overlap=False)
    def slow_sync_task():
        nonlocal execution_counter
        with lock:
            execution_counter += 1
        time.sleep(1.2)

    # 在后台线程运行调度器
    cron_thread = threading.Thread(target=cron.run, daemon=True)
    cron_thread.start()

    # 观察 2.5 秒
    time.sleep(2.5)
    cron._running = False

    # 预期：第 1 秒启动，第 2 秒检测到线程 alive 于是跳过
    with lock:
        assert execution_counter < 3, "同步模式下禁止重叠失败，执行次数过多"


def test_sync_no_overlap_allowed():
    """
    测试同步模式下的并发：
    允许重叠时，即使任务慢，触发点到了也应该立即启动新线程。
    """
    cron = FastCron()
    execution_counter = 0
    lock = threading.Lock()

    @cron.schedule("* * * * * *", allow_overlap=True)
    def slow_concurrent_task():
        nonlocal execution_counter
        with lock:
            execution_counter += 1
        time.sleep(2)

    cron_thread = threading.Thread(target=cron.run, daemon=True)
    cron_thread.start()

    time.sleep(2.5)
    cron._running = False

    # 允许重叠，2.5秒内应该触发 2-3 次
    with lock:
        assert execution_counter >= 2