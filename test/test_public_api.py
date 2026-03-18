from faster_cron import AsyncFasterCron, ExecutionRecord, FasterCron, TaskInfo, TaskState



def test_public_exports_are_available():
    assert AsyncFasterCron is not None
    assert FasterCron is not None
    assert TaskInfo is not None
    assert TaskState is not None
    assert ExecutionRecord is not None



def test_sync_and_async_expose_run_aliases():
    assert hasattr(FasterCron(), "run")
    assert hasattr(AsyncFasterCron(), "run")

