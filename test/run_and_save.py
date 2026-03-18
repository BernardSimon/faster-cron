#!/usr/bin/env python3
import sys
sys.path.insert(0, '..')

results = []

# Test imports
try:
    from faster_cron import FasterCron, AsyncFasterCron
    results.append("✓ Import OK")
except Exception as e:
    results.append(f"✗ Import error: {e}")
    with open('test_results.txt', 'w') as f:
        f.write('\n'.join(results))
    sys.exit(1)

# Test sync
try:
    cron = FasterCron()
    assert cron.tasks == []
    results.append("✓ Sync init OK")
    
    @cron.schedule('* * * * *')
    def t(ctx): pass
    assert len(cron.tasks) == 1
    results.append("✓ Add task OK")
    
    assert hasattr(cron, 'run'), "Missing run method"
    results.append("✓ Has run method")
    
    assert hasattr(cron, 'stop'), "Missing stop method"
    results.append("✓ Has stop method")
except Exception as e:
    results.append(f"✗ Sync test error: {e}")
    with open('test_results.txt', 'w') as f:
        f.write('\n'.join(results))
    sys.exit(1)

# Test async
import asyncio
async def test_async():
    try:
        cron = AsyncFasterCron()
        assert cron is not None
        
        @cron.schedule('* * * * *')
        async def at(ctx): pass
        assert len(cron.tasks) == 1
        
        # Don't actually start, just verify structure
        assert hasattr(cron, 'start')
        assert hasattr(cron, 'run')
        
        return True
    except Exception as e:
        results.append(f"✗ Async test error: {e}")
        raise

try:
    asyncio.run(test_async())
    results.append("✓ Async OK")
except Exception as e:
    pass

# Save results
with open('test_results.txt', 'w') as f:
    f.write('\n'.join(results))
    f.write('\n\n' + '='*40 + '\n')
    if all(r.startswith('✓') for r in results):
        f.write("ALL TESTS PASSED!")
    else:
        f.write("SOME TESTS FAILED")
        sys.exit(1)

print("\n".join(results))
