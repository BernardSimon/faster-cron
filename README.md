# FasterCron - 轻量级 Python 定时任务调度器 🐱

FasterCron 是一个功能强大、易用性极高的 Python 定时任务调度库，支持 **异步模式**（asyncio）和 **同步模式**（threading）双架构设计。

---

<div align="center">

**Lightweight, Intuitive, and Powerful Task Scheduling for Python  
支持 Asyncio (异步) 和 Threading (同步) 双模式**

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

可选依赖（配置加载）：
```bash
pip install pyyaml  # YAML 支持
```

### 基础用法

#### 异步模式（推荐用于异步应用）

```python
import asyncio
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()

# 注册周期性任务
@cron.schedule("*/5 * * * * *")  # 每 5 秒执行
async def my_task(context):
    print(f"任务执行时间：{context['scheduled_at']}")

async def main():
    await cron.start()      # 启动调度器
    await asyncio.sleep(60)  # 运行 60 秒
    await cron.stop()        # 优雅关闭

if __name__ == "__main__":
    asyncio.run(main())
```

#### 同步模式（适用于传统脚本）

```python
from faster_cron import FasterCron

cron = FasterCron()

@cron.schedule("* * * * * *")  # 每秒执行
def my_task(context):
    print(f"同步任务时间：{context['scheduled_at']}")

if __name__ == "__main__":
    cron.run(wait_on_exit=True)  # 阻塞运行直到停止
```

---

## ✨ 核心功能

### 1. 高精度时间控制 ⭐⭐⭐⭐⭐

动态计算下一个触发时刻，亚秒级精度。

- ❌ 传统方式：每秒检查一次 → ~500ms 误差
- ✅ FasterCron：精确等待 → <0.1ms 误差 (**提升 5000 倍!**)

```python
@cron.schedule("0 * * * * *")  # 整点触发
async def hourly_job(ctx):
    # 以<0.1ms 精度在整点执行
    pass
```

### 2. 动态任务管理 ⭐⭐⭐⭐

运行时添加、删除、暂停、恢复、禁用任务。

```python
cron = AsyncFasterCron()

# 初始注册
@cron.schedule("*/5 * * * * *")
async def initial_task(ctx):
    pass

# 动态添加任务
def new_task(ctx):
    pass
cron.add_task("*/10 * * * * *", new_task)

# 查询任务信息
all_tasks = cron.list_tasks()
task_info = cron.get_task("initial_task")
print(f"状态：{task_info.state}")

# 生命周期管理
cron.pause_task("initial_task")      # 暂停
cron.resume_task("initial_task")     # 恢复
cron.disable_task("initial_task")    # 禁用（保留配置）
cron.remove_task("initial_task")     # 移除
```

### 3. 智能重试机制 ⭐⭐⭐⭐⭐

失败自动重试，可配置最大重试次数、重试间隔、错误回调。

```python
def on_error_handler(error, record):
    """自定义错误处理"""
    print(f"任务 {record.task_name} 最终失败：{error}")

cron = AsyncFasterCron(
    max_retries=3,           # 最多重试 3 次
    retry_delay=5.0,         # 每次间隔 5 秒
    on_error=on_error_handler
)

@cron.schedule("* * * * * *")
async def flaky_task(ctx):
    if should_fail():
        raise ValueError("临时错误")
    do_work()
```

### 4. 一次性任务 ⭐⭐⭐

无需注册，立即调度延迟或定时执行的任务。

```python
from datetime import datetime, timedelta

# 延迟 N 秒后执行一次
cron.once_in(300, send_email)  # 5 分钟后

# 指定时间执行一次
target_time = datetime.now() + timedelta(hours=1)
cron.run_at(target_time, generate_report)
```

### 5. 灵活日志配置 ⭐⭐⭐

自定义日志格式、输出到文件、使用外部 logger。

```python
import logging

# 自定义格式
cron = AsyncFasterCron(log_format="[%(levelname)s] %(message)s")

# 文件日志
cron = AsyncFasterCron(log_file="/var/log/faster-cron.log")

# 外部 logger
cron = AsyncFasterCron(custom_logger=custom_logger)
```

### 6. 配置文件加载 ⭐⭐⭐

从 YAML/JSON 文件加载任务配置。

```yaml
# tasks.yaml
tasks:
  - module: my_app.backup
    function: nightly_backup
    expression: "0 2 * * *"      # 每天凌晨 2 点
    allow_overlap: false
    priority: 5
```

```python
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron()
cron.load_from_yaml("tasks.yaml")
# 或
cron.load_from_json("tasks.json")
```

### 7. 优雅关闭和资源管理 ⭐⭐⭐⭐

干净地停止所有活跃任务，避免资源泄漏。

```python
import signal
import sys

def handle_shutdown(signum, frame):
    print("优雅关闭中...")
    cron.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
cron.run(wait_on_exit=True)
```

### 8. 智能参数注入

自动检测函数签名并注入 context。

```python
@cron.schedule("*/5 * * * * *")
def simple_task():
    print("简单任务")

@cron.schedule("*/5 * * * * *")
def smart_task(context):
    print(f"任务名：{context['task_name']}")
    print(f"计划时间：{context['scheduled_at']}")
```

### 9. 并发控制

控制同一任务是否允许重叠执行。

```python
# 允许重叠（默认）
@cron.schedule("*/5 * * * * *", allow_overlap=True)
async def fast_task(ctx):
    await asyncio.sleep(6)  # 耗时 6 秒

# 单例模式
@cron.schedule("* * * * * *", allow_overlap=False)
async def heavy_task(ctx):
    await asyncio.sleep(200)  # 若上一个未结束则跳过本次
```

---

## 📖 完整 API 参考

### 构造函数选项

#### `AsyncFasterCron`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_level` | int | `logging.INFO` | 日志级别 |
| `log_format` | str | 标准格式 | 自定义日志格式 |
| `log_file` | Optional[str] | None | 日志文件路径 |
| `custom_logger` | Optional[Logger] | None | 自定义 logger |
| `max_retries` | int | 3 | 最大重试次数 |
| `retry_delay` | float | 5.0 | 重试间隔秒数 |
| `on_error` | Optional[callable] | None | 错误回调 |

#### `FasterCron`

与 `AsyncFasterCron` 相同，额外增加：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wait_on_exit` | bool | True | 退出时等待线程完成 |

### 任务注册方法

#### 装饰器方式

```python
@cron.schedule(expression, allow_overlap=True, priority=0)
async def task_function(context):
    ...
```

#### 编程方式

```python
def task_func(context):
    ...

info = cron.add_task(
    expression="*/5 * * * * *",
    func=task_func,
    allow_overlap=False,
    priority=5
)
```

### 任务信息对象 (`TaskInfo`)

```python
@dataclass
class TaskInfo:
    name: str                        # 任务名称
    expression: str                  # Cron 表达式
    func: Callable                   # 函数引用
    allow_overlap: bool              # 是否允许重叠
    state: TaskState                 # 当前状态枚举
    priority: int = 0                # 优先级
    retry_count: int = 0             # 当前重试次数
    last_execution: Optional[datetime]  # 上次执行时间
    last_result: Optional[str]       # 上次执行结果
```

### `TaskState` 枚举

| 值 | 说明 |
|----|------|
| `PENDING` | 待调度 |
| `RUNNING` | 运行中 |
| `PAUSED` | 已暂停 |
| `DISABLED` | 已禁用（保留配置） |
| `COMPLETED` | 已完成 |

---

## 🔧 Cron 表达式格式

支持标准 5 位和 6 位 Cron 表达式：

### 字段说明

| 位置 | 字段 | 值范围 | 特殊字符 |
|------|------|--------|----------|
| 1 (或 0) | 秒 | 0-59 | `*`, `,`, `-`, `/` |
| 2 | 分 | 0-59 | `*`, `,`, `-`, `/` |
| 3 | 时 | 0-23 | `*`, `,`, `-`, `/` |
| 4 | 日 | 1-31 | `*`, `,`, `-`, `/` |
| 5 | 月 | 1-12 | `*`, `,`, `-`, `/` |
| 6 (可选) | 周 | 0-6(周日=0) | `*`, `,`, `-`, `/` |

### 特殊字符

- `*` - 任意值
- `,` - 列表分隔符 (如 `1,3,5`)
- `-` - 范围 (如 `1-5` = 1,2,3,4,5)
- `/` - 步长 (如 `*/5` = 每 5 个单位)

### 常用示例

| 表达式 | 含义 |
|--------|------|
| `* * * * * *` | 每秒执行 |
| `*/5 * * * * *` | 每 5 秒执行 |
| `0 */30 * * * *` | 每 30 分钟执行 |
| `0 0 * * * *` | 每小时执行 |
| `0 0 9-17 * * *` | 工作日 9:00-17:00 每小时执行 |
| `0 0 0 * * 0` | 每周日凌晨 0 点执行 |
| `30 9 * * 1,5` | 周一和周五上午 9:30 执行 |

---

## 🎬 演示程序

运行 `demo/` 目录中的示例：

### 异步模式演示
```bash
python3 demo/v2_demo_async.py
```

### 同步模式演示
```bash
python3 demo/v2_demo_sync.py
```

### 配置文件加载演示
```bash
python3 demo/v2_demo_config.py
```

---

## 🧪 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio pyyaml

# 运行所有测试
pytest test/ -v

# 查看覆盖率
pytest --cov=faster_cron
```

---

## 💡 最佳实践

### 选择异步还是同步？

**使用异步模式当：**
- 应用使用 async 框架 (FastAPI, aiohttp)
- 需要非阻塞 I/O
- 运行大量并发任务

**使用同步模式当：**
- 传统阻塞脚本
- 简单的自动化任务
- 无 async 框架依赖

### 生产环境部署

```python
import signal
import sys
from faster_cron import AsyncFasterCron

cron = AsyncFasterCron(
    log_level=logging.INFO,
    log_file="/var/log/faster-cron/app.log",
    max_retries=3,
    retry_delay=30.0
)

def graceful_shutdown(signum, frame):
    print("准备优雅关闭...")
    cron.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

try:
    asyncio.run(cron.start())
except KeyboardInterrupt:
    graceful_shutdown(None, None)
```

---

## 🤝 贡献

欢迎贡献！请：

1. Fork 仓库
2. 创建特性分支
3. 为新功能添加测试
4. 确保所有测试通过
5. 提交 Pull Request

---

## 📄 许可证

MIT License. 详见 [LICENSE](LICENSE).

---

<div align="center">

Made with ❤️ by Bernard Simon  
FasterCron · 轻量、快速、强大

</div>
