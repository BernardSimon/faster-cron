from __future__ import annotations

import json
from pathlib import Path

import pytest

from faster_cron import AsyncFasterCron, FasterCron


def test_sync_load_from_json_uses_real_repo_module(tmp_path: Path):
    config = {
        "tasks": [
            {
                "module": "faster_cron.example_tasks",
                "function": "heartbeat",
                "expression": "* * * * * *",
                "allow_overlap": True,
            },
            {
                "module": "faster_cron.example_tasks",
                "function": "health_check",
                "expression": "*/2 * * * * *",
                "allow_overlap": False,
            },
        ]
    }
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    cron = FasterCron(log_level=50)
    loaded = cron.load_from_json(str(path))

    assert loaded == 2
    assert {task.name for task in cron.list_tasks()} == {"heartbeat", "health_check"}


@pytest.mark.asyncio
async def test_async_load_from_json_skips_invalid_entries(tmp_path: Path):
    config = {
        "tasks": [
            {
                "module": "faster_cron.example_tasks",
                "function": "heartbeat",
                "expression": "* * * * * *",
            },
            {
                "module": "missing.module",
                "function": "nope",
                "expression": "* * * * * *",
            },
            {
                "module": "faster_cron.example_tasks",
                "function": "",
                "expression": "* * * * * *",
            },
        ]
    }
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    cron = AsyncFasterCron(log_level=50)
    loaded = cron.load_from_json(str(path))

    assert loaded == 1
    assert [task.name for task in cron.list_tasks()] == ["heartbeat"]


def test_load_from_yaml_handles_optional_dependency(tmp_path: Path):
    yaml_content = """
tasks:
  - module: faster_cron.example_tasks
    function: heartbeat
    expression: "* * * * * *"
"""
    path = tmp_path / "tasks.yaml"
    path.write_text(yaml_content, encoding="utf-8")

    cron = FasterCron(log_level=50)

    try:
        import yaml  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            cron.load_from_yaml(str(path))
    else:
        assert cron.load_from_yaml(str(path)) == 1
        assert cron.get_task("heartbeat") is not None


def test_invalid_tasks_structure_raises_value_error():
    cron = FasterCron(log_level=50)
    with pytest.raises(ValueError):
        cron._load_tasks({"tasks": {"not": "a list"}})
