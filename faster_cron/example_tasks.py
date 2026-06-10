"""Example task functions used by demos and config-loading tests."""

from __future__ import annotations

import asyncio
from typing import Dict, List

EXECUTION_LOG: List[str] = []


def _record(message: str):
    EXECUTION_LOG.append(message)
    print(message)


def clear_execution_log():
    EXECUTION_LOG.clear()


def heartbeat(context: Dict):
    _record(
        f"[heartbeat] {context['task_name']} at {context['scheduled_at'].isoformat()}"
    )


def health_check(context: Dict):
    _record(f"[health_check] checked at {context['scheduled_at'].isoformat()}")


def clean_temp_files(context: Dict):
    _record(f"[clean_temp_files] running via {context['task_name']}")


def nightly_backup(context: Dict):
    _record(f"[nightly_backup] scheduled at {context['scheduled_at'].isoformat()}")


async def async_ping(context: Dict):
    await asyncio.sleep(0)
    _record(
        f"[async_ping] {context['task_name']} at {context['scheduled_at'].isoformat()}"
    )
