#!/usr/bin/env python3
"""
FasterCron 2.1 - 配置文件加载演示

展示如何从 YAML/JSON 文件加载任务配置！
"""

import logging
from datetime import datetime
from faster_cron import AsyncFasterCron, FasterCron


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sync_example():
    """同步模式 - 从 YAML 加载"""
    print("=" * 60)
    print("📄 同步模式 - 配置文件加载演示")
    print("=" * 60)
    
    # 创建调度器
    cron = FasterCron(log_level=logging.WARNING)
    
    try:
        # 加载 YAML 配置
        config_path = "examples/tasks.yaml"
        logger.info(f"📂 加载配置文件：{config_path}")
        
        cron.load_from_yaml(config_path)
        
        # 查看加载的任务
        tasks = cron.list_tasks()
        print(f"\n✅ 成功加载 {len(tasks)} 个任务:")
        
        for task in tasks:
            print(f"   • {task.name}:")
            print(f"     表达式：{task.expression}")
            print(f"     优先级：{task.priority}")
            print(f"     状态：{task.state.name}")
            print()
        
        # 注意：实际运行时需要 start()，但这里我们只演示配置加载
        
    except FileNotFoundError:
        logger.warning(f"配置文件不存在：{config_path}")
        logger.info("这是演示模式，不会实际运行所有任务。")
    except ImportError as e:
        logger.warning(f"缺少依赖库：{e}")
        logger.info("提示：pip install pyyaml")


async def async_example():
    """异步模式 - 从 JSON 加载"""
    print("=" * 60)
    print("🔄 异步模式 - 配置文件加载演示")
    print("=" * 60)
    
    # 创建异步调度器
    cron = AsyncFasterCron(log_level=logging.WARNING)
    
    try:
        # 加载 JSON 配置
        config_path = "examples/tasks.json"
        logger.info(f"📂 加载配置文件：{config_path}")
        
        cron.load_from_json(config_path)
        
        # 查看加载的任务
        tasks = cron.list_tasks()
        print(f"\n✅ 成功加载 {len(tasks)} 个任务:")
        
        for task in tasks:
            print(f"   • {task.name}:")
            print(f"     表达式：{task.expression}")
            print(f"     优先级：{task.priority}")
            print(f"     状态：{task.state.name}")
            print()
        
        # 注意：实际运行时需要 await start(), 但这里只演示加载
        
    except FileNotFoundError:
        logger.warning(f"配置文件不存在：{config_path}")
        logger.info("这是演示模式，不会实际运行所有任务。")
    except ImportError as e:
        logger.warning(f"需要安装依赖：{e}")
        logger.info("提示：pip install pyyaml")


if __name__ == "__main__":
    import asyncio
    
    print("\n🚀 FasterCron 2.1 - Config Loading Demo\n")
    
    # 同步示例
    try:
        sync_example()
    except Exception as e:
        logger.error(f"同步示例出错：{e}")
    
    print("\n")
    
    # 异步示例
    try:
        asyncio.run(async_example())
    except Exception as e:
        logger.error(f"异步示例出错：{e}")
    
    print("\n" + "=" * 60)
    print("✨ 演示完成！配置文件加载功能已就绪")
    print("=" * 60 + "\n")
