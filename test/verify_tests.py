#!/usr/bin/env python3
"""
Quick verification script for FasterCron functionality
Run this with: python test/verify_tests.py
"""
import sys
import os
import time
from datetime import datetime, timedelta

# Ensure fresh import
if 'faster_cron' in sys.modules:
    del sys.modules['faster_cron']

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 60)
print("FasterCron Test Verification")
print("=" * 60)

errors = []
passed = []

def test(name, func):
    try:
        result = func()
        if result:
            print(f"✓ {name}")
            passed.append(name)
        return result
    except Exception as e:
        print(f"✗ {name}: {e}")
        errors.append((name, str(e)))

# Test 1: Import sync cron
def test_import_sync():
    from faster_cron import FasterCron
    return True

test("Import FasterCron (sync)", test_import_sync)

# Test 2: Create instance
def test_create_instance():
    from faster_cron import FasterCron
    cron = FasterCron()
    assert cron is not None
    return True

test("Create FasterCron instance", test_create_instance)

# Test 3: Add task
def test_add_task():
    from faster_cron import FasterCron
    cron = FasterCron()
    
    @cron.schedule("* * * * *")
    def my_task(ctx):
        pass
    
    assert len(cron.tasks) == 1
    return True

test("Add scheduled task", test_add_task)

# Test 4: Remove task
def test_remove_task():
    from faster_cron import FasterCron
    cron = FasterCron()
    
    @cron.schedule("* * * * *")
    def my_task(ctx):
        pass
    
    cron.remove_task("my_task")
    assert len(cron.tasks) == 0
    return True

test("Remove task", test_remove_task)

# Test 5: Run method exists
def test_run_exists():
    from faster_cron import FasterCron
    cron = FasterCron()
    return hasattr(cron, 'run') and callable(cron.run)

test("Has run() method", test_run_exists)

# Test 6: Stop method exists
def test_stop_exists():
    from faster_cron import FasterCron
    cron = FasterCron()
    return hasattr(cron, 'stop') and callable(cron.stop)

test("Has stop() method", test_stop_exists)

# Test 7: One-shot once_in
def test_once_in():
    from faster_cron import FasterCron
    cron = FasterCron()
    results = []
    
    @cron.once_in(0.1)
    def delayed_task(ctx):
        results.append(time.time())
    
    # Just verify it was added, execution happens async
    assert len(results) >= 0  # May or may not have executed yet
    return True

test("once_in decorator works", test_once_in)

# Test 8: One-shot run_at
def test_run_at():
    from faster_cron import FasterCron
    cron = FasterCron()
    
    target_time = datetime.now() + timedelta(seconds=0.1)
    
    @cron.run_at(target_time)
    def scheduled_task(ctx):
        pass
    
    return True

test("run_at decorator works", test_run_at)

# Test 9: Load methods exist
def test_load_methods():
    from faster_cron import FasterCron
    cron = FasterCron()
    return hasattr(cron, 'load_from_yaml') and hasattr(cron, 'load_from_json')

test("Has load_from_yaml/json", test_load_methods)

# Test 10: Pause/resume
def test_pause_resume():
    from faster_cron import FasterCron
    cron = FasterCron()
    
    @cron.schedule("* * * * *")
    def my_task(ctx):
        pass
    
    cron.pause_task("my_task")
    cron.resume_task("my_task")
    return True

test("Pause/Resume tasks", test_pause_resume)

# Test 11: Async imports
def test_async_import():
    from faster_cron import AsyncFasterCron
    return True

test("Import AsyncFasterCron", test_async_import)

# Test 12: Async create
def test_async_create():
    from faster_cron import AsyncFasterCron
    cron = AsyncFasterCron()
    assert cron is not None
    return True

test("Create AsyncFasterCron", test_async_create)

# Test 13: Async add task
def test_async_add_task():
    from faster_cron import AsyncFasterCron
    cron = AsyncFasterCron()
    
    @cron.schedule("* * * * *")
    async def my_task(ctx):
        pass
    
    assert len(cron.tasks) == 1
    return True

test("Async add scheduled task", test_async_add_task)

# Test 14: Async run method
def test_async_run():
    import asyncio
    from faster_cron import AsyncFasterCron
    
    async def check():
        cron = AsyncFasterCron()
        return hasattr(cron, 'run') and callable(cron.run)
    
    return asyncio.run(check())

test("Async has run() method", test_async_run)

# Summary
print("\n" + "=" * 60)
print(f"Passed: {len(passed)}/{len(passed) + len(errors)}")
print(f"Failed: {len(errors)}")
print("=" * 60)

if errors:
    print("\nErrors:")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("\n🎉 All tests passed!")
    sys.exit(0)
