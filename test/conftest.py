"""
Common fixtures for FasterCron tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from faster_cron import AsyncFasterCron, FasterCron


@pytest.fixture
def sync_cron():
    """Create a synchronous cron instance"""
    return FasterCron(log_level=logging.WARNING)


@pytest.fixture
def async_cron():
    """Create an asynchronous cron instance"""
    return AsyncFasterCron(log_level=logging.WARNING)


@pytest.fixture
def sample_tasks():
    """Sample task functions for testing"""
    results = []
    
    def sync_task(ctx):
        results.append(('sync', ctx))
    
    async def async_task(ctx):
        results.append(('async', ctx))
    
    return {
        'sync': sync_task,
        'async': async_task,
        'results': results
    }
