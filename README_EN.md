# FasterCron - Lightweight Python Task Scheduler 🐱

FasterCron is a lightweight but feature-complete Python scheduler with two mirrored engines:
- `AsyncFasterCron` (based on `asyncio`)
- `FasterCron` (based on `threading`)

It supports recurring cron tasks, one-shot tasks, retry handling, runtime task management, config loading, execution history, and error history.

---

<div align="center">

**Lightweight, Intuitive, and Powerful Task Scheduling for Python  
Dual mode: Asyncio and Threading**

[![PyPI version](https://img.shields.io/pypi/v/faster-cron.svg)](https://pypi.org/project/faster-cron/)
[![Python Versions](https://img.shields.io/pypi/pyversions/faster-cron.svg)](https://pypi.org/project/faster-cron/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passed-green.svg)](test/)

👉 **中文文档**: [README.md](./README.md) | 🚀 **Quick Start** below

</div>

---

## 🚀 Quick Start

### Installation

```bash
pip install faster-cron
```

Optional dependency (YAML config loading):

```bash
pip install pyyaml
```

Optional dependency (Web admin UI):

```bash
pip install "faster-cron[web]"
```

Development/test setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install pyyaml
```

### Basic usage

#### Async mode (recommended for async applications)

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()

@cron.schedule("*/5 * * * * *")
async def my_task(context):
    print(f"Scheduled at: {context['scheduled_at']}")

async def main():
    runner = asyncio.create_task(cron.start())
    await asyncio.sleep(10)
    await cron.stop()
    await runner

if __name__ == "__main__":
    asyncio.run(main())
```

#### Sync mode (for traditional scripts)

```python
import threading
import time
from faster_cron import FasterCron

cron = FasterCron()

@cron.schedule("* * * * * *")
def my_task(context):
    print(f"Scheduled at: {context['scheduled_at']}")

if __name__ == "__main__":
    t = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    t.start()
    time.sleep(5)
    cron.stop(wait_timeout=2)
    t.join(timeout=2)
```

---

## ✨ Core Features

### 1. Runtime task management

Manage tasks while the scheduler is running:
- `add_task()`
- `remove_task()`
- `pause_task()` / `resume_task()`
- `disable_task()` / `enable_task()`
- `list_tasks()` / `get_task()`
- `enable_web()` / `disable_web()` (also `enableWeb()` / `disableWeb()` aliases)

```python
cron = AsyncFasterCron()

@cron.schedule("*/5 * * * * *")
async def initial_task(ctx):
    pass

async def dynamic_task(ctx):
    pass

cron.add_task("*/10 * * * * *", dynamic_task, allow_overlap=False)
cron.update_task("dynamic_task", expression="*/15 * * * * *", kwargs={"env": "prod"})
print([task.name for task in cron.list_tasks()])
```

### 7. Optional web admin UI (FastAPI + Tailwind)

Enable `enable_web_ui=True` in constructor to launch a lightweight web page for task CRUD, pause/resume, parameter inspection/editing, and execution history.

```python
from faster_cron import FasterCron

cron = FasterCron(
    enable_web_ui=True,
    web_host="127.0.0.1",   # optional, default 127.0.0.1
    web_port=8000,           # optional, default 8000
)
```

After starting the scheduler, open: `http://127.0.0.1:8000`

### 2. Retry + error callback

Failed tasks can retry automatically with configurable limits and delay.

```python
def on_error_handler(error, record):
    print(f"Task {record.task_name} failed permanently: {error}")

cron = AsyncFasterCron(
    max_retries=3,
    retry_delay=1.0,
    on_error=on_error_handler,
)
```

### 3. One-shot tasks (delayed / scheduled)

- `once_in(seconds, ...)`
- `run_at(datetime, ...)`

Supports both decorator style and direct-call style, including explicit `args` / `kwargs`.

```python
from datetime import datetime, timedelta
from faster_cron import FasterCron

cron = FasterCron()

@cron.once_in(3)
def delayed_job(ctx):
    print(ctx["execution_type"])  # one_time_delayed

cron.run_at(
    datetime.now() + timedelta(seconds=5),
    print,
    args=("one-shot executed",),
)
```

One-shot context includes:
- `scheduled_at`
- `task_name`
- `execution_type` (`one_time_delayed` / `one_time_scheduled`)

After execution, one-shot tasks are removed from `task_registry` and internal task storage.

### 4. Signature-aware context injection

Context injection is based on callable signature:
- If `context` exists, it is injected as keyword arg
- If `**kwargs` exists, `context` is injected there
- If there is one plain positional parameter (for example `ctx`), context is passed positionally

```python
@cron.schedule("*/5 * * * * *")
def no_context():
    print("simple")

@cron.schedule("*/5 * * * * *")
def by_name(context):
    print(context["task_name"])

@cron.schedule("*/5 * * * * *")
def by_positional(ctx):
    print(ctx["scheduled_at"])
```

### 5. Overlap control

With `allow_overlap=False`, a new tick is skipped if previous execution is still running.

```python
@cron.schedule("* * * * * *", allow_overlap=False)
async def heavy_task(ctx):
    await asyncio.sleep(2)
```

### 6. Config loading

Load tasks from YAML/JSON files:
- `load_from_yaml(path)` (requires `pyyaml`)
- `load_from_json(path)`

Returns the number of successfully loaded tasks. Invalid entries/import failures are logged and skipped.

```yaml
tasks:
  - module: faster_cron.example_tasks
    function: heartbeat
    expression: "* * * * * *"
    allow_overlap: true
```

---

## 📖 API Reference

### Constructor options

Shared by `AsyncFasterCron` and `FasterCron`:
- `log_level`
- `log_format`
- `log_file`
- `custom_logger`
- `max_retries`
- `retry_delay`
- `on_error`
- `enable_web_ui`
- `web_host`
- `web_port`

`FasterCron` also supports:
- `wait_on_exit`

### Lifecycle

Async:
- `await start()`
- `await stop()`
- `await run()` (compatibility alias to `start()`)

Sync:
- `start(wait_on_exit=...)`
- `run(wait_on_exit=...)`
- `stop(wait_timeout=...)`

### Task registration

Decorator:

```python
@cron.schedule(expression, allow_overlap=True)
def or_async_task(...):
    ...
```

Programmatic:

```python
info = cron.add_task(
    expression="*/5 * * * * *",
    func=my_task,
    allow_overlap=False,
    args=(1, "x"),
    kwargs={"env": "dev"},
)

cron.update_task(
    task_name="my_task",
    expression="*/10 * * * * *",
    args=(2,),
    kwargs={"env": "prod"},
)
```

### Task information object `TaskInfo`

```python
@dataclass
class TaskInfo:
    name: str
    expression: str
    func: Callable
    allow_overlap: bool
    state: TaskState
    task_args: tuple = ()
    task_kwargs: Dict[str, Any] = field(default_factory=dict)
    func_module: Optional[str] = None
    func_qualname: Optional[str] = None
    retry_count: int = 0
    last_execution: Optional[datetime] = None
    last_result: Optional[str] = None
```

### Task states `TaskState`

- `PENDING`
- `RUNNING`
- `PAUSED`
- `DISABLED`
- `COMPLETED`

---

## 🔧 Cron Expressions

Supports both 5-field and 6-field formats:
- 5 fields: `minute hour day month weekday`
- 6 fields: `second minute hour day month weekday`

Supported operators:
- `*`
- `,`
- `-`
- `/`

Implementation details:
- Weekday `7` maps to `0` (Sunday)
- When day-of-month and weekday are both constrained, standard cron OR semantics are used

Common examples:
- `* * * * * *` — every second
- `*/5 * * * * *` — every 5 seconds
- `30 9 * * 1` — every Monday at 09:30
- `0 0 1 * 5` — first day of month OR Friday

---

## 🎬 Demos

```bash
python3 demo/v2_demo_async.py
python3 demo/v2_demo_sync.py
python3 demo/v2_demo_config.py
python3 demo/v2_demo_run.py
python3 demo/v2_demo_one_shot.py
python3 demo/v2_demo_management.py
python3 demo/v2_demo_web.py
python3 demo/v2_demo_web_async.py
```

`v2_demo_web.py` and `v2_demo_web_async.py` preload three task types:
- normal success task
- slow task (`allow_overlap=False`)
- intermittent failure task (to populate error history)

---

## 🧪 Tests

```bash
source .venv/bin/activate
pytest test/ -v
python test/quick_test.py
```

Current unit coverage includes:
- cron matching logic
- async/sync lifecycle
- dynamic task management
- pause/resume/disable/enable
- retry/error callback/history
- one-shot tasks and argument passing
- JSON/YAML config loading
- public API exports

---

## 📁 Project Layout

```text
faster_cron/
  __init__.py
  async_cron.py
  sync_cron.py
  web_admin.py
  base.py
  models.py
  example_tasks.py

demo/
  v2_demo_async.py
  v2_demo_sync.py
  v2_demo_config.py
  v2_demo_run.py
  v2_demo_one_shot.py
  v2_demo_management.py
  v2_demo_web.py
  v2_demo_web_async.py

test/
  test_cron_logic.py
  test_async_scheduler.py
  test_sync_scheduler.py
  test_one_shot.py
  test_retry_and_history.py
  test_config_loading.py
  test_public_api.py
  test_logging.py
```

---

## 🤝 Contributing

Issues and pull requests are welcome.

Suggested workflow:
1. create a feature branch
2. update code and tests
3. run `pytest test/ -v`
4. open a PR

---

## 📄 License

MIT License. See `LICENSE`.
