from __future__ import annotations

import logging
from pathlib import Path

from faster_cron import AsyncFasterCron, FasterCron



def test_sync_custom_logger_is_used():
    logger = logging.getLogger("faster_cron.test.sync")
    cron = FasterCron(custom_logger=logger)
    assert cron.logger is logger



def test_async_file_logger_creates_handler(tmp_path: Path):
    log_path = tmp_path / "async.log"
    cron = AsyncFasterCron(log_file=str(log_path))
    assert any(getattr(handler, "baseFilename", None) == str(log_path) for handler in cron.logger.handlers)

