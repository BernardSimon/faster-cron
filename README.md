# FasterCron - 轻量级 Python 定时任务调度器 🐱

FasterCron 是一个轻量但功能完整的 Python 定时任务调度库，提供双引擎：
- `AsyncFasterCron`（基于 `asyncio`）
- `FasterCron`（基于 `threading`）

支持周期任务、一次性任务、重试机制、动态任务管理、配置文件加载、执行历史与错误历史、运行时统计。

---

<div align="center">

**Lightweight, Intuitive, and Powerful Task Scheduling for Python  
支持 Asyncio（异步）和 Threading（同步）双模式**

[![PyPI version](https://img.shields.io/pypi/v/faster-cron.svg)](https://pypi.org/project/faster-cron/)
[![Python Versions](https://img.shields.io/pypi/pyversions/faster-cron.svg)](https://pypi.org/project/faster-cron/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passed-green.svg)](test/)

👉 **English**: [README_EN.md](./README_EN.md) | 🚀 **快速开始**：见下方

</div>

---

## 🚀 快速开始

### 安装

```bash
pip install faster-cron
```

可选依赖（YAML 配置加载）：

```bash
pip install "faster-cron[yaml]"
```

可选依赖（Web 管理后台）：

```bash
pip install "faster-cron[web]"
```

开发/测试环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 基础用法

#### 异步模式（推荐用于异步应用）

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()

@cron.schedule("*/5 * * * * *")
async def my_task(context):
    print(f"任务执行时间：{context['scheduled_at']}")

async def main():
    runner = asyncio.create_task(cron.start())
    await asyncio.sleep(10)
    await cron.stop()
    await runner

if __name__ == "__main__":
    asyncio.run(main())
```

#### 同步模式（适用于传统脚本）

```python
import threading
import time
from faster_cron import FasterCron

cron = FasterCron()

@cron.schedule("* * * * * *")
def my_task(context):
    print(f"同步任务时间：{context['scheduled_at']}")

if __name__ == "__main__":
    t = threading.Thread(target=cron.run, kwargs={"wait_on_exit": False}, daemon=True)
    t.start()
    time.sleep(5)
    cron.stop(wait_timeout=2)
    t.join(timeout=2)
```

---

## ✨ 核心功能

### 1. 动态任务管理

支持运行时任务增删改查：
- `add_task()`
- `remove_task()`
- `pause_task()` / `resume_task()`
- `disable_task()` / `enable_task()`
- `list_tasks()` / `get_task()`
- `enable_web()` / `disable_web()`（也支持 `enableWeb()` / `disableWeb()`）

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

### 2. 重试机制与错误回调

任务执行失败时自动重试，可配置最大重试次数、重试间隔、错误回调。

```python
def on_error_handler(error, record):
    print(f"任务 {record.task_name} 最终失败：{error}")

cron = AsyncFasterCron(
    max_retries=3,
    retry_delay=1.0,
    on_error=on_error_handler,
)
```

### 3. 一次性任务（延迟/定时）

- `once_in(seconds, ...)`
- `run_at(datetime, ...)`

支持装饰器写法和显式函数写法，且支持 `args` / `kwargs`。

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

一次性任务上下文包含：
- `scheduled_at`
- `task_name`
- `execution_type`（`one_time_delayed` / `one_time_scheduled`）

任务执行后会自动从 `task_registry` 与内部任务列表清理。

### 4. 智能上下文注入

上下文注入是签名感知的：
- 声明 `context` 参数：以关键字注入
- 声明 `**kwargs`：注入 `context`
- 单一普通位置参数（如 `ctx`）：以首个位置参数注入

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

### 5. 并发控制

`allow_overlap=False` 时，同一任务上一次未结束会跳过本次调度。

```python
@cron.schedule("* * * * * *", allow_overlap=False)
async def heavy_task(ctx):
    await asyncio.sleep(2)
```

### 6. 配置文件加载

支持从 YAML/JSON 批量加载任务：
- `load_from_yaml(path)`（需要 `pyyaml`）
- `load_from_json(path)`

返回值是成功加载任务数量，非法配置或导入失败会记录日志并跳过。

```yaml
tasks:
  - module: faster_cron.example_tasks
    function: heartbeat
    expression: "* * * * * *"
    allow_overlap: true
```

### 7. 运行时统计（v2.3.0 新增）

通过 `get_stats()` 获取调度器运行统计信息：

```python
stats = cron.get_stats()
print(stats.to_dict())
# {
#   "total_tasks": 3,
#   "active_tasks": 2,
#   "paused_tasks": 1,
#   "disabled_tasks": 0,
#   "total_executions": 150,
#   "successful_executions": 145,
#   "failed_executions": 5,
#   "error_history_size": 5,
#   "success_rate": 96.67
# }
```

Web 管理后台也提供 `/api/stats` 端点。

### 8. 可选 Web 管理后台（FastAPI + Tailwind）

实例化时开启 `enable_web_ui=True` 即可启用在线管理页面，支持任务增删改、暂停/恢复、参数查看和执行记录查看。

```python
from faster_cron import FasterCron

cron = FasterCron(
    enable_web_ui=True,
    web_host="127.0.0.1",   # 可选，默认 127.0.0.1
    web_port=8000,           # 可选，默认 8000
)
```

启动调度器后访问：`http://127.0.0.1:8000`

---

## 📖 API 参考

### 构造参数

`AsyncFasterCron` 与 `FasterCron` 共同支持：
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

`FasterCron` 额外支持：
- `wait_on_exit`

### 生命周期

异步：
- `await start()`
- `await stop()`
- `await run()`（`start()` 的兼容别名）

同步：
- `start(wait_on_exit=...)`
- `run(wait_on_exit=...)`
- `stop(wait_timeout=...)`

### 任务注册

装饰器：

```python
@cron.schedule(expression, allow_overlap=True)
def or_async_task(...):
    ...
```

编程式：

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

### 任务信息对象 `TaskInfo`

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

### 任务状态 `TaskState`

- `PENDING`
- `RUNNING`
- `PAUSED`
- `DISABLED`
- `COMPLETED`

---

## 🔧 Cron 表达式

支持 5 位和 6 位：
- 5 位：`分 时 日 月 周`
- 6 位：`秒 分 时 日 月 周`

支持语法：
- `*`
- `,`
- `-`
- `/`

实现细节：
- 周字段中 `7` 等价于 `0`（周日）
- 当"日"和"周"都被限制时，采用标准 Cron 的 OR 语义

常见示例：
- `* * * * * *`：每秒
- `*/5 * * * * *`：每 5 秒
- `30 9 * * 1`：每周一 09:30
- `0 0 1 * 5`：每月 1 号或每周五

---

## 🎬 Demo

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

`v2_demo_web.py` 与 `v2_demo_web_async.py` 会预置三类任务：
- 正常成功任务
- 慢任务（禁用重叠）
- 间歇失败任务（用于观察错误记录）

---

## 🧪 测试

```bash
source .venv/bin/activate
pytest test/ -v
python test/quick_test.py
```

当前单测覆盖（80+ 用例）：
- Cron 匹配逻辑与边界情况
- `_calculate_next_trigger` 字段约束算法
- `_expand_field` 字段展开
- 异步/同步生命周期
- 动态任务管理
- 暂停/恢复/禁用/启用
- 重试与错误回调
- 一次性任务与参数传递
- JSON/YAML 配置加载
- 公共 API 导出
- 并发安全
- `SchedulerStats` 统计
- Web 管理后台 CRUD

---

## 📁 项目结构

```text
faster_cron/
  __init__.py          # 公共 API 导出
  base.py              # CronBase（表达式解析）+ SchedulerMixin（共享逻辑）
  async_cron.py        # AsyncFasterCron 引擎
  sync_cron.py         # FasterCron 引擎
  models.py            # TaskInfo, TaskState, ExecutionRecord, SchedulerStats
  web_admin.py         # 可选 Web 管理后台
  example_tasks.py     # 示例任务
  py.typed             # PEP 561 类型标记

demo/                  # 演示脚本
test/                  # 测试套件（80+ 用例）
examples/              # 配置文件示例
```

---

## 🤝 贡献

欢迎提交 Issue / PR。

建议流程：
1. 新建分支
2. 修改代码并补充测试
3. 本地执行 `pytest test/ -v`
4. 提交 PR

---

## 📄 许可证

MIT License，详见 `LICENSE`。
