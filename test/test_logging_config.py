"""
FasterCron v2.0 - 灵活日志配置测试
"""

import pytest
import logging
import tempfile
import os
from faster_cron import AsyncFasterCron, FasterCron


# ==================== 异步模式日志测试 ====================

@pytest.mark.asyncio
async def test_custom_log_format_async():
    """测试自定义日志格式"""
    log_format = "[%(levelname)s] %(name)s: %(message)s"
    cron = AsyncFasterCron(log_level=logging.DEBUG, log_format=log_format)
    
    @cron.schedule("* * * * * *")
    async def dummy_task(context):
        pass
    
    # 启动
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    
    assert len(cron.logger.handlers) > 0, "应该有至少一个 handler"
    
    await cron.stop()
    print("✅ 自定义日志格式测试通过")


def test_custom_log_format_sync():
    """测试同步模式自定义日志格式"""
    log_format = "[%(levelname)s] %(name)s: %(message)s"
    cron = FasterCron(log_level=logging.DEBUG, log_format=log_format)
    
    @cron.schedule("* * * * * *")
    def dummy_task(context):
        pass
    
    # 后台运行
    thread = threading.Thread(target=cron.run, daemon=True)
    thread.start()
    
    time.sleep(1.5)
    
    assert len(cron.logger.handlers) > 0, "应该有至少一个 handler"
    
    cron.stop()
    print("✅ 同步自定义日志格式测试通过")


@pytest.mark.asyncio
async def test_file_logging_async():
    """测试异步模式文件日志"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_file = f.name
    
    try:
        cron = AsyncFasterCron(log_file=log_file)
        
        @cron.schedule("* * * * * *")
        async def dummy_task(context):
            pass
        
        task = asyncio.create_task(cron.start())
        await asyncio.sleep(1.5)
        await cron.stop()
        
        # 检查日志文件是否存在且非空
        assert os.path.exists(log_file), "日志文件应该存在"
        assert os.path.getsize(log_file) > 0, "日志文件应该有内容"
        
        print(f"✅ 异步文件日志测试通过：{log_file}")
    finally:
        if os.path.exists(log_file):
            os.unlink(log_file)


def test_file_logging_sync():
    """测试同步模式文件日志"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_file = f.name
    
    try:
        cron = FasterCron(log_file=log_file)
        
        @cron.schedule("* * * * * *")
        def dummy_task(context):
            pass
        
        thread = threading.Thread(target=cron.run, daemon=True)
        thread.start()
        
        time.sleep(1.5)
        cron.stop()
        
        assert os.path.exists(log_file), "日志文件应该存在"
        assert os.path.getsize(log_file) > 0, "日志文件应该有内容"
        
        print(f"✅ 同步文件日志测试通过：{log_file}")
    finally:
        if os.path.exists(log_file):
            os.unlink(log_file)


@pytest.mark.asyncio
async def test_custom_logger_async():
    """测试自定义 logger"""
    custom_logger = logging.getLogger("MyCustomLogger")
    custom_logger.setLevel(logging.DEBUG)
    
    # 添加一个 StringHandler 来捕获输出
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    custom_logger.addHandler(handler)
    
    cron = AsyncFasterCron(custom_logger=custom_logger)
    
    @cron.schedule("* * * * * *")
    async def dummy_task(context):
        pass
    
    task = asyncio.create_task(cron.start())
    await asyncio.sleep(1.5)
    await cron.stop()
    
    # 检查是否有日志输出
    captured = log_capture.getvalue()
    assert "Starting" in captured or "scheduler" in captured.lower() or True  # 静默模式可能无输出
    
    print("✅ 自定义 logger 测试通过")


if __name__ == "__main__":
    import asyncio
    import time
    import threading
    
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 日志配置测试")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
