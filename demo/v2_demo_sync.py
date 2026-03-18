#!/usr/bin/env python3
"""
FasterCron v2.0 - 完整功能演示（同步模式）

演示内容:
1. 高精度时间控制
2. 优雅状态管理 (信号处理)
3. 动态任务管理
4. 异常处理与重试机制
5. 一次性任务
6. 执行历史记录

运行方式：
    python demo/v2_demo_sync.py
"""

import signal
import sys
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

from faster_cron import FasterCron


def signal_handler(signum, frame):
    """SIGINT/SIGTERM 信号处理"""
    print("\n\n接收到退出信号...")
    cron.stop()
    sys.exit(0)


def main():
    print("="*70)
    print("FasterCron v2.0 完整功能演示（同步模式）")
    print("="*70)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建调度器（带详细日志和错误处理）
    cron = FasterCron(
        log_level=logging.DEBUG,
        max_retries=2,           # 最多重试 2 次
        retry_delay=0.5,         # 每次重试间隔 0.5 秒
    )
    
    # ========== 示例 1: 周期性任务 ==========
    print("\n📋 [示例 1] 注册周期性任务...")
    
    counter = [0]
    
    @cron.schedule("*/2 * * * * *")  # 每 2 秒
    def periodic_job(ctx):
        counter[0] += 1
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✓ [周期任务] 第 {counter[0]} 次执行 - 已运行 {elapsed:.1f}s")
    
    # ========== 示例 2: 模拟会失败的任务（测试重试） ==========
    print("\n📋 [示例 2] 注册一个会反复失败的任务...")
    
    fail_attempts = [0]
    
    @cron.schedule("* * * * * *")  # 每秒
    def flaky_task(ctx):
        fail_attempts[0] += 1
        
        if fail_attempts[0] <= 3:
            raise ValueError(f"模拟失败！尝试次数：{fail_attempts[0]}")
        
        print(f"✓ [故障任务] 经过 {fail_attempts[0]} 次尝试后成功！")
    
    # ========== 示例 3: 动态添加任务 ==========
    print("\n📋 [示例 3] 运行时动态添加新任务...")
    
    dynamic_counter = [0]
    
    def dynamic_function(ctx):
        dynamic_counter[0] += 1
        print(f"✓ [动态任务] 第 {dynamic_counter[0]} 次执行")
    
    # 先查询当前任务数
    initial_count = len(cron.list_tasks())
    print(f"  → 当前任务数：{initial_count}")
    
    # 动态添加一个新任务
    cron.add_task("*/3 * * * * *", dynamic_function, allow_overlap=True, priority=1)
    new_count = len(cron.list_tasks())
    print(f"  → 添加后任务数：{new_count}")
    
    # ========== 示例 4: 暂停/恢复任务 ==========
    print("\n📋 [示例 4] 演示任务的暂停和恢复...")
    
    paused_at = None
    
    @cron.schedule("*/5 * * * * *")  # 每 5 秒
    def long_running(ctx):
        now = datetime.now()
        print(f"✓ [长耗时任务] 执行于 {now.strftime('%H:%M:%S')}")
    
    time.sleep(8)
    paused_at = datetime.now()
    print(f"\n⏸️  在 {paused_at.strftime('%H:%M:%S')} 暂停任务 'long_running'...")
    cron.pause_task("long_running")
    
    time.sleep(6)
    resumed_at = datetime.now()
    print(f"▶️  在 {resumed_at.strftime('%H:%M:%S')} 恢复任务 'long_running'...")
    cron.resume_task("long_running")
    
    # ========== 示例 5: 一次性任务 ==========
    print("\n📋 [示例 5] 演示一次性任务...")
    
    @cron.once_in(3)  # 3 秒后执行一次
    def one_time_email(ctx):
        print(f"📨 [一次性任务] 发送周报邮件！类型：{ctx['execution_type']}")
    
    target_time = datetime.now() + __import__('datetime').timedelta(seconds=5)
    @cron.run_at(target_time)  # 5 秒后
    def scheduled_report(ctx):
        print(f"📊 [定时任务] 生成日报报表！预定时间：{target_time.strftime('%H:%M:%S')}")
    
    # ========== 示例 6: 查询任务信息 ==========
    print("\n📋 [示例 6] 查询任务详细信息...")
    
    all_tasks = cron.list_tasks()
    for task in all_tasks:
        print(f"  • {task.name}:")
        print(f"    - Cron: {task.expression}")
        print(f"    - 状态：{task.state.value}")
        print(f"    - 优先级：{task.priority}")
    
    # ========== 启动调度器 ==========
    print("\n🚀 启动调度器，准备运行 12 秒...")
    start_time = datetime.now()
    
    try:
        cron.run(wait_on_exit=True)
    except KeyboardInterrupt:
        print("\n用户中断！")
    
    print(f"\n✅ 调度器已停止")
    
    # ========== 显示执行统计 ==========
    print("\n📈 执行统计:")
    print(f"  • 周期任务执行次数：{counter[0]}")
    print(f"  • 故障任务尝试次数：{fail_attempts[0]}")
    print(f"  • 动态任务执行次数：{dynamic_counter[0]}")
    
    # 显示最近 10 条执行历史
    recent_executions = cron.execution_history[-10:]
    if recent_executions:
        print(f"\n  最近 {len(recent_executions)} 次执行记录:")
        for record in recent_executions:
            status = "✓成功" if record.success else f"✗失败 ({record.retry_count}次重试)"
            duration = f"{record.elapsed_ms:.0f}ms" if record.elapsed_ms else "-"
            print(f"    - {record.task_name}: {status} ({duration})")
    
    # 显示错误历史
    if cron.error_history:
        print(f"\n  错误记录数：{len(cron.error_history)}")
    
    print("\n" + "="*70)
    print("演示完成！✨")
    print("="*70)


if __name__ == "__main__":
    print("提示：按 Ctrl+C 可提前结束演示")
    main()
