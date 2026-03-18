# FasterCron Test Suite

## Quick Start

```bash
# Run all tests
cd /home/gem/workspace/agent/workspace/faster-cron
python3 test/run_and_save.py

# View detailed results
cat test/test_results.txt
```

## Test Files

- `conftest.py` - Pytest fixtures and common utilities
- `test_sync_cron.py` - Synchronous cron tests  
- `test_async_cron.py` - Asynchronous cron tests
- `verify_tests.py` - Comprehensive verification script
- `quick_test.py` - Simple smoke test
- `run_and_save.py` - Automated test runner with file output

## Running with pytest

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
python3 -m pytest test/ -v

# With coverage
python3 -m pytest test/ --cov=faster_cron --cov-report=html
```

## What's Tested

### Sync Cron (`FasterCron`)
✓ Initialization
✓ Task scheduling (`@schedule` decorator)
✓ Dynamic task management (add/remove/pause/resume/disable/enable)
✓ One-shot execution (`once_in`, `run_at`)
✓ Execution tracking
✓ Configuration loading methods
✓ Run method with wait_on_exit parameter

### Async Cron (`AsyncFasterCron`)
✓ Initialization
✓ Task scheduling (`@schedule` decorator)
✓ Dynamic task management
✓ One-shot execution (async versions)
✓ Run/start aliases
✓ Execution tracking

## Notes

- Tests use minimal timeouts for one-shot schedulers
- YAML loading tests require `pyyaml` package
- Full integration tests can be added later
- Code coverage target: 90%+

## Success Criteria

All assertions must pass:
- ✓ Import OK
- ✓ Sync init OK
- ✓ Add task OK  
- ✓ Has run method
- ✓ Has stop method
- ✓ Async OK
- ✓ One-shot decorators work
- ✓ Config loading methods exist
