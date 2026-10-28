# 桌面智能体 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个能用自然语言驱动、会验证结果、能沉淀技能、可远程下任务的 Windows 桌面智能体。

**Architecture:** 五层结构——感知（截图/控件树）、决策（Planner/Operator/Verifier/Recoverer 四角色状态机）、执行（鼠标键盘/程序/文件）、安全（风险分级与预算）、记忆（轨迹/技能库 RAG/SOP 知识库 RAG）。核心循环不依赖网页与远程层，两者均为可插拔旁路。

**Tech Stack:** Python 3.10+、Ollama HTTP API（`gemma4:31b-cloud` 主模型 / `deepseek-r1:1.5b` 验证器 / `bge-m3` 向量）、mss、pyautogui、pynput、uiautomation、FastAPI + WebSocket、SQLite + numpy、pytest。

**Spec:** `docs/superpowers/specs/2026-10-28-desktop-agent-design.md`

## Global Constraints

- Python 3.10 及以上；全部依赖可 `pip install -r requirements.txt` 安装。
- Ollama 地址固定 `http://127.0.0.1:11434`。
- 主模型 `gemma4:31b-cloud`，验证器 `deepseek-r1:1.5b`，向量模型 `bge-m3`。
- 预算默认值：最多 30 步、600 秒、120 次模型调用。
- 所有运行时产物写入 `runs/<timestamp>/`，沙箱目录为 `runs/_sandbox/`。
- 破坏性动作必须在执行前确认；确认逻辑不得写在动作之后。
- 视觉模型返回归一化坐标（0–1000），由本地换算为绝对像素。
- 中文界面与中文提示词；日志与报告用中文。
- 每个 Task 结束必须提交一次，提交信息用 `feat:` / `test:` / `chore:` 前缀。

## Review Focus

1. **DPI 缩放导致点击偏移**：系统缩放 125%/150% 时截图尺寸与屏幕坐标不一致，点击必须落在视觉目标上。
2. **模态对话框阻塞**：保存/覆盖确认框弹出后，流程不能误判为完成。
3. **控件被遮挡或跨屏**：控件树能找到但点击无效时，应回退视觉并重新验证。
4. **模型超时或断网**：单次调用失败不能终止整个任务，应重试并最终降级或明确报错。
5. **破坏性动作先执行后确认**：确认门必须在执行之前拦截，测试要能证明文件未被修改。

---

## 文件结构

```
desktop_agent/
  __init__.py
  __main__.py            命令行入口
  config.py              配置与默认值
  llm.py                 模型调用（chat / embed / health）
  core/
    state.py             任务状态
    planner.py           规划
    verifier.py          验证
    loop.py              主循环
  orchestration/
    roles.py             四角色提示词与输出契约
    router.py            确定性状态机
  perception/
    screen.py            截图、活动窗口、光标
    uitree.py            控件树定位
  actions/
    registry.py          工具注册表与执行入口
    mouse.py             鼠标动作
    keyboard.py          键盘动作
    apps.py              程序启动与切换
    files.py             文件与系统信息工具
  safety/
    guard.py             风险分级与确认
    budget.py            步数/时长/调用上限
  memory/
    trace.py             轨迹落盘与读取
    skills.py            技能库 RAG
    knowledge.py         SOP 知识库 RAG
    recorder.py          人手示范录制
  ui/
    server.py            本地网页
    static/index.html
  remote/
    server.py            被控端
    client.py            控制端
eval/
  tasks.json
  run_eval.py
tests/
```

---

### Task 1: 工程骨架与模型联通

**Files:**
- Create: `requirements.txt`, `desktop_agent/__init__.py`, `desktop_agent/config.py`, `desktop_agent/llm.py`, `tests/test_config.py`, `tests/test_llm.py`

**Interfaces:**
- Produces: `Settings(ollama_base, model_main, model_verifier, model_embed, max_steps, max_seconds, max_llm_calls, runs_dir, sandbox_dir)`；`load_settings() -> Settings`；`chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None, timeout: int = 120) -> dict`；`embed(texts: list[str]) -> list[list[float]]`；`health() -> dict`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
def test_defaults_match_spec():
    s = load_settings()
    assert s.ollama_base == "http://127.0.0.1:11434"
    assert s.model_main == "gemma4:31b-cloud"
    assert (s.max_steps, s.max_seconds, s.max_llm_calls) == (30, 600, 120)
```

```python
# tests/test_llm.py
def test_health_reports_model_and_capabilities():
    h = health()
    assert h["ok"] is True
    assert "tools" in h["capabilities"] and "vision" in h["capabilities"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_config.py tests/test_llm.py -v`
Expected: FAIL，`ModuleNotFoundError: desktop_agent`

- [ ] **Step 3: 实现**

`config.py` 用 `dataclass` + 环境变量覆盖（`DA_MODEL_MAIN` 等）。`llm.py` 用 `requests` 封装
`/api/chat`、`/api/embed`、`/api/show`；`health()` 返回 `{"ok", "model", "capabilities"}`，
异常时 `ok=False` 并带 `error` 字符串，不抛异常。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_config.py tests/test_llm.py -v`
Expected: PASS（需要 Ollama 在线）

- [ ] **Step 5: 提交**

```bash
git add requirements.txt desktop_agent tests && git commit -m "feat: 工程骨架与模型联通"
```

---

### Task 2: 截图感知与 DPI 换算

**Files:**
- Create: `desktop_agent/perception/screen.py`, `tests/test_screen.py`

**Interfaces:**
- Produces: `ScreenShot(path: Path, width: int, height: int, scale: float, active_window: str, cursor: tuple[int, int])`；`capture(out_dir: Path) -> ScreenShot`；`to_absolute(nx: int, ny: int, shot: ScreenShot) -> tuple[int, int]`；`set_backend(fn)` 供测试注入

- [ ] **Step 1: 写失败测试**

```python
def test_normalized_to_absolute_with_dpi_scale(tmp_path):
    shot = ScreenShot(path=tmp_path/"a.png", width=1920, height=1080, scale=1.25,
                      active_window="记事本", cursor=(10, 10))
    assert to_absolute(500, 500, shot) == (1200, 675)
```

```python
def test_capture_writes_png(tmp_path):
    set_backend(lambda p: (p.write_bytes(b"\x89PNG"), 800, 600, 1.0, "测试", (0, 0)))
    shot = capture(tmp_path)
    assert shot.path.exists() and shot.width == 800
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_screen.py -v`
Expected: FAIL，`ImportError`

- [ ] **Step 3: 实现**

`mss` 抓取主显示器，`png` 落盘；`scale` 取自 `ctypes.windll.shcore.GetScaleFactorForMonitor`
（失败回退 1.0）。`to_absolute` 按 `round(nx/1000*width*scale)` 计算。`set_backend` 让测试
不依赖真实桌面。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_screen.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/perception tests/test_screen.py
git commit -m "feat: 截图感知与 DPI 坐标换算"
```

---

### Task 3: 任务状态与预算

**Files:**
- Create: `desktop_agent/core/state.py`, `desktop_agent/safety/budget.py`, `tests/test_budget.py`

**Interfaces:**
- Produces: `Budget(max_steps, max_seconds, max_llm_calls)`，方法 `spend_step() -> None`、`spend_call() -> None`、`can_continue() -> bool`、`reason() -> str | None`；`TaskState(task: str, plan: list, step_idx: int, failures: int, status: str)`

- [ ] **Step 1: 写失败测试**

```python
def test_budget_blocks_after_max_steps():
    b = Budget(max_steps=2, max_seconds=600, max_llm_calls=10)
    b.spend_step(); b.spend_step()
    assert b.can_continue() is False
    assert b.reason() == "超过最大步数"

def test_budget_counts_time():
    b = Budget(max_steps=10, max_seconds=0.05, max_llm_calls=10)
    time.sleep(0.06)
    assert b.can_continue() is False and "超时" in b.reason()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_budget.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`Budget` 记录 `started_at`、步数与调用数；`can_continue` 依次检查步数、时长、调用次数，
`reason()` 返回第一个触顶条件的固定中文文案。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_budget.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/core/state.py desktop_agent/safety/budget.py tests/test_budget.py
git commit -m "feat: 任务状态与预算上限"
```

---

### Task 4: 轨迹落盘与读取

**Files:**
- Create: `desktop_agent/memory/trace.py`, `tests/test_trace.py`

**Interfaces:**
- Produces: `StepRecord(idx, tool, args, risk, before, after, verdict, reason, seconds)`；`TraceWriter(run_dir: Path)` 方法 `write_task(meta: dict)`、`write_step(step: StepRecord)`、`finalize(status: str)`；`load_run(run_dir: Path) -> dict`

- [ ] **Step 1: 写失败测试**

```python
def test_trace_roundtrip(tmp_path):
    w = TraceWriter(tmp_path)
    w.write_task({"task": "打开记事本"})
    w.write_step(StepRecord(1, "open_app", {"name": "notepad"}, "ui",
                            "a.png", "b.png", "continue", "已打开", 1.2))
    w.finalize("success")
    data = load_run(tmp_path)
    assert data["task"]["task"] == "打开记事本"
    assert data["steps"][0]["tool"] == "open_app"
    assert data["status"] == "success"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_trace.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`write_task` 写 `task.json`，`write_step` 追加到内存列表并在 `finalize` 时整体写 `trace.json`
（含 `status`、`steps`）。`load_run` 读取两者，文件缺失时返回空结构而不是抛异常。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_trace.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/memory/trace.py tests/test_trace.py
git commit -m "feat: 轨迹落盘与读取"
```

---

### Task 5: 只读工具与注册表

**Files:**
- Create: `desktop_agent/actions/files.py`, `desktop_agent/actions/registry.py`, `tests/test_registry.py`, `tests/test_files_tools.py`

**Interfaces:**
- Produces: `get_disk_usage(drive: str) -> dict`、`check_port(port: int) -> dict`、`get_system_info() -> dict`、`list_dir(path: str) -> dict`、`read_file(path: str, max_chars: int = 2000) -> dict`、`write_file(path: str, content: str) -> dict`；`TOOLS: list[dict]`；`execute(name: str, args: dict) -> dict`；`tool_names() -> list[str]`

- [ ] **Step 1: 写失败测试**

```python
def test_every_schema_has_matching_implementation():
    assert set(tool_names()) == {t["function"]["name"] for t in TOOLS}

def test_unknown_tool_returns_error_not_exception():
    assert "error" in execute("nope", {})

def test_write_then_read_roundtrip(tmp_path):
    p = str(tmp_path/"a.txt")
    assert execute("write_file", {"path": p, "content": "你好"})["ok"] is True
    assert execute("read_file", {"path": p})["content"] == "你好"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_registry.py tests/test_files_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

沿用 `agent.py` 里已验证的实现（盘符容错、netstat 判断、编码容错），补 `write_file`：
写前检查父目录存在，禁止写到 `C:\Windows` 等系统目录，返回 `{"ok": True, "path": ...}`。
`registry.execute` 捕获所有异常并返回 `{"error": str}`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_registry.py tests/test_files_tools.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/actions tests/test_registry.py tests/test_files_tools.py
git commit -m "feat: 只读工具与写入工具注册表"
```

---

### Task 6: 输入动作与风险确认门

**Files:**
- Create: `desktop_agent/actions/mouse.py`, `desktop_agent/actions/keyboard.py`, `desktop_agent/actions/apps.py`, `desktop_agent/safety/guard.py`, `tests/test_guard.py`, `tests/test_confirm_gate.py`

**Interfaces:**
- Produces: `click(x: int, y: int) -> dict`、`move(x: int, y: int) -> dict`、`type_text(text: str) -> dict`、`press_keys(keys: list[str]) -> dict`、`open_app(name: str) -> dict`；`classify(tool: str, args: dict) -> Risk`（`"read" | "ui" | "destructive"`）；`require_confirm(tool: str, args: dict, confirm_fn=...) -> bool`

- [ ] **Step 1: 写失败测试**

```python
def test_destructive_tool_blocked_before_action(tmp_path):
    target = tmp_path/"keep.txt"; target.write_text("重要")
    asked = []
    ok = require_confirm("write_file", {"path": str(target), "content": ""},
                         confirm_fn=lambda q: (asked.append(q), False)[1])
    assert ok is False and asked and target.read_text() == "重要"

def test_ui_actions_do_not_require_confirm():
    assert require_confirm("type_text", {"text": "hi"}, confirm_fn=lambda q: True) is True
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_guard.py tests/test_confirm_gate.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`classify` 规则：`read_* / list_dir / get_* / check_port / screenshot` 为 read；`click / move /
type_text / press_keys / open_app` 为 ui；`write_file` 覆盖已存在文件、`delete_*`、`shutdown`
为 destructive。`require_confirm` 在执行前调用 `confirm_fn`，返回 False 时调用方必须放弃动作。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_guard.py tests/test_confirm_gate.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/actions desktop_agent/safety/guard.py tests/test_guard.py tests/test_confirm_gate.py
git commit -m "feat: 输入动作与破坏性动作确认门"
```

---

### Task 7: 控件树定位与回退

**Files:**
- Create: `desktop_agent/perception/uitree.py`, `tests/test_uitree.py`

**Interfaces:**
- Produces: `UIElement(name, control_type, rect, automation_id)`；`find_elements(name_hint: str, window_title: str | None = None, limit: int = 20) -> list[UIElement]`；`click_element(element: UIElement) -> bool`；`set_backend(fn)`

- [ ] **Step 1: 写失败测试**

```python
def test_find_returns_matching_control():
    set_backend(lambda hint, title, limit: [
        UIElement("保存", "Button", (10, 20, 60, 30), "btnSave"),
        UIElement("取消", "Button", (80, 20, 60, 30), "btnCancel"),
    ])
    got = find_elements("保存")
    assert len(got) == 1 and got[0].automation_id == "btnSave"

def test_click_element_returns_false_when_offscreen():
    assert click_element(UIElement("X", "Button", (-9999, -9999, 10, 10), "x")) is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_uitree.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

默认后端用 `uiautomation` 遍历桌面与指定窗口子树，按 `Name`/`AutomationId` 模糊匹配；
元素矩形完全落在屏幕外时 `click_element` 返回 False（触发上层回退视觉）。后端可注入，
测试不依赖真实界面。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_uitree.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/perception/uitree.py tests/test_uitree.py
git commit -m "feat: 控件树定位与离屏回退"
```

---

### Task 8: 规划器

**Files:**
- Create: `desktop_agent/orchestration/roles.py`, `desktop_agent/core/planner.py`, `tests/test_planner.py`

**Interfaces:**
- Produces: `PlanStep(id: int, intent: str, expected: str, tool_hint: str | None)`；`make_plan(task: str, skills: list[dict], sop: list[dict]) -> list[PlanStep]`；`PLANNER_PROMPT: str`

- [ ] **Step 1: 写失败测试**

```python
def test_plan_parses_structured_json(monkeypatch):
    monkeypatch.setattr(planner, "chat", lambda *a, **k: {"content":
        '{"steps":[{"intent":"打开记事本","expected":"记事本窗口出现","tool_hint":"open_app"}]}'})
    steps = make_plan("打开记事本", [], [])
    assert steps[0].tool_hint == "open_app" and steps[0].expected

def test_plan_rejects_empty(monkeypatch):
    monkeypatch.setattr(planner, "chat", lambda *a, **k: {"content": '{"steps":[]}'})
    with pytest.raises(ValueError):
        make_plan("做点事", [], [])
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_planner.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`PLANNER_PROMPT` 要求只输出 JSON（`{"steps":[{intent, expected, tool_hint}]}`），并注入
技能与 SOP 摘要。解析失败时重试一次，仍失败抛 `ValueError`。步骤上限 15。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_planner.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/orchestration/roles.py desktop_agent/core/planner.py tests/test_planner.py
git commit -m "feat: 规划器与结构化计划解析"
```

---

### Task 9: 验证器与自查证据

**Files:**
- Create: `desktop_agent/core/verifier.py`, `tests/test_verifier.py`

**Interfaces:**
- Produces: `Verdict(action: str, reason: str, evidence: str)`（`action ∈ {"continue","retry","replan"}`）；`verify(expected: str, before: Path, after: Path) -> Verdict`；`VERIFIER_PROMPT: str`

- [ ] **Step 1: 写失败测试**

```python
def test_missing_after_image_forces_retry(tmp_path):
    v = verify("文件已保存", tmp_path/"a.png", tmp_path/"missing.png")
    assert v.action == "retry" and "截图" in v.reason

def test_verdict_rejects_unknown_action(monkeypatch):
    monkeypatch.setattr(verifier, "chat", lambda *a, **k: {"content":
        '{"action":"looks_good","reason":"ok","evidence":"x"}'})
    v = verify("x", tmp_path/"a.png", tmp_path/"b.png")
    assert v.action == "retry"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_verifier.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

验证器只接收 `expected` 与两张截图，不接收 Operator 的文字解释（上下文隔离）。截图缺失直接
返回 retry；模型返回非法 action 时降级为 retry。使用 `settings.model_verifier`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_verifier.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/core/verifier.py tests/test_verifier.py
git commit -m "feat: 独立验证器与证据判断"
```

---

### Task 10: 主循环

**Files:**
- Create: `desktop_agent/core/loop.py`, `tests/test_loop.py`

**Interfaces:**
- Produces: `TaskResult(status: str, steps: int, seconds: float, answer: str, run_dir: Path)`；`run_task(task: str, confirm_fn=..., settings=None, dry_run=False) -> TaskResult`

- [ ] **Step 1: 写失败测试**

```python
def test_loop_stops_at_max_steps(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, "make_plan", lambda *a: [PlanStep(1, "x", "y", None)] * 3)
    monkeypatch.setattr(loop, "verify", lambda *a: Verdict("retry", "没成", ""))
    res = run_task("做点事", confirm_fn=lambda q: True, dry_run=True)
    assert res.status in {"blocked", "failed"} and res.steps >= 3

def test_destructive_action_not_executed_when_declined(monkeypatch, tmp_path):
    target = tmp_path/"keep.txt"
    monkeypatch.setattr(loop, "make_plan", lambda *a: [
        PlanStep(1, "清空文件", "文件为空", "write_file")])
    monkeypatch.setattr(loop, "execute", lambda n, a: {"ok": True})
    res = run_task("清空", confirm_fn=lambda q: False, dry_run=False)
    assert res.status == "blocked" and not target.exists()

def test_verifier_timeout_is_retried_not_fatal(monkeypatch):
    calls = {"n": 0}
    def flaky(*a, **k):
        calls["n"] += 1
        raise TimeoutError("模型超时")
    monkeypatch.setattr(loop, "verify", flaky)
    res = run_task("做点事", confirm_fn=lambda q: True, dry_run=True)
    assert calls["n"] >= 2 and res.status != "success"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_loop.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

循环顺序固定：预算检查 → 规划（首轮或重规划）→ 执行一步（先过确认门）→ 截图 → 验证 →
写轨迹。`dry_run=True` 时动作只记录不执行，供测试与演示彩排。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_loop.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/core/loop.py tests/test_loop.py
git commit -m "feat: 规划执行验证主循环"
```

---

### Task 11: 多智能体路由

**Files:**
- Create: `desktop_agent/orchestration/router.py`, `tests/test_router.py`

**Interfaces:**
- Produces: `Route(action: str, next_role: str)`；`decide(verdict: Verdict, failures: int, max_failures: int = 3) -> Route`；`role_context(role: str, history: list[dict]) -> list[dict]`（Verifier 只保留预期与截图，剔除 Operator 解释）

- [ ] **Step 1: 写失败测试**

```python
def test_three_failures_trigger_recoverer():
    r = decide(Verdict("retry", "没成", ""), failures=3)
    assert r.next_role == "recoverer"

def test_verifier_context_excludes_operator_reasoning():
    ctx = role_context("verifier", [{"role":"operator","content":"我点了保存"},
                                   {"role":"observation","content":"dialog_open"}])
    assert all(m["role"] != "operator" for m in ctx)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_router.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

纯函数状态机：`continue → operator`、`retry → operator`、`replan → planner`、
`failures >= max_failures → recoverer`。`role_context` 按角色白名单过滤消息类型。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_router.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/orchestration/router.py tests/test_router.py
git commit -m "feat: 四角色确定性路由与上下文隔离"
```

---

### Task 12: 技能库 RAG

**Files:**
- Create: `desktop_agent/memory/skills.py`, `tests/test_skills.py`

**Interfaces:**
- Produces: `Skill(id, task, precondition, tools, success_count, avg_steps, vector)`；`SkillStore(root: Path)` 方法 `add(skill) -> str`、`search(query: str, k: int = 3) -> list[Skill]`、`record_use(id: str, steps: int) -> None`、`stats() -> dict`

- [ ] **Step 1: 写失败测试**

```python
def test_skill_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    store = SkillStore(tmp_path)
    sid = store.add(Skill("", "打开记事本并保存", "无", ["open_app", "type_text"], 0, 3, []))
    hits = store.search("打开记事本")
    assert hits[0].id == sid

def test_record_use_updates_average(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    store = SkillStore(tmp_path)
    sid = store.add(Skill("", "保存文件", "无", ["write_file"], 0, 2, []))
    store.record_use(sid, steps=4)
    store.record_use(sid, steps=6)
    assert store.stats()["avg_steps"] == 4.0
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_skills.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

SQLite 存 `id/task/precondition/tools_json/success_count/total_steps/vector`。检索：embed 查询
后与库内向量做余弦相似度，取 top-k 并对低于 0.5 的结果丢弃。`record_use` 累加使用次数与总步数。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_skills.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/memory/skills.py tests/test_skills.py
git commit -m "feat: 技能库向量检索与使用统计"
```

---

### Task 13: SOP 知识库 RAG

**Files:**
- Create: `desktop_agent/memory/knowledge.py`, `tests/test_knowledge.py`

**Interfaces:**
- Produces: `Chunk(id, text, source, heading, vector, keywords)`；`KnowledgeBase(root: Path)` 方法 `ingest(path: Path) -> int`、`search(query: str, k: int = 5) -> list[Chunk]`、`stats() -> dict`

- [ ] **Step 1: 写失败测试**

```python
def test_ingest_markdown_splits_by_heading(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    doc = tmp_path/"sop.md"; doc.write_text("# 报销\n先填单。\n## 审批\n找主管。", encoding="utf-8")
    kb = KnowledgeBase(tmp_path/"idx"); assert kb.ingest(doc) >= 2
    assert kb.search("报销要做什么")[0].heading

def test_hybrid_scoring_prefers_keyword_overlap(tmp_path, monkeypatch):
    vectors = {"报销": [1.0, 0.0], "审批": [0.0, 1.0], "报销要做什么": [1.0, 0.0]}
    monkeypatch.setattr(knowledge, "embed", lambda texts: [vectors[t] for t in texts])
    doc = tmp_path/"sop.md"
    doc.write_text("# 报销\n填单。\n## 审批\n找主管。", encoding="utf-8")
    kb = KnowledgeBase(tmp_path/"idx")
    kb.ingest(doc)
    assert "报销" in kb.search("报销要做什么")[0].text
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

切分：Markdown 按标题层级，纯文本按空行分段，单段上限 500 字。索引存 SQLite；检索分数 =
`0.7 * 余弦 + 0.3 * 关键词重叠率`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_knowledge.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/memory/knowledge.py tests/test_knowledge.py
git commit -m "feat: SOP 知识库切分与混合检索"
```

---

### Task 14: 本地网页界面

**Files:**
- Create: `desktop_agent/ui/server.py`, `desktop_agent/ui/static/index.html`, `tests/test_ui.py`

**Interfaces:**
- Produces: `create_app(state_feed) -> FastAPI`；WebSocket `/ws` 推送 `{"type":"screen"|"log"|"done","payload":...}`；POST `/api/task` 接收 `{"task": str}`；POST `/api/stop`

- [ ] **Step 1: 写失败测试**

```python
def test_task_endpoint_requires_task():
    client = TestClient(create_app(lambda: None))
    assert client.post("/api/task", json={}).status_code == 422
    assert client.get("/").status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ui.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

FastAPI 托管 `index.html`（左屏右日志），`/ws` 广播截图与日志事件，`/api/stop` 置位急停标志。
界面只读状态，不直接驱动动作。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_ui.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/ui tests/test_ui.py
git commit -m "feat: 本地实时界面与任务入口"
```

---

### Task 15: 远程被控端与控制端

**Files:**
- Create: `desktop_agent/remote/server.py`, `desktop_agent/remote/client.py`, `tests/test_remote.py`

**Interfaces:**
- Produces: `create_remote_app(run_task_fn, token: str) -> FastAPI`；WebSocket `/agent` 接收 `{"task": str}`，回传 `{"type":"frame"|"status","payload":...}`；`submit_task(url: str, token: str, task: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
def test_rejects_missing_or_wrong_token():
    app = create_remote_app(lambda t: None, "secret")
    client = TestClient(app)
    assert client.post("/api/task", json={"task":"x"}).status_code == 401
    assert client.post("/api/task", json={"task":"x"},
                       headers={"X-Agent-Token":"secret"}).status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_remote.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

被控端校验一次性令牌，接收任务后在线程中调用 `run_task_fn`，通过 WebSocket 推送状态；
控制端提供 `submit_task` 与订阅帧的简易函数。核心循环不 import 该模块。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_remote.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/remote tests/test_remote.py
git commit -m "feat: 远程任务下发与画面回传"
```

---

### Task 16: 示范学习

**Files:**
- Create: `desktop_agent/memory/recorder.py`, `tests/test_recorder.py`

**Interfaces:**
- Produces: `record_session(seconds: int, out: Path) -> Path`（记录键鼠事件为 JSON）；`events_to_skill(events: list[dict]) -> Skill`；`replay_events(events: list[dict], dry_run=True) -> list[dict]`

- [ ] **Step 1: 写失败测试**

```python
def test_events_become_skill_with_tool_sequence(tmp_path):
    events = [{"type":"key","key":"ctrl+n"}, {"type":"text","text":"你好"},
              {"type":"key","key":"ctrl+s"}]
    skill = events_to_skill(events)
    assert skill.tools == ["press_keys", "type_text", "press_keys"]

def test_replay_dry_run_does_not_touch_desktop(monkeypatch):
    called = []
    monkeypatch.setattr(recorder, "execute", lambda n, a: called.append(n) or {})
    replay_events([{"type":"text","text":"x"}], dry_run=True)
    assert called == []
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_recorder.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

用 `pynput` 监听键盘与鼠标，合并连续输入为单个 `text` 事件；`events_to_skill` 把事件序列
映射成工具名序列并生成触发描述；`replay_events` 在 `dry_run` 时只返回计划动作。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_recorder.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add desktop_agent/memory/recorder.py tests/test_recorder.py
git commit -m "feat: 人手示范录制与技能抽象"
```

---

### Task 17: 评估与四组对照

**Files:**
- Create: `eval/tasks.json`, `eval/run_eval.py`, `tests/test_eval.py`

**Interfaces:**
- Produces: `load_tasks(path: Path) -> list[dict]`；`run_suite(config: str) -> dict`；`summarize(results: list[dict]) -> dict`（含 `success_rate`、`avg_steps`、`avg_seconds`、`false_complete_rate`）

- [ ] **Step 1: 写失败测试**

```python
def test_summary_computes_rates():
    rows = [{"ok": True, "steps": 4, "seconds": 10, "false_complete": False},
            {"ok": False, "steps": 8, "seconds": 20, "false_complete": True}]
    s = summarize(rows)
    assert s["success_rate"] == 0.5 and s["false_complete_rate"] == 0.5
    assert s["avg_steps"] == 6
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_eval.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`tasks.json` 放 10 条任务（含验证陷阱）。`run_eval.py` 支持 `--config vision|hybrid|rag|multi`
四组，逐条调用 `run_task`，结果写 `eval/results/<config>-<timestamp>.json`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_eval.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add eval tests/test_eval.py
git commit -m "feat: 评估脚本与四组对照统计"
```

---

### Task 18: 交付文档与演示脚本

**Files:**
- Create: `README.md`, `docs/演示脚本.md`, `docs/架构说明.md`

**Interfaces:**
- Consumes: 前 17 个 Task 的模块与命令
- Produces: 可供评审直接照做的三份文档

- [ ] **Step 1: 写 README 的快速开始段**

必含四行可复制命令：安装依赖、检查模型、跑一次任务、启动网页。命令必须与
`desktop_agent/__main__.py` 实际参数一致。

- [ ] **Step 2: 逐条验证 README 命令**

Run: 按 README 从干净 shell 逐行执行
Expected: 每行返回成功，第一次任务能产出 `runs/<timestamp>/trace.json`

- [ ] **Step 3: 写演示脚本**

六个场景各写：开场一句话、预期动作、成功判据、翻车时的应对。验证陷阱场景单独写明
如何人为制造"未真正完成"的状态。

- [ ] **Step 4: 写架构说明**

含五层结构图、主循环时序、两个 RAG 的区别、四角色职责与 Verifier 上下文隔离。

- [ ] **Step 5: 提交**

```bash
git add README.md docs && git commit -m "docs: 交付文档与六场景演示脚本"
```

---

## 执行说明

本计划共 18 个 Task，顺序即依赖顺序：Task 1–7 构成可用的单步执行器，Task 8–11 构成完整
智能体循环，Task 12–13 接入两个 RAG，Task 14–17 补界面、远程、示范与评估，Task 18 收口交付物。

每个 Task 独立跑绿后再进入下一个；Task 10 完成后即可用终端跑通第一个演示场景，
后续 Task 均可在已有闭环上增量验证。
