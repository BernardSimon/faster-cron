"""
FasterCron v2.0 - 配置文件加载测试（YAML/JSON/TOML）
"""

import pytest
import asyncio
import time
import threading
import tempfile
import os
import json
from faster_cron import AsyncFasterCron, FasterCron


# ==================== YAML 配置加载测试 ====================

@pytest.mark.asyncio
async def test_load_from_yaml_async():
    """测试异步模式从 YAML 加载任务"""
    cron = AsyncFasterCron(log_level=0)
    
    # 创建临时 YAML 文件
    yaml_content = """
tasks:
  - module: my_app.backup
    function: nightly_backup
    expression: "0 2 * * * *"
    allow_overlap: false
  - module: my_app.report
    function: hourly_metrics
    expression: "*/60 * * * * *"
    allow_overlap: true
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_file = f.name
    
    try:
        count = cron.load_from_yaml(yaml_file)
        
        assert count == 2, f"应该加载 2 个任务，实际 {count}"
        assert len(cron.list_tasks()) == 2
        
        # 验证任务信息
        tasks = cron.list_tasks()
        assert tasks[0].name == "nightly_backup"
        assert tasks[0].expression == "0 2 * * * *"
        assert tasks[1].name == "hourly_metrics"
        
        print("✅ 异步 YAML 配置加载测试通过")
    finally:
        os.unlink(yaml_file)


def test_load_from_yaml_sync():
    """测试同步模式从 YAML 加载任务"""
    cron = FasterCron(log_level=0)
    
    yaml_content = """
tasks:
  - module: my_app.tasks
    function: periodic_job
    expression: "* * * * * *"
    allow_overlap: true
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_file = f.name
    
    try:
        count = cron.load_from_yaml(yaml_file)
        
        assert count == 1
        assert len(cron.list_tasks()) == 1
        assert cron.get_task("periodic_job").expression == "* * * * * *"
        
        print("✅ 同步 YAML 配置加载测试通过")
    finally:
        os.unlink(yaml_file)


# ==================== JSON 配置加载测试 ====================

@pytest.mark.asyncio
async def test_load_from_json_async():
    """测试异步模式从 JSON 加载任务"""
    cron = AsyncFasterCron(log_level=0)
    
    config_data = {
        "tasks": [
            {
                "module": "my_app.service",
                "function": "health_check",
                "expression": "*/30 * * * * *",
                "allow_overlap": True
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        json_file = f.name
    
    try:
        count = cron.load_from_json(json_file)
        
        assert count == 1
        assert len(cron.list_tasks()) == 1
        
        print("✅ 异步 JSON 配置加载测试通过")
    finally:
        os.unlink(json_file)


def test_load_from_json_sync():
    """测试同步模式从 JSON 加载任务"""
    cron = FasterCron(log_level=0)
    
    config_data = {
        "tasks": [
            {"module": "mod", "function": "func1", "expression": "0 0 * * * *"}
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        json_file = f.name
    
    try:
        count = cron.load_from_json(json_file)
        assert count == 1
        
        print("✅ 同步 JSON 配置加载测试通过")
    finally:
        os.unlink(json_file)


# ==================== JSON 配置加载测试 ====================

@pytest.mark.asyncio
async def test_load_from_json_async():
    """测试无效 YAML 结构时的处理"""
    cron = AsyncFasterCron(log_level=logging.INFO)
    
    # 缺少 module/function/expression
    yaml_content = """
tasks:
  - name: invalid_task
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_file = f.name
    
    try:
        count = cron.load_from_yaml(yaml_file)
        
        # 应该没有加载任何任务
        assert count == 0
        assert len(cron.list_tasks()) == 0
        
        print("✅ 无效 YAML 结构测试通过（忽略无效任务）")
    finally:
        os.unlink(yaml_file)


@pytest.mark.asyncio
async def test_nonexistent_module_async():
    """测试不存在的模块"""
    cron = AsyncFasterCron(log_level=logging.INFO)
    
    yaml_content = """
tasks:
  - module: nonexistent_module
    function: some_function
    expression: "* * * * * *"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_file = f.name
    
    try:
        count = cron.load_from_yaml(yaml_file)
        
        # 应该没有加载成功
        assert count == 0 or len(cron.list_tasks()) == 0
        
        print("✅ 不存在模块测试通过（正确记录错误）")
    finally:
        os.unlink(yaml_file)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("运行 FasterCron v2.0 配置文件加载测试")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
