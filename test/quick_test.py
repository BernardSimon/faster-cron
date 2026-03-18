#!/usr/bin/env python3
"""Simple quick test for FasterCron"""
import sys
sys.path.insert(0, '..')

print("Testing...")

# Test imports
from faster_cron import FasterCron, AsyncFasterCron
print("✓ Import OK")

# Test sync
cron = FasterCron()
assert cron.tasks == []
print("✓ Sync init OK")

@cron.schedule('* * * * *')
def t(ctx): pass
assert len(cron.tasks) == 1
print("✓ Add task OK")

assert hasattr(cron, 'run')
print("✓ Has run method")

assert hasattr(cron, 'stop')
print("✓ Has stop method")

# Test async
async def test_async():
    cron = AsyncFasterCron()
    assert cron is not None
    
    @cron.schedule('* * * * *')
    async def at(ctx): pass
    assert len(cron.tasks) == 1
    
    await cron.start()
    print("✓ Async start OK")

import asyncio
asyncio.run(test_async())

print("\nAll basic tests passed!")
