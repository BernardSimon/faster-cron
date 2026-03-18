#!/usr/bin/env python3
"""
FasterCron 2.1 - 一次性任务演示

演示如何使用一次性的延迟和定时执行功能！
"""

import asyncio
import logging
from datetime import datetime, timedelta
from faster_cron import AsyncOneShotScheduler, OneShotScheduler


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sync_example():
    """同步模式示例"""
    print("=" * 60)
    print("📅 同步模式 - 一次性任务演示")
    print("=" * 60)
    
    # 创建调度器
    cron = OneShotScheduler(log_level=logging.INFO)
    
    # 示例 1: 延迟 3 秒后执行
    def send_email():
        logger.info("📧 正在发送邮件...")
    
    logger.info("🔔 计划在 3 秒后发送邮件...")
    record1 = cron.once_in(3, send_email)
    
    # 示例 2: 指定时间执行（5 秒后）
    def generate_report():
        logger.info("📊 正在生成报告...")
    
    target_time = datetime.now() + timedelta(seconds=5)
    logger.info(f"🔔 计划在 {target_time} 生成报告...")
    record2 = cron.run_at(target_time, generate_report)
    
    # 示例 3: 连续多个一次性任务
    def task_a():
        logger.info("⚡ 任务 A 执行完成！")
    
    def task_b():
        logger.info("⚡ 任务 B 执行完成！")
    
    def task_c():
        logger.info("⚡ 任务 C 执行完成！")
    
    logger.info("\n📋 添加一组快速执行的任务...")
    cron.once_in(0.5, task_a)
    cron.once_in(1.0, task_b)
    cron.once_in(1.5, task_c)
    
    # 等待所有任务完成
    logger.info("\n⏳ 等待所有任务执行完毕...")
    print("(程序将等待约 5 秒)")
    
    # 同步调度器会自己管理循环直到所有任务完成
    # 这里我们用 sleep 来等待
    time.sleep(5)
    
    # 查看执行记录
    logger.info(f"\n✅ 成功执行：{len(cron.execution_history)} 次")
    logger.info(f"❌ 失败执行：{len(cron.error_history)} 次")
    
    if cron.execution_history:
        for record in cron.execution_history[:3]:
            logger.info(
                f"   • {record.task_name}: "
                f"{record.duration_seconds:.2f}s | "
                f"{'✅' if record.success else '❌'}"
            )


async def async_example():
    """异步模式示例"""
    print("=" * 60)
    print("🔄 异步模式 - 一次性任务演示")
    print("=" * 60)
    
    # 创建异步调度器
    cron = AsyncOneShotScheduler(log_level=logging.INFO)
    
    # 示例 1: 延迟 3 秒发送异步消息
    async def send_async_message():
        await asyncio.sleep(0.5)  # 模拟网络请求
        logger.info("💬 异步消息已发送！")
    
    logger.info("🔔 计划在 3 秒后发送异步消息...")
    record1 = await cron.once_in(3, send_async_message)
    
    # 示例 2: 指定时间执行（4 秒后）
    async def fetch_data():
        await asyncio.sleep(0.3)
        logger.info("🌐 数据获取完成！")
    
    target_time = datetime.now() + timedelta(seconds=4)
    logger.info(f"🔔 计划在 {target_time} 获取数据...")
    record2 = await cron.run_at(target_time, fetch_data)
    
    # 示例 3: 使用 context 参数
    async def task_with_context(context):
        await asyncio.sleep(0.2)
        logger.info(f"🎯 任务 {context['task_name']} 执行完成!")
        logger.info(f"   📅 计划时间：{context['scheduled_at']}")
    
    logger.info("\n📋 添加带有 context 的任务...")
    await cron.once_in(1, task_with_context)
    
    # 示例 4: 错误处理
    async def failing_task():
        raise RuntimeError("这是一个测试错误!")
    
    def error_handler(error, record):
        logger.warning(f"⚠️ 错误回调被调用：{error}")
    
    logger.info("\n🔴 故意添加一个会失败的任务...")
    cron.on_error = error_handler
    await cron.once_in(2, failing_task)
    
    # 等待所有任务完成
    logger.info("\n⏳ 等待所有任务执行完毕...")
    print("(程序将等待约 6 秒)")
    await asyncio.sleep(6)
    
    # 查看所有执行记录
    logger.info(f"\n📊 执行统计:")
    logger.info(f"   ✅ 成功执行：{len(cron.execution_history)} 次")
    logger.info(f"   ❌ 失败执行：{len(cron.error_history)} 次")
    
    # 显示历史记录
    logger.info("\n📝 最近执行记录:")
    for i, record in enumerate(cron.execution_history[-3:], 1):
        status = "✅" if record.success else "❌"
        logger.info(
            f"   {i}. {record.task_name}: "
            f"{record.duration_seconds:.2f}s | "
            f"{status}"
        )


if __name__ == "__main__":
    import time
    
    print("\n🚀 FasterCron 2.1 - One Shot Scheduler Demo\n")
    
    # 运行同步示例
    try:
        sync_example()
    except Exception as e:
        logger.error(f"同步示例出错：{e}")
    
    print("\n")
    
    # 运行异步示例
    try:
        asyncio.run(async_example())
    except Exception as e:
        logger.error(f"异步示例出错：{e}")
    
    print("\n" + "=" * 60)
    print("✨ 演示完成！感谢使用 FasterCron One Shot Scheduler!")
    print("=" * 60 + "\n")
