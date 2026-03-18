# AGENTS.md

## Project shape
- `faster_cron/` contains two mirrored scheduler engines: `AsyncFasterCron` in `faster_cron/async_cron.py` and `FasterCron` in `faster_cron/sync_cron.py`. Keep public behavior aligned unless the difference is inherently async/sync.
- Public imports come from `faster_cron/__init__.py`; export any new user-facing symbol there.
- Shared cron parsing lives in `faster_cron/base.py` (`CronBase.is_time_match`). It supports 5-field and 6-field expressions and uses standard cron OR semantics when both day-of-month and weekday are constrained.
- Runtime metadata is centralized in `faster_cron/models.py` (`TaskInfo`, `TaskState`, `ExecutionRecord`). Both schedulers keep raw task dicts in `self.tasks` for runtime loops plus richer `TaskInfo` objects in `task_registry` for inspection.
- `faster_cron/example_tasks.py` holds repo-local functions used by demos and config-loading tests; prefer it over fake modules in examples.

## Scheduling internals that matter
- Next-run calculation is brute-force by second: `_calculate_next_trigger()` scans forward from the next whole second up to 1 year. Both engines then sleep/wait for `min(delay_seconds, 0.5)` before re-checking.
- `allow_overlap=False` is enforced differently per engine: sync stores `last_worker` in the task dict; async tracks a per-monitor `current_task`.
- Recurring task context always includes `scheduled_at` and `task_name`.
- Context injection is signature-aware: prefer `context=` if the callable declares `context` or `**kwargs`; otherwise a single plain positional parameter (for example `ctx`) receives the context object.
- One-shot scheduling (`once_in`, `run_at`) is implemented separately from recurring monitors, supports explicit `args`/`kwargs`, adds `execution_type` to context, and cleans its task entry from `task_registry`/`self.tasks` after execution.

## Lifecycle and config loading
- Async lifecycle: `await start()` / `await stop()`; `run()` is a compatibility alias to `start()`.
- Sync lifecycle: `start(wait_on_exit=...)` and `run(wait_on_exit=...)`; `stop(wait_timeout=...)` joins monitor/worker/timer threads.
- `load_from_yaml()` / `load_from_json()` are synchronous helpers in both engines. They read a `tasks:` array, then use `importlib.import_module(module)` + `getattr(function)` before calling `add_task()`.
- YAML support is optional (`pyproject.toml`: extra `yaml = ["pyyaml"]`). `load_from_yaml()` should raise a clear `ImportError` when PyYAML is unavailable.
- Example config shape is in `examples/tasks.yaml` and `examples/tasks.json`; both now point at `faster_cron.example_tasks` so demos are runnable.

## Repo-specific testing and workflow
- Preferred local setup:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install pyyaml
```
- Main validation entry points:
```bash
pytest test/ -v
python test/quick_test.py
```
- Useful demos:
```bash
python demo/v2_demo_async.py
python demo/v2_demo_sync.py
python demo/v2_demo_config.py
python demo/v2_demo_run.py
python demo/v2_demo_one_shot.py
python demo/v2_demo_management.py
```
- The test suite intentionally reaches into some internals (`_active_tasks`, `_execute_task`, `task_registry`, raw `self.tasks`) to verify lifecycle and one-shot behavior, so renaming those requires coordinated updates.

## Project conventions
- Keep async/sync code paths behaviorally aligned when adding features or fixing bugs.
- Prefer small repo-local demos/tests over placeholder imports; `faster_cron.example_tasks` exists for that purpose.
- When docs, demos, and source drift, treat current source + tests as the contract and update the docs/demos in the same change.
