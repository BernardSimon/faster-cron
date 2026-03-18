from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from faster_cron import AsyncFasterCron, FasterCron


@pytest.fixture
def sync_cron() -> FasterCron:
    return FasterCron(log_level=logging.CRITICAL, retry_delay=0.01, wait_on_exit=True)


@pytest.fixture
def async_cron() -> AsyncFasterCron:
    return AsyncFasterCron(log_level=logging.CRITICAL, retry_delay=0.01)

