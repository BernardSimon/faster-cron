# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.3.0] - 2026-06-10

### Changed
- Refactored: extracted shared scheduler logic into `SchedulerMixin` base class in `base.py`
- Performance: replaced brute-force `_calculate_next_trigger` with field-constrained stepping algorithm
- Performance: replaced `list` slicing with `collections.deque(maxlen=N)` for execution/error history
- Activated `SchedulerStats` for runtime monitoring via `get_stats()` method

### Added
- LICENSE file (MIT)
- GitHub Actions CI/CD pipeline (Python 3.8-3.12 matrix + lint)
- `py.typed` marker for PEP 561 compliance
- `[tool.mypy]` configuration in `pyproject.toml`
- `/api/stats` endpoint in web admin
- Comprehensive test coverage for cron parsing edge cases, `_calculate_next_trigger`, concurrent safety, and stats

## [2.2.0] - 2026-03-18

### Added
- Optional web admin UI with FastAPI + Tailwind CSS
- Internationalization (Chinese/English) in web admin
- Runtime web toggle (`enable_web` / `disable_web`)
- Paginated execution history in web admin
- CamelCase aliases for web methods

### Fixed
- Weekday mapping bug (weekday 7 → 0 for Sunday)

## [2.1.0] - 2026-03-15

### Added
- Comprehensive test suite (pytest + pytest-asyncio)
- `run()` method as alias for `start()`
- Configuration file loading (`load_from_yaml`, `load_from_json`)
- One-shot scheduler (`once_in`, `run_at`)
- Execution history and error history tracking

## [2.0.0] - 2026-03-10

### Added
- Async/sync dual engine design (`AsyncFasterCron`, `FasterCron`)
- Task management API (`pause_task`, `resume_task`, `disable_task`, `enable_task`, `remove_task`, `update_task`)
- Signature-aware context injection
- Overlap control (`allow_overlap`)
- Retry mechanism with configurable `max_retries` and `retry_delay`
- Error callbacks (`on_error`)
- Custom logger injection
