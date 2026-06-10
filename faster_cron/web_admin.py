import asyncio
import importlib
import threading
from typing import Any, Dict, List, Optional


def _require_web_dependencies():
    try:
        from fastapi import Body, FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise ImportError(
            "Web admin requires optional dependencies. Install 'faster-cron[web]'."
        ) from exc

    try:
        import uvicorn
    except ImportError as exc:
        raise ImportError(
            "Web admin requires uvicorn. Install 'faster-cron[web]'."
        ) from exc

    return FastAPI, HTTPException, HTMLResponse, BaseModel, Body, Field, uvicorn


def _safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return repr(value)


def _serialize_task(task_info: Any) -> Dict[str, Any]:
    payload = task_info.to_dict()
    payload["task_args"] = _safe_value(payload.get("task_args", []))
    payload["task_kwargs"] = _safe_value(payload.get("task_kwargs", {}))
    return payload


def _serialize_record(record: Any) -> Dict[str, Any]:
    return record.to_dict()


def _import_task_callable(module_name: str, function_name: str):
    module = importlib.import_module(module_name)
    func = getattr(module, function_name)
    return func


def create_web_app(cron: Any):
    FastAPI, HTTPException, HTMLResponse, BaseModel, Body, Field, _ = _require_web_dependencies()

    class CreateTaskRequest(BaseModel):
        expression: str
        module: str
        function: str
        allow_overlap: bool = True
        args: List[Any] = Field(default_factory=list)
        kwargs: Dict[str, Any] = Field(default_factory=dict)

    class UpdateTaskRequest(BaseModel):
        expression: Optional[str] = None
        allow_overlap: Optional[bool] = None
        args: Optional[List[Any]] = None
        kwargs: Optional[Dict[str, Any]] = None

    app = FastAPI(title="FasterCron Web Admin")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _render_index_page()

    @app.get("/api/tasks")
    async def list_tasks() -> Dict[str, Any]:
        tasks = [_serialize_task(item) for item in cron.list_tasks()]
        return {"tasks": tasks}

    @app.post("/api/tasks")
    async def create_task(payload: CreateTaskRequest = Body(...)) -> Dict[str, Any]:
        try:
            func = _import_task_callable(payload.module, payload.function)
        except (ImportError, AttributeError) as exc:
            raise HTTPException(status_code=400, detail=f"Failed to import task: {exc}")

        task_info = cron.add_task(
            expression=payload.expression,
            func=func,
            allow_overlap=payload.allow_overlap,
            args=tuple(payload.args),
            kwargs=dict(payload.kwargs),
        )
        return _serialize_task(task_info)

    @app.put("/api/tasks/{task_name}")
    async def update_task(task_name: str, payload: UpdateTaskRequest = Body(...)) -> Dict[str, Any]:
        updated = cron.update_task(
            task_name,
            expression=payload.expression,
            allow_overlap=payload.allow_overlap,
            args=tuple(payload.args) if payload.args is not None else None,
            kwargs=dict(payload.kwargs) if payload.kwargs is not None else None,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return _serialize_task(updated)

    @app.delete("/api/tasks/{task_name}")
    async def delete_task(task_name: str) -> Dict[str, Any]:
        removed = cron.remove_task(task_name)
        return {"ok": removed}

    @app.post("/api/tasks/{task_name}/pause")
    async def pause_task(task_name: str) -> Dict[str, Any]:
        ok = cron.pause_task(task_name)
        return {"ok": ok}

    @app.post("/api/tasks/{task_name}/resume")
    async def resume_task(task_name: str) -> Dict[str, Any]:
        ok = cron.resume_task(task_name)
        return {"ok": ok}

    @app.get("/api/history")
    async def execution_history(limit: int = 100) -> Dict[str, Any]:
        records = [_serialize_record(record) for record in cron.execution_history[-max(limit, 1):]]
        return {"records": records}

    @app.get("/api/errors")
    async def error_history(limit: int = 100) -> Dict[str, Any]:
        records = [_serialize_record(record) for record in cron.error_history[-max(limit, 1):]]
        return {"records": records}

    @app.get("/api/stats")
    async def get_stats() -> Dict[str, Any]:
        return cron.get_stats().to_dict()

    return app


class _NoSignalUvicornServer:
    def __init__(self, uvicorn_module, app, host: str, port: int):
        config = uvicorn_module.Config(app=app, host=host, port=port, log_level="warning")

        class _Server(uvicorn_module.Server):
            def install_signal_handlers(self):
                return None

        self.server = _Server(config=config)


class WebAdminServer:
    def __init__(self, cron: Any, host: str, port: int, logger: Any):
        _, _, _, _, _, _, uvicorn = _require_web_dependencies()
        self._uvicorn = uvicorn
        self._cron = cron
        self._host = host
        self._port = port
        self._logger = logger
        self._app = create_web_app(cron)
        self._thread: Optional[threading.Thread] = None
        self._runner: Optional[_NoSignalUvicornServer] = None
        self._serve_task: Optional[asyncio.Task] = None

    def start_sync(self):
        if self._thread and self._thread.is_alive():
            return

        self._runner = _NoSignalUvicornServer(self._uvicorn, self._app, self._host, self._port)

        def run_server():
            self._runner.server.run()

        self._thread = threading.Thread(target=run_server, name="FasterCronWebAdmin", daemon=True)
        self._thread.start()

    def stop_sync(self, wait_timeout: Optional[float] = None):
        if self._runner is None:
            return

        self._runner.server.should_exit = True
        if self._thread is not None:
            timeout = wait_timeout if wait_timeout is not None else 2.0
            self._thread.join(timeout=timeout)
        self._thread = None
        self._runner = None

    async def start_async(self):
        if self._serve_task and not self._serve_task.done():
            return

        self._runner = _NoSignalUvicornServer(self._uvicorn, self._app, self._host, self._port)
        self._serve_task = asyncio.create_task(self._runner.server.serve(), name="faster-cron-web-admin")
        await asyncio.sleep(0)

    async def stop_async(self):
        if self._runner is None:
            return

        self._runner.server.should_exit = True
        if self._serve_task is not None:
            try:
                await asyncio.wait_for(self._serve_task, timeout=2.0)
            except asyncio.TimeoutError:
                self._serve_task.cancel()
        self._serve_task = None
        self._runner = None


def _render_index_page() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>FasterCron Web Admin</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
</head>
<body class=\"bg-slate-50 text-slate-900\">
  <main class=\"max-w-6xl mx-auto p-6 space-y-6\">
    <section class=\"bg-white rounded-xl shadow p-4\">
      <div class=\"flex items-start justify-between gap-3\">
        <div>
          <h1 class=\"text-xl font-semibold\" data-i18n=\"app.title\">FasterCron Web Admin</h1>
          <p class=\"text-sm text-slate-600 mt-1\" data-i18n=\"app.subtitle\">任务管理、参数查看和执行记录面板</p>
        </div>
        <div class=\"flex items-center gap-2\">
          <label for=\"language-switch\" class=\"text-sm text-slate-600\" data-i18n=\"lang.label\">语言</label>
          <select id=\"language-switch\" class=\"border rounded px-2 py-1 text-sm\">
            <option value=\"zh\">中文</option>
            <option value=\"en\">English</option>
          </select>
        </div>
      </div>
    </section>

    <section class=\"grid md:grid-cols-2 gap-4\">
      <div class=\"bg-white rounded-xl shadow p-4 space-y-3\">
        <h2 class=\"font-medium\" data-i18n=\"create.title\">新增任务</h2>
        <input id=\"task-expression\" class=\"w-full border rounded px-3 py-2\" placeholder=\"表达式，例如 */5 * * * * *\" data-i18n-placeholder=\"create.expression_placeholder\" />
        <input id=\"task-module\" class=\"w-full border rounded px-3 py-2\" placeholder=\"模块，例如 faster_cron.example_tasks\" data-i18n-placeholder=\"create.module_placeholder\" />
        <input id=\"task-function\" class=\"w-full border rounded px-3 py-2\" placeholder=\"函数，例如 heartbeat\" data-i18n-placeholder=\"create.function_placeholder\" />
        <label class=\"inline-flex gap-2 items-center text-sm\"><input id=\"task-overlap\" type=\"checkbox\" checked /><span data-i18n=\"common.allow_overlap\">允许重叠执行</span></label>
        <textarea id=\"task-args\" class=\"w-full border rounded px-3 py-2\" rows=\"2\" placeholder=\"args JSON 数组，例如 [1, &quot;a&quot;]\" data-i18n-placeholder=\"create.args_placeholder\"></textarea>
        <textarea id=\"task-kwargs\" class=\"w-full border rounded px-3 py-2\" rows=\"2\" placeholder=\"kwargs JSON 对象，例如 {&quot;env&quot;:&quot;dev&quot;}\" data-i18n-placeholder=\"create.kwargs_placeholder\"></textarea>
        <button onclick=\"createTask()\" class=\"bg-blue-600 text-white px-4 py-2 rounded\" data-i18n=\"create.submit\">创建任务</button>
      </div>

      <div class=\"bg-white rounded-xl shadow p-4 space-y-3\">
        <h2 class=\"font-medium\" data-i18n=\"edit.title\">编辑任务</h2>
        <select id=\"edit-task-name\" class=\"w-full border rounded px-3 py-2\"></select>
        <input id=\"edit-task-expression\" class=\"w-full border rounded px-3 py-2\" placeholder=\"cron 表达式\" data-i18n-placeholder=\"edit.expression_placeholder\" />
        <label class=\"inline-flex gap-2 items-center text-sm\"><input id=\"edit-task-overlap\" type=\"checkbox\" /><span data-i18n=\"common.allow_overlap\">允许重叠执行</span></label>
        <textarea id=\"edit-task-args\" class=\"w-full border rounded px-3 py-2\" rows=\"2\" placeholder=\"args JSON 数组\" data-i18n-placeholder=\"edit.args_placeholder\"></textarea>
        <textarea id=\"edit-task-kwargs\" class=\"w-full border rounded px-3 py-2\" rows=\"2\" placeholder=\"kwargs JSON 对象\" data-i18n-placeholder=\"edit.kwargs_placeholder\"></textarea>
        <div class=\"flex gap-2\">
          <button onclick=\"submitTaskEdit()\" class=\"bg-indigo-600 text-white px-4 py-2 rounded\" data-i18n=\"edit.save\">保存修改</button>
          <button onclick=\"fillEditorBySelection()\" class=\"bg-slate-500 text-white px-4 py-2 rounded\" data-i18n=\"edit.reload\">重新加载</button>
        </div>
      </div>
    </section>

    <section class=\"bg-white rounded-xl shadow p-4\">
      <div class=\"flex items-center justify-between\">
        <h2 class=\"font-medium\" data-i18n=\"table.title\">任务列表</h2>
        <button onclick=\"loadTasks()\" class=\"bg-emerald-600 text-white px-3 py-2 rounded text-sm\" data-i18n=\"table.refresh\">刷新</button>
      </div>
      <div class=\"overflow-auto mt-3\">
        <table class=\"w-full text-sm\">
          <thead>
            <tr class=\"text-left border-b\">
              <th class=\"py-2\" data-i18n=\"table.name\">名称</th>
              <th data-i18n=\"table.expression\">表达式</th>
              <th data-i18n=\"table.state\">状态</th>
              <th data-i18n=\"table.params\">参数</th>
              <th data-i18n=\"table.actions\">操作</th>
            </tr>
          </thead>
          <tbody id=\"task-table\"></tbody>
        </table>
      </div>
    </section>

    <section class="bg-white rounded-xl shadow p-4 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="font-medium" data-i18n="history.title">执行记录</h2>
        <button onclick="refreshExecutionTables()" class="bg-slate-700 text-white px-3 py-2 rounded text-sm" data-i18n="history.refresh_all">刷新记录</button>
      </div>

      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-emerald-700" data-i18n="history.success_title">成功记录</h3>
          <div class="flex items-center gap-2 text-sm">
            <label for="history-success-size" data-i18n="history.page_size">每页</label>
            <select id="history-success-size" class="border rounded px-2 py-1 text-sm">
              <option value="5" selected>5</option>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
            <button id="history-success-prev" onclick="changeSuccessPage(-1)" class="px-2 py-1 rounded border" data-i18n="history.prev">上一页</button>
            <span id="history-success-page" class="text-slate-600"></span>
            <button id="history-success-next" onclick="changeSuccessPage(1)" class="px-2 py-1 rounded border" data-i18n="history.next">下一页</button>
          </div>
        </div>
        <div class="overflow-auto border rounded">
          <table class="w-full text-sm" id="history-success-table">
            <thead class="bg-slate-50">
              <tr class="text-left border-b">
                <th class="py-2 px-2" data-i18n="history.col_task">任务</th>
                <th class="px-2" data-i18n="history.col_scheduled">计划时间</th>
                <th class="px-2" data-i18n="history.col_started">开始时间</th>
                <th class="px-2" data-i18n="history.col_finished">结束时间</th>
                <th class="px-2" data-i18n="history.col_duration">耗时</th>
              </tr>
            </thead>
            <tbody id="history-success-body"></tbody>
          </table>
        </div>
      </div>

      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-rose-700" data-i18n="history.error_title">错误记录</h3>
          <div class="flex items-center gap-2 text-sm">
            <label for="history-error-size" data-i18n="history.page_size">每页</label>
            <select id="history-error-size" class="border rounded px-2 py-1 text-sm">
              <option value="5" selected>5</option>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
            <button id="history-error-prev" onclick="changeErrorPage(-1)" class="px-2 py-1 rounded border" data-i18n="history.prev">上一页</button>
            <span id="history-error-page" class="text-slate-600"></span>
            <button id="history-error-next" onclick="changeErrorPage(1)" class="px-2 py-1 rounded border" data-i18n="history.next">下一页</button>
          </div>
        </div>
        <div class="overflow-auto border rounded">
          <table class="w-full text-sm" id="history-error-table">
            <thead class="bg-slate-50">
              <tr class="text-left border-b">
                <th class="py-2 px-2" data-i18n="history.col_task">任务</th>
                <th class="px-2" data-i18n="history.col_scheduled">计划时间</th>
                <th class="px-2" data-i18n="history.col_started">开始时间</th>
                <th class="px-2" data-i18n="history.col_finished">结束时间</th>
                <th class="px-2" data-i18n="history.col_error">错误信息</th>
              </tr>
            </thead>
            <tbody id="history-error-body"></tbody>
          </table>
        </div>
      </div>
    </section>
  </main>

  <script>
    let currentTasks = [];
    let successRecords = [];
    let errorRecords = [];
    let currentLang = 'zh';
    const successPager = { page: 1, size: 5 };
    const errorPager = { page: 1, size: 5 };

    const I18N = {
      zh: {
        'app.title': 'FasterCron Web Admin',
        'app.subtitle': '任务管理、参数查看和执行记录面板',
        'lang.label': 'Language',
        'create.title': '新增任务',
        'create.expression_placeholder': '表达式，例如 */5 * * * * *',
        'create.module_placeholder': '模块，例如 faster_cron.example_tasks',
        'create.function_placeholder': '函数，例如 heartbeat',
        'create.args_placeholder': 'args JSON 数组，例如 [1, "a"]',
        'create.kwargs_placeholder': 'kwargs JSON 对象，例如 {"env":"dev"}',
        'create.submit': '创建任务',
        'edit.title': '编辑任务',
        'edit.expression_placeholder': 'cron 表达式',
        'edit.args_placeholder': 'args JSON 数组',
        'edit.kwargs_placeholder': 'kwargs JSON 对象',
        'edit.save': '保存修改',
        'edit.reload': '重新加载',
        'history.title': '执行记录',
        'history.refresh': '刷新记录',
        'history.refresh_errors': '刷新错误',
        'history.refresh_all': '刷新记录',
        'history.success_title': '成功记录',
        'history.error_title': '错误记录',
        'history.col_task': '任务',
        'history.col_scheduled': '计划时间',
        'history.col_started': '开始时间',
        'history.col_finished': '结束时间',
        'history.col_duration': '耗时',
        'history.col_error': '错误信息',
        'history.empty': '暂无记录',
        'history.page_size': '每页',
        'history.prev': '上一页',
        'history.next': '下一页',
        'history.page_info': '第 {page} / {total} 页',
        'table.title': '任务列表',
        'table.refresh': '刷新',
        'table.name': '名称',
        'table.expression': '表达式',
        'table.state': '状态',
        'table.params': '参数',
        'table.actions': '操作',
        'common.allow_overlap': '允许重叠执行',
        'common.pause': '暂停',
        'common.resume': '恢复',
        'common.edit': '编辑',
        'common.delete': '删除',
        'common.args': '参数',
        'common.kwargs': '关键字参数',
        'common.select_task': '请选择任务',
        'state.pending': '待调度',
        'state.running': '运行中',
        'state.paused': '已暂停',
        'state.disabled': '已禁用',
        'state.completed': '已完成',
      },
      en: {
        'app.title': 'FasterCron Web Admin',
        'app.subtitle': 'Task management, parameters, and execution history panel',
        'lang.label': '语言',
        'create.title': 'Create Task',
        'create.expression_placeholder': 'Cron expression, e.g. */5 * * * * *',
        'create.module_placeholder': 'Module, e.g. faster_cron.example_tasks',
        'create.function_placeholder': 'Function, e.g. heartbeat',
        'create.args_placeholder': 'args JSON array, e.g. [1, "a"]',
        'create.kwargs_placeholder': 'kwargs JSON object, e.g. {"env":"dev"}',
        'create.submit': 'Create',
        'edit.title': 'Edit Task',
        'edit.expression_placeholder': 'Cron expression',
        'edit.args_placeholder': 'args JSON array',
        'edit.kwargs_placeholder': 'kwargs JSON object',
        'edit.save': 'Save',
        'edit.reload': 'Reload',
        'history.title': 'Execution History',
        'history.refresh': 'Refresh History',
        'history.refresh_errors': 'Refresh Errors',
        'history.refresh_all': 'Refresh Records',
        'history.success_title': 'Success Records',
        'history.error_title': 'Error Records',
        'history.col_task': 'Task',
        'history.col_scheduled': 'Scheduled',
        'history.col_started': 'Started',
        'history.col_finished': 'Finished',
        'history.col_duration': 'Duration',
        'history.col_error': 'Error',
        'history.empty': 'No records',
        'history.page_size': 'Page size',
        'history.prev': 'Prev',
        'history.next': 'Next',
        'history.page_info': 'Page {page} / {total}',
        'table.title': 'Task List',
        'table.refresh': 'Refresh',
        'table.name': 'Name',
        'table.expression': 'Expression',
        'table.state': 'State',
        'table.params': 'Parameters',
        'table.actions': 'Actions',
        'common.allow_overlap': 'Allow overlap',
        'common.pause': 'Pause',
        'common.resume': 'Resume',
        'common.edit': 'Edit',
        'common.delete': 'Delete',
        'common.args': 'Args',
        'common.kwargs': 'Kwargs',
        'common.select_task': 'Please select a task',
        'state.pending': 'Pending',
        'state.running': 'Running',
        'state.paused': 'Paused',
        'state.disabled': 'Disabled',
        'state.completed': 'Completed',
      },
    };

    function pretty(v) { return JSON.stringify(v ?? null); }

    function t(key) {
      return (I18N[currentLang] && I18N[currentLang][key]) || key;
    }

    function normalizeLang(lang) {
      if (lang === 'en' || lang === 'zh') {
        return lang;
      }
      return 'zh';
    }

    function formatState(state) {
      return t(`state.${state || ''}`);
    }

    function pageText(page, total) {
      return t('history.page_info').replace('{page}', String(page)).replace('{total}', String(total));
    }

    function applyI18n() {
      document.documentElement.lang = currentLang;
      document.querySelectorAll('[data-i18n]').forEach((element) => {
        element.textContent = t(element.getAttribute('data-i18n'));
      });
      document.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
        element.setAttribute('placeholder', t(element.getAttribute('data-i18n-placeholder')));
      });
      const langSwitch = document.getElementById('language-switch');
      if (langSwitch) {
        langSwitch.value = currentLang;
      }
      if (currentTasks.length) {
        renderTaskTable();
      }
      renderSuccessHistoryTable();
      renderErrorHistoryTable();
    }

    async function api(url, options) {
      const res = await fetch(url, options);
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed: ${res.status}`);
      }
      return await res.json();
    }

    function parseJsonInput(id, fallback) {
      const raw = document.getElementById(id).value.trim();
      if (!raw) return fallback;
      return JSON.parse(raw);
    }

    async function createTask() {
      try {
        const payload = {
          expression: document.getElementById('task-expression').value.trim(),
          module: document.getElementById('task-module').value.trim(),
          function: document.getElementById('task-function').value.trim(),
          allow_overlap: document.getElementById('task-overlap').checked,
          args: parseJsonInput('task-args', []),
          kwargs: parseJsonInput('task-kwargs', {}),
        };
        await api('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        await loadTasks();
      } catch (err) {
        alert(err.message);
      }
    }

    async function removeTask(name) {
      await api(`/api/tasks/${name}`, { method: 'DELETE' });
      await loadTasks();
    }

    async function pauseTask(name) {
      await api(`/api/tasks/${name}/pause`, { method: 'POST' });
      await loadTasks();
    }

    async function resumeTask(name) {
      await api(`/api/tasks/${name}/resume`, { method: 'POST' });
      await loadTasks();
    }

    function fillEditorBySelection() {
      const selectedName = document.getElementById('edit-task-name').value;
      const first = currentTasks.length ? currentTasks[0].name : '';
      const targetName = selectedName || first;
      const task = currentTasks.find((item) => item.name === targetName);
      if (!task) {
        document.getElementById('edit-task-expression').value = '';
        document.getElementById('edit-task-overlap').checked = false;
        document.getElementById('edit-task-args').value = '[]';
        document.getElementById('edit-task-kwargs').value = '{}';
        return;
      }

      document.getElementById('edit-task-name').value = task.name;
      document.getElementById('edit-task-expression').value = task.expression || '';
      document.getElementById('edit-task-overlap').checked = !!task.allow_overlap;
      document.getElementById('edit-task-args').value = JSON.stringify(task.task_args || [], null, 2);
      document.getElementById('edit-task-kwargs').value = JSON.stringify(task.task_kwargs || {}, null, 2);
    }

    function openEditor(taskName) {
      document.getElementById('edit-task-name').value = taskName;
      fillEditorBySelection();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async function submitTaskEdit() {
      try {
        const name = document.getElementById('edit-task-name').value;
        if (!name) {
          alert(t('common.select_task'));
          return;
        }

        const payload = {
          expression: document.getElementById('edit-task-expression').value.trim(),
          allow_overlap: document.getElementById('edit-task-overlap').checked,
          args: JSON.parse(document.getElementById('edit-task-args').value || '[]'),
          kwargs: JSON.parse(document.getElementById('edit-task-kwargs').value || '{}'),
        };

        await api(`/api/tasks/${name}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        await loadTasks();
      } catch (err) {
        alert(err.message);
      }
    }

    function renderTaskTable() {
      const tbody = document.getElementById('task-table');
      const editorSelect = document.getElementById('edit-task-name');
      tbody.innerHTML = '';
      editorSelect.innerHTML = '';

      for (const task of currentTasks) {
        const opt = document.createElement('option');
        opt.value = task.name;
        opt.textContent = `${task.name} (${formatState(task.state)})`;
        editorSelect.appendChild(opt);

        const tr = document.createElement('tr');
        tr.className = 'border-b align-top';
        tr.innerHTML = `
          <td class="py-2 font-mono text-xs">${task.name}</td>
          <td class="font-mono text-xs">${task.expression || '-'}</td>
          <td>${formatState(task.state)}</td>
          <td class="font-mono text-xs">${t('common.args')}=${pretty(task.task_args)}<br/>${t('common.kwargs')}=${pretty(task.task_kwargs)}</td>
          <td class="space-x-1 py-2">
            <button class="px-2 py-1 bg-slate-700 text-white rounded" onclick="pauseTask('${task.name}')">${t('common.pause')}</button>
            <button class="px-2 py-1 bg-emerald-700 text-white rounded" onclick="resumeTask('${task.name}')">${t('common.resume')}</button>
            <button class="px-2 py-1 bg-indigo-600 text-white rounded" onclick='openEditor(${JSON.stringify(task.name)})'>${t('common.edit')}</button>
            <button class="px-2 py-1 bg-rose-700 text-white rounded" onclick="removeTask('${task.name}')">${t('common.delete')}</button>
          </td>
        `;
        tbody.appendChild(tr);
      }

      fillEditorBySelection();
    }

    function parseRecordTime(record) {
      return Date.parse(record.started_at || record.scheduled_at || record.finished_at || 0) || 0;
    }

    function formatDateTime(value) {
      if (!value) {
        return '-';
      }
      const dt = new Date(value);
      if (Number.isNaN(dt.getTime())) {
        return value;
      }
      return dt.toLocaleString();
    }

    function formatDuration(record) {
      if (record.elapsed_ms !== null && record.elapsed_ms !== undefined) {
        return `${Math.round(record.elapsed_ms)} ms`;
      }
      return '-';
    }

    function renderHistoryTable(bodyId, rows, columns) {
      const tbody = document.getElementById(bodyId);
      tbody.innerHTML = '';

      if (!rows.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="${columns.length}" class="px-2 py-2 text-slate-500">${t('history.empty')}</td>`;
        tbody.appendChild(tr);
        return;
      }

      for (const row of rows) {
        const tr = document.createElement('tr');
        tr.className = 'border-b align-top';
        tr.innerHTML = columns.map((column) => `<td class="px-2 py-2">${column(row)}</td>`).join('');
        tbody.appendChild(tr);
      }
    }

    function getPagedRows(rows, pager) {
      const totalPages = Math.max(1, Math.ceil(rows.length / pager.size));
      if (pager.page > totalPages) {
        pager.page = totalPages;
      }
      const start = (pager.page - 1) * pager.size;
      return { rows: rows.slice(start, start + pager.size), totalPages };
    }

    function updatePagerControls(prefix, pager, totalPages) {
      const pageLabel = document.getElementById(`${prefix}-page`);
      const prevBtn = document.getElementById(`${prefix}-prev`);
      const nextBtn = document.getElementById(`${prefix}-next`);
      if (pageLabel) {
        pageLabel.textContent = pageText(pager.page, totalPages);
      }
      if (prevBtn) {
        prevBtn.disabled = pager.page <= 1;
      }
      if (nextBtn) {
        nextBtn.disabled = pager.page >= totalPages;
      }
    }

    function renderSuccessHistoryTable() {
      const paged = getPagedRows(successRecords, successPager);
      renderHistoryTable(
        'history-success-body',
        paged.rows,
        [
          (r) => r.task_name || '-',
          (r) => formatDateTime(r.scheduled_at),
          (r) => formatDateTime(r.started_at),
          (r) => formatDateTime(r.finished_at),
          (r) => formatDuration(r),
        ],
      );
      updatePagerControls('history-success', successPager, paged.totalPages);
    }

    function renderErrorHistoryTable() {
      const paged = getPagedRows(errorRecords, errorPager);
      renderHistoryTable(
        'history-error-body',
        paged.rows,
        [
          (r) => r.task_name || '-',
          (r) => formatDateTime(r.scheduled_at),
          (r) => formatDateTime(r.started_at),
          (r) => formatDateTime(r.finished_at),
          (r) => r.error_message || '-',
        ],
      );
      updatePagerControls('history-error', errorPager, paged.totalPages);
    }

    function changeSuccessPage(offset) {
      successPager.page = Math.max(1, successPager.page + offset);
      renderSuccessHistoryTable();
    }

    function changeErrorPage(offset) {
      errorPager.page = Math.max(1, errorPager.page + offset);
      renderErrorHistoryTable();
    }

    async function loadTasks() {
      const data = await api('/api/tasks');
      currentTasks = data.tasks || [];
      renderTaskTable();
    }

    async function loadHistory() {
      const data = await api('/api/history?limit=50');
      successRecords = (data.records || []).slice().sort((a, b) => parseRecordTime(b) - parseRecordTime(a));
      successPager.page = 1;
      renderSuccessHistoryTable();
    }

    async function loadErrors() {
      const data = await api('/api/errors?limit=50');
      errorRecords = (data.records || []).slice().sort((a, b) => parseRecordTime(b) - parseRecordTime(a));
      errorPager.page = 1;
      renderErrorHistoryTable();
    }

    async function refreshExecutionTables() {
      await Promise.all([loadHistory(), loadErrors()]);
    }

    document.getElementById('edit-task-name').addEventListener('change', fillEditorBySelection);
    document.getElementById('history-success-size').addEventListener('change', (event) => {
      successPager.size = Math.max(1, Number(event.target.value) || 5);
      successPager.page = 1;
      renderSuccessHistoryTable();
    });
    document.getElementById('history-error-size').addEventListener('change', (event) => {
      errorPager.size = Math.max(1, Number(event.target.value) || 5);
      errorPager.page = 1;
      renderErrorHistoryTable();
    });
    document.getElementById('language-switch').addEventListener('change', (event) => {
      currentLang = normalizeLang(event.target.value);
      applyI18n();
    });

    currentLang = normalizeLang((navigator.language || '').toLowerCase().startsWith('en') ? 'en' : 'zh');
    applyI18n();
    loadTasks();
    refreshExecutionTables();
  </script>
</body>
</html>"""

