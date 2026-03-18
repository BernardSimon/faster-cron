#!/usr/bin/env python3
"""Config loading demo for FasterCron."""

import asyncio
from pathlib import Path

from faster_cron import AsyncFasterCron, FasterCron

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "examples" / "tasks.yaml"
JSON_PATH = ROOT / "examples" / "tasks.json"


def _print_loaded_tasks(mode: str, cron):
    print(f"[{mode}] loaded={len(cron.list_tasks())}")
    for task in cron.list_tasks():
        print(f"  - {task.name}: {task.expression} overlap={task.allow_overlap}")


def sync_demo() -> None:
    cron = FasterCron(log_level=50)
    if not YAML_PATH.exists():
        print(f"[sync] skipped: missing file {YAML_PATH}")
        return

    try:
        loaded = cron.load_from_yaml(str(YAML_PATH))
    except ImportError as exc:
        print(f"[sync] skipped: {exc}")
        return

    _print_loaded_tasks("sync", cron)


async def async_demo() -> None:
    cron = AsyncFasterCron(log_level=50)
    if not JSON_PATH.exists():
        print(f"[async] skipped: missing file {JSON_PATH}")
        return

    loaded = cron.load_from_json(str(JSON_PATH))
    _print_loaded_tasks("async", cron)


if __name__ == "__main__":

    sync_demo()
    asyncio.run(async_demo())
