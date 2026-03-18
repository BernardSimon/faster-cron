# FasterCron

[English](./README_EN.md) | **中文版**

**FasterCron** 是一个轻量级、直观且功能强大的 Python 定时任务调度工具库。它完美支持 **Asyncio (异步)** 和 **Threading (多线程)** 双模式，专为需要高可靠性、简单配置和任务并发控制的场景设计。

---

## 🌟 核心特性

* **双模式支持**：一套逻辑同时提供 `AsyncFasterCron`（异步）和 `FasterCron`（同步多线程）两种实现。
* **任务级并发控制**：通过 `allow_overlap` 参数精准控制同一个任务是否允许重叠执行（单例模式 vs 并发模式）。
* **智能参数注入**：自动检测任务函数签名，按需注入包含调度时间、任务名称的 `context` 上下文。
* **标准 Cron 支持**：兼容 5 位（分时日月周）和 6 位（秒分时日月周）Cron 表达式。
* **健壮性**：内置异常捕获机制，单个任务崩溃不影响调度器运行。
* **无外部依赖**：仅使用 Python 标准库实现，轻量无负担。

---

## 🆕 v2.0 新特性

> **版本：v2.0.0** | **发布日期：2026-03-18**

### ⚡ 高精度时间控制
- ✅ 动态计算下一个触发时刻，亚秒级精度
- ✅ 不再每秒检查一次，而是精确等待到触发点
- ✅ context 中的 `scheduled_at` 包含精确的目标触发时间

### 🛑 优雅状态管理
- ✅ 新增 `stop()` 方法，优雅关闭调度器
- ✅ 主动等待所有活跃任务完成后再退出
- ✅ 支持异步/同步模式的资源清理

### 🔄 资源管理改进
- ✅ 追踪所有活跃监控任务
- ✅ 同步模式使用非守护线程，确保程序退出前任务完成
- ✅ 避免 daemon 线程导致的中断风险

---

## 📦 安装

您可以直接通过 pip 安装：

```bash
pip install faster-cron

```

或者直接将源码放入您的项目中。

---

## 🚀 快速上手

### 1. 异步模式 (Async Mode)

适用于使用了 `aiohttp`, `httpx` 或 `tortoise-orm` 等异步库的项目。

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()


# 示例：每 5 秒执行一次，禁止重叠（若上一个任务没跑完，则跳过本次）
@cron.schedule("*/5 * * * * *", allow_overlap=False)
async def my_async_job(context):
    print(f"正在执行任务：{context['task_name']}, 计划时间：{context['scheduled_at']}")
    await asyncio.sleep(6)  # 模拟长耗时任务


async def main():
    await cron.start()


if __name__ == "__main__":
    asyncio.run(main())

```

#### 🆕 v2.0 推荐用法 - 优雅关闭

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()

@cron.schedule("* * * * * *")
async def periodic_task():
    ...

async def main():
    # 启动调度器
    await cron.start()
    
    # 运行一段时间后停止
    await asyncio.sleep(3600)
    
    # 优雅关闭，等待所有活跃任务完成
    await cron.stop()
```

或者使用上下文管理器：

```python
async with AsyncFasterCron() as cron:
    @cron.schedule("* * * * * *")
    async def task():
        ...
    # 自动管理生命周期
```

---

### 2. 同步模式 (Sync Mode)

适用于传统的阻塞式脚本或爬虫。

```python
from faster_cron import FasterCron
import time

cron = FasterCron()


# 示例：每秒执行一次，允许并发执行
@cron.schedule("* * * * * *", allow_overlap=True)
def my_sync_job():
    print("滴答，同步任务正在运行...")
    time.sleep(2)


if __name__ == "__main__":
    cron.run()

```

#### 🆕 v2.0 推荐用法 - 优雅退出

```python
from faster_cron import FasterCron
import signal
import sys

cron = FasterCron()

@cron.schedule("* * * * * *")
def my_task():
    ...

def handle_signal(signum, frame):
    print("\n接收到退出信号，正在优雅关闭...")
    cron.stop()  # 等待所有任务完成后再退出
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

try:
    cron.run(wait_on_exit=True)  # 等待任务完成
except KeyboardInterrupt:
    handle_signal(None, None)
```

---

## 🛠 核心 API 说明

### 调度装饰器 `schedule`

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `expression` | `str` | - | Cron 表达式。支持 `*`, `,`, `-`, `/`。 |
| `allow_overlap` | `bool` | `True` | **关键参数**。`True`: 时间点到达即执行；`False`: 若该任务的上一个实例未结束，则跳过本次执行循环。 |

### 上下文参数 `context`

如果您的任务函数接收名为 `context` 的参数，FasterCron 会自动注入以下字典：

* `task_name`: 任务函数名称。
* `scheduled_at`: 任务触发的**精确** `datetime` 对象（v2.0 新增）。

---

## 🆕 v2.0 新增 API

### 异步模式 `AsyncFasterCron`

```python
async def stop(self, wait_timeout: float = 30.0) -> None:
    """
    优雅关闭调度器
    
    Args:
        wait_timeout: 等待活跃任务完成的超时时间（秒）
    """
    await cron.stop()  # 等待最多 30 秒
```

### 同步模式 `FasterCron`

```python
def run(self, wait_on_exit: bool = True) -> None:
    """
    启动调度器并阻塞
    
    Args:
        wait_on_exit: 程序退出时是否等待所有任务完成（默认 True）
    """
    cron.run(wait_on_exit=True)  # 等待线程完成再退出

def stop(self, wait_timeout: float = 30.0) -> None:
    """
    优雅关闭调度器
    
    Args:
        wait_timeout: 等待所有监控线程完成的超时时间（秒）
    """
    cron.stop()  # 等待所有线程结束
```

---

## 📅 Cron 表达式参考

FasterCron 支持灵活的表达式定义：

* `* * * * * *` : 每秒执行。
* `*/5 * * * * *` : 每 5 秒执行。
* `0 0 * * * *` : 每整小时执行。
* `0 30 9-17 * * *` : 每天 9:00 到 17:00 之间的每半小时执行。
* `0 0 0 * * 0` : 每周日凌晨执行。

---

## 🧪 运行测试

本项目包含完善的单元测试。您可以使用 `pytest` 来验证功能：

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
pytest

# 运行特定测试文件
pytest test/test_v2_improvements.py -v
```

---

## 📄 开源协议

MIT License.

---

**如果您觉得好用，欢迎点一个 Star！🌟**

---

## 🔄 升级指南

### v1.x → v2.0 主要变化

| 变更项 | v1.x | v2.0 | 影响 |
|--------|------|------|------|
| 时间精度 | 每秒检查 | 精确等待触发点 | ⭐ 性能提升 |
| 停止方式 | 设置 `_running=False` | 调用 `stop()` 方法 | 🔒 更可靠 |
| 线程类型 | daemon=True | daemon=False | 🔒 更稳定 |
| 活跃任务追踪 | 无 | `set[Task]` | 🔍 可调试 |

**兼容性提示**: v2.0 保留了 `start()`/`run()` 方法，但仍推荐使用 `stop()` 进行优雅关闭。
