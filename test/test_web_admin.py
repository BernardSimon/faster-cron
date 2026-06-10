from __future__ import annotations

import importlib
import logging
from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
TestClient = importlib.import_module("fastapi.testclient").TestClient

from faster_cron import AsyncFasterCron, FasterCron
from faster_cron.web_admin import create_web_app


def test_web_admin_crud_and_history_for_sync_scheduler():
    cron = FasterCron(log_level=logging.CRITICAL)

    def local_task(ctx):
        return None

    cron.add_task("*/5 * * * * *", local_task, args=(1,), kwargs={"env": "test"})

    app = create_web_app(cron)
    client = TestClient(app)

    listed = client.get("/api/tasks")
    assert listed.status_code == 200
    listed_payload = listed.json()["tasks"]
    assert any(task["name"] == "local_task" for task in listed_payload)

    created = client.post(
        "/api/tasks",
        json={
            "expression": "*/10 * * * * *",
            "module": "faster_cron.example_tasks",
            "function": "heartbeat",
            "allow_overlap": False,
            "args": ["hello"],
            "kwargs": {"tag": "demo"},
        },
    )
    assert created.status_code == 200
    assert created.json()["allow_overlap"] is False

    updated = client.put(
        "/api/tasks/heartbeat",
        json={
            "expression": "*/15 * * * * *",
            "allow_overlap": True,
            "args": ["updated"],
            "kwargs": {"tag": "changed"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["expression"] == "*/15 * * * * *"
    assert updated.json()["allow_overlap"] is True
    assert updated.json()["task_args"] == ["updated"]
    assert updated.json()["task_kwargs"] == {"tag": "changed"}

    invalid_update = client.put("/api/tasks/heartbeat", json={"args": {"bad": "shape"}})
    assert invalid_update.status_code == 422

    context = {"scheduled_at": datetime.now(), "task_name": "local_task"}
    cron._execute_task(cron.tasks[0], context)

    history = client.get("/api/history?limit=5")
    assert history.status_code == 200
    assert len(history.json()["records"]) >= 1

    deleted = client.delete("/api/tasks/heartbeat")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_web_admin_constructor_options_are_available():
    sync_cron = FasterCron(enable_web_ui=True, web_host="0.0.0.0", web_port=8010)
    async_cron = AsyncFasterCron(
        enable_web_ui=True, web_host="127.0.0.1", web_port=8011
    )

    assert sync_cron.enable_web_ui is True
    assert sync_cron.web_host == "0.0.0.0"
    assert sync_cron.web_port == 8010

    assert async_cron.enable_web_ui is True
    assert async_cron.web_host == "127.0.0.1"
    assert async_cron.web_port == 8011


def test_web_admin_index_contains_inline_editor_form():
    cron = FasterCron(log_level=logging.CRITICAL)
    app = create_web_app(cron)
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    html = index.text
    assert 'id="edit-task-name"' in html
    assert "submitTaskEdit()" in html


def test_sync_enable_disable_web_is_idempotent(monkeypatch):
    cron = FasterCron(log_level=logging.CRITICAL)
    starts = {"count": 0}
    stops = {"count": 0}

    def fake_start():
        starts["count"] += 1
        cron._web_admin_server = object()

    def fake_stop(wait_timeout=None):
        stops["count"] += 1
        cron._web_admin_server = None

    monkeypatch.setattr(cron, "_start_web_admin_server", fake_start)
    monkeypatch.setattr(cron, "_stop_web_admin_server", fake_stop)

    assert cron.enable_web(host="127.0.0.1", port=9001) is True
    assert cron.enable_web() is True
    assert cron.enableWeb(base_url="127.0.0.1", port=9002) is True
    assert cron.web_port == 9002
    assert starts["count"] == 0

    cron._running = True
    assert cron.enable_web() is True
    assert starts["count"] == 1
    assert cron.enable_web() is False
    assert starts["count"] == 1

    assert cron.disable_web() is True
    assert stops["count"] == 1
    assert cron.disable_web() is False
    assert cron.disableWeb() is False


@pytest.mark.asyncio
async def test_async_enable_disable_web_is_idempotent(monkeypatch):
    cron = AsyncFasterCron(log_level=logging.CRITICAL)
    starts = {"count": 0}
    stops = {"count": 0}

    async def fake_start():
        starts["count"] += 1
        cron._web_admin_server = object()

    async def fake_stop():
        stops["count"] += 1
        cron._web_admin_server = None

    monkeypatch.setattr(cron, "_start_web_admin_server", fake_start)
    monkeypatch.setattr(cron, "_stop_web_admin_server", fake_stop)

    assert await cron.enable_web(host="127.0.0.1", port=9011) is True
    assert await cron.enable_web() is True
    assert await cron.enableWeb(base_url="127.0.0.1", port=9012) is True
    assert cron.web_port == 9012
    assert starts["count"] == 0

    cron._running = True
    assert await cron.enable_web() is True
    assert starts["count"] == 1
    assert await cron.enable_web() is False
    assert starts["count"] == 1

    assert await cron.disable_web() is True
    assert stops["count"] == 1
    assert await cron.disable_web() is False
    assert await cron.disableWeb() is False
