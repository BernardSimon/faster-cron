# FasterCron

English | [中文版](./README.md)

**FasterCron** is a lightweight, intuitive, and powerful Python task scheduling library. It provides seamless support for both **Asyncio** and **Threading** modes, designed specifically for scenarios requiring high reliability, minimal configuration, and fine-grained task concurrency control.

---

## 🌟 Key Features

* **Dual-Mode Support**: A unified logic offering both `AsyncFasterCron` (Asynchronous) and `FasterCron` (Synchronous/Threaded) implementations.
* **Task-Level Concurrency Control**: Precisely control whether a single task can overlap using the `allow_overlap` parameter (Singleton vs. Concurrent mode).
* **Smart Dependency Injection**: Automatically detects function signatures and injects a `context` argument (containing schedule time, task name, etc.) only when needed.
* **Standard Cron Support**: Compatible with both 5-digit (Min, Hour, Day, Month, Week) and 6-digit (Sec, Min, Hour, Day, Month, Week) Cron expressions.
* **Robustness**: Built-in exception handling ensures that a single task failure does not crash the entire scheduler.
* **Zero Dependencies**: Implemented using only the Python Standard Library—keep your project lean.

---

## 📦 Installation

You can install it directly via pip:

```bash
pip install faster-cron

```

Alternatively, just drop the source folder into your project directory.

---

## 🚀 Quick Start

### 1. Async Mode

Ideal for projects using `aiohttp`, `httpx`, `tortoise-orm`, or other asynchronous frameworks.

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()

# Example: Run every 5 seconds, disable overlap 
# (If the previous run isn't finished, the next cycle is skipped)
@cron.schedule("*/5 * * * * *", allow_overlap=False)
async def my_async_job(context):
    print(f"Task: {context['task_name']} | Scheduled at: {context['scheduled_at']}")
    await asyncio.sleep(6)  # Simulate a long-running task

async def main():
    await cron.start()

if __name__ == "__main__":
    asyncio.run(main())

```

### 2. Sync Mode (Threaded)

Perfect for traditional blocking scripts, web scrapers, or synchronous database operations.

```python
from faster_cron import FasterCron
import time

cron = FasterCron()

# Example: Run every second, allow concurrent execution
@cron.schedule("* * * * * *", allow_overlap=True)
def my_sync_job():
    print("Tick... Synchronous task is running.")
    time.sleep(2)

if __name__ == "__main__":
    cron.run()

```

---

## 🛠 Core API Reference

### The `schedule` Decorator

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `expression` | `str` | - | Cron expression. Supports `*`, `,`, `-`, `/`. |
| `allow_overlap` | `bool` | `True` | **Critical Parameter**. `True`: Execute whenever time matches; `False`: Skip execution if the previous instance of this task is still running. |

### The `context` Argument

If your task function accepts an argument named `context`, FasterCron will automatically inject a dictionary containing:

* `task_name`: The name of the decorated function.
* `scheduled_at`: The precise `datetime` object when the task was triggered.
* `expression`: The Cron expression used for this task.

---

## 📅 Cron Expression Examples

FasterCron supports flexible time definitions:

* `* * * * * *` : Every second.
* `*/5 * * * * *` : Every 5 seconds.
* `0 0 * * * *` : Every hour on the hour.
* `0 30 9-17 * * *` : Every half-hour between 9:00 AM and 5:00 PM.
* `0 0 0 * * 0` : Every Sunday at midnight.

---

## 🧪 Running Tests

This project comes with a comprehensive suite of unit tests. You can use `pytest` to verify the functionality:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

```

---

## 📄 License

MIT License.

If you find this project helpful, please give it a Star! 🌟