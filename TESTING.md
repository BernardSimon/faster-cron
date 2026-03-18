# FasterCron Testing Guide

## Running Tests

```bash
cd faster-cron
python3 -m pytest test/ -v
```

## Manual Verification

```bash
python3 test/quick_test.py
```

## Test Coverage

### Sync Cron (`test_sync_cron.py`)
- Initialization tests
- Task management (add, remove, pause, resume)
- One-shot scheduler (`once_in`, `run_at`)
- Execution records
- Configuration loading

### Async Cron (`test_async_cron.py`)
- Initialization tests  
- Task management
- One-shot scheduler
- Execution records
- run() / start() methods

## Expected Results

All tests should pass:
- ✓ Import OK
- ✓ Sync init OK  
- ✓ Add task OK
- ✓ Has run method
- ✓ Has stop method
- ✓ Async OK

## Known Issues

1. No pytest configuration in pyproject.toml
2. Need to install dev dependencies: `pip install -e ".[dev]"`
3. For YAML tests: `pip install pyyaml`
