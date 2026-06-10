from faster_cron import (
    AsyncFasterCron,
    ExecutionRecord,
    FasterCron,
    SchedulerStats,
    TaskInfo,
    TaskState,
)


def test_public_exports_are_available():
    assert AsyncFasterCron is not None
    assert FasterCron is not None
    assert TaskInfo is not None
    assert TaskState is not None
    assert ExecutionRecord is not None
    assert SchedulerStats is not None


def test_sync_and_async_expose_run_aliases():
    assert hasattr(FasterCron(), "run")
    assert hasattr(AsyncFasterCron(), "run")


def test_get_stats_is_available():
    assert hasattr(FasterCron(), "get_stats")
    assert hasattr(AsyncFasterCron(), "get_stats")
