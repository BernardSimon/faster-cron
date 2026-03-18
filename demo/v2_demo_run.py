#!/usr/bin/env python3
"""
FasterCron 2.1 - run() 方法演示

展示同步模式的 run(wait_on_exit=True) 和异步模式的运行方式！
"""

import asyncio
import logging
import time
from datetime import datetime
from faster_cron import AsyncFasterCron, FasterCron


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sync_example():
    """同步模式 - run(wait_on_exit=True)"""
    print("=" * 60)
    print("🔧 同步模式 - run(wait_on_exit=True)")
    print("=" * 60)
    
    cron = FasterCron(log_level=logging.WARNING)
    
    # 添加任务
    counter = [0]
    
    @cron.schedule("* * * * *")
    def every_minute(ctx):
        counter[0] += 1
        print(f"✅ [Sync] Every minute task executed! (count: {counter[0]})")
    
    logger.info("添加了一个每分钟执行的任务")
    
    # 运行 5 秒后停止
    import threading
    
    def stop_after_delay():
        time.sleep(3)
        logger.info("3 秒后停止调度器...")
        cron.stop()
    
    timer = threading.Thread(target=stop_after_delay, daemon=True)
    timer.start()
    
    # 使用 run(wait_on_exit=False) - 立即返回，在后台运行
    logger.info("调用 cron.run(wait_on_exit=False)...")
    cron.run(wait_on_exit=False)
    
    print("\n✓ 同步演示完成")


async def async_example():
    """异步模式 - await cron.run()"""
    print("=" * 60)
    print("🔄 异步模式 - await cron.run()")
    print("=" * 60)
    
    cron = AsyncFasterCron(log_level=logging.WARNING)
    
    # 添加任务
    counter = [0]
    
    @cron.schedule("* * * * *")
    async def every_minute_async(ctx):
        counter[0] += 1
        print(f"✅ [Async] Every minute task executed! (count: {counter[0]})")
    
    logger.info("添加了一个每分钟的异步任务")
    
    # 运行 5 秒后停止
    async def stop_after_delay():
        await asyncio.sleep(3)
        logger.info("3 秒后停止调度器...")
        await cron.stop()
    
    stop_task = asyncio.create_task(stop_after_delay())
    
    # 使用 run() - 等同于 start()
    logger.info("调用 await cron.run()...")
    await cron.run()
    
    print("\n✓ 异步演示完成")


if __name__ == "__main__":
    print("\n🚀 FasterCron 2.1 - run() Method Demo\n")
    
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
    print("✨ run() 方法演示完成！")
    print("=" * 60 + "\n")
