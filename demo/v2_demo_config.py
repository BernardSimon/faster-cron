#!/usr/bin/env python3
"""
FasterCron v2.0 - 配置文件加载演示

演示内容:
1. 从 YAML 文件加载任务配置
2. 从 JSON 文件加载任务配置
3. 动态模块导入
4. 优先级配置

运行方式:
    python demo/v2_demo_config.py
"""

import asyncio
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

from faster_cron import AsyncFasterCron


# ========== 模拟任务模块 ==========#

class MyApp:
    """模拟应用模块"""
    
    @staticmethod
    def backup_task(ctx):
        """备份任务"""
        now = datetime.now()
        print(f"💾 [备份任务] 执行时间：{now.strftime('%H:%M:%S')}")
        print(f"    → 执行类型：{ctx.get('execution_type', 'periodic')}")
    
    @staticmethod
    def report_task(ctx):
        """报表任务"""
        now = datetime.now()
        print(f"📊 [报表任务] 生成报表，时间：{now.strftime('%H:%M:%S')}")
    
    @staticmethod
    def cleanup_task(ctx):
        """清理任务"""
        now = datetime.now()
        print(f"🧹 [清理任务] 清理临时文件，时间：{now.strftime('%H:%M:%S')}")


# ========== 示例配置 ==========

YAML_CONFIG = """
tasks:
  - module: demo.v2_demo_config.MyApp
    function: backup_task
    expression: "*/3 * * * * *"
    allow_overlap: false
    priority: 5

  - module: demo.v2_demo_config.MyApp
    function: report_task
    expression: "*/5 * * * * *"
    allow_overlap: true
    priority: 3

  - module: demo.v2_demo_config.MyApp
    function: cleanup_task
    expression: "0 */2 * * * *"
    allow_overlap: false
    priority: 1
"""

JSON_CONFIG = """
{
  "tasks": [
    {
      "module": "demo.v2_demo_config.MyApp",
      "function": "backup_task",
      "expression": "*/4 * * * * *",
      "allow_overlap": false,
      "priority": 4
    },
    {
      "module": "demo.v2_demo_config.MyApp",
      "function": "report_task",
      "expression": "*/6 * * * * *",
      "allow_overlap": true,
      "priority": 2
    }
  ]
}
"""


def main():
    print("="*70)
    print("FasterCron v2.0 - 配置文件加载演示")
    print("="*70)
    
    # ========== 从 YAML 加载配置 ==========
    print("\n📄 [步骤 1] 从 YAML 配置文件加载任务...")
    
    yaml_file = "/tmp/tasks.yaml"
    
    # 创建配置文件
    with open(yaml_file, 'w', encoding='utf-8') as f:
        f.write(YAML_CONFIG)
    
    print(f"  → 配置文件：{yaml_file}")
    print("  → 包含以下任务:")
    print("     • backup_task: 每 3 秒，优先级 5")
    print("     • report_task: 每 5 秒，优先级 3")
    print("     • cleanup_task: 每 2 分钟，优先级 1")
    
    # 创建调度器并加载配置
    cron = AsyncFasterCron(log_level=logging.INFO)
    loaded_count = cron.load_from_yaml(yaml_file)
    print(f"\n✅ 成功加载 {loaded_count} 个任务！")
    
    # 显示加载的任务信息
    print("\n当前任务列表:")
    for task in sorted(cron.list_tasks(), key=lambda t: t.priority, reverse=True):
        print(f"  • [{task.priority}] {task.name}: {task.expression}")
    
    # ========== 暂停调度器，再添加 JSON 配置 ==========
    print("\n📄 [步骤 2] 从 JSON 配置文件追加任务...")
    
    json_file = "/tmp/tasks.json"
    
    # 创建配置文件
    with open(json_file, 'w', encoding='utf-8') as f:
        f.write(JSON_CONFIG)
    
    print(f"  → 配置文件：{json_file}")
    print("  → 包含以下任务:")
    print("     • backup_task (新增): 每 4 秒，优先级 4")
    print("     • report_task (新增): 每 6 秒，优先级 2")
    
    loaded_count = cron.load_from_json(json_file)
    print(f"\n✅ 成功追加 {loaded_count} 个任务！")
    
    # 显示所有任务
    print("\n完整任务列表 (按优先级排序):")
    tasks = cron.list_tasks()
    sorted_tasks = sorted(tasks, key=lambda t: (-t.priority, t.name))
    for i, task in enumerate(sorted_tasks, 1):
        overlap_str = "并发" if task.allow_overlap else "单例"
        print(f"  {i}. [{task.priority:2d}] {task.name:15s} | {task.expression:15s} | {overlap_str}")
    
    # ========== 启动调度器运行观察 ==========
    print("\n" + "="*70)
    print("🚀 启动调度器，运行 15 秒后停止...")
    print("="*70)
    
    start_time = datetime.now()
    
    async def run_and_stop():
        task = asyncio.create_task(cron.start())
        
        try:
            await asyncio.sleep(15)
        finally:
            await cron.stop()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n✅ 调度器已停止，总运行时长：{duration:.1f} 秒")
        
        # 统计执行次数
        execution_counts = {}
        for record in cron.execution_history:
            name = record.task_name
            execution_counts[name] = execution_counts.get(name, 0) + 1
        
        print("\n📈 各任务执行次数统计:")
        for name, count in sorted(execution_counts.items()):
            print(f"  • {name}: {count} 次")
    
    # 运行异步函数
    asyncio.run(run_and_stop())
    
    # ========== 清理临时文件 ==========
    import os
    if os.path.exists(yaml_file):
        os.unlink(yaml_file)
    if os.path.exists(json_file):
        os.unlink(json_file)
    
    print("\n" + "="*70)
    print("配置文件加载演示完成！✨")
    print("="*70)
    
    print("\n💡 提示:")
    print("  • YAML 配置需要安装 pyyaml: pip install pyyaml")
    print("  • JSON 配置无需额外依赖（使用内置 json 模块）")
    print("  • 配置文件路径可以是绝对路径或相对路径")


if __name__ == "__main__":
    print("提示：此演示将创建临时配置文件 /tmp/tasks.yaml 和 /tmp/tasks.json")
    print("如需查看实际配置文件内容，请取消注释相关行\n")
    
    main()
