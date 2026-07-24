# Crop Cycle Setup Task Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让“创建西瓜 8424 茬口，约 20 亩”这类多层写入意图通过 `agent_task_states` 收集缺失信息，并在信息足够后生成模板、茬口、种植单元的待确认计划。

**Architecture:** 第一版采用保守规则 planner，而不是直接做通用 LLM planner。`agent_task_states` 保存跨轮 crop cycle setup 草稿；`tool_pending` 在写确认前把单个茬口创建工具调用升格为两步或三步 pending plan；pending plan executor 解析 `$from_step`，把创建茬口输出的 `cycle_id` 传给后续种植单元步骤。

**Tech Stack:** FastAPI backend、SQLAlchemy、LangChain ToolMessage、SkillResult、pytest、ruff。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `backend/app/application/chat/task_state_updater.py` | 识别 `crop_cycle_setup` 任务，写入/更新 `agent_task_states`，处理缺种植单元名称的多轮补齐。 |
| `backend/app/agent/runtime/crop_cycle_setup_planner.py` | 新增纯函数 planner，从用户输入、active task state 和 tool calls 生成 task state 更新建议与 pending plan steps。 |
| `backend/app/agent/runtime/tool_pending.py` | 调用 crop setup planner，并把 planner 输出存为 pending plan。 |
| `backend/app/agent/executor/pending_actions.py` | 在执行 pending plan 步骤前解析 `$from_step` 绑定。 |
| `backend/app/infra/pending_action_presenter.py` | 展示种植单元创建步骤与面积语义提示。 |
| `backend/tests/agent/test_task_state_flow.py` | 覆盖缺种植单元名称、多轮补齐和 side query 不覆盖。 |
| `backend/tests/agent/test_plan_draft_pending_execution.py` | 覆盖两步和三步 pending plan 生成。 |
| `backend/tests/agent/test_pending_plan_executor.py` | 覆盖 `$from_step` 输出绑定和上游失败暂停。 |

## Task 1: Crop Setup TaskState

**Files:**
- Modify: `backend/app/application/chat/task_state_updater.py`
- Test: `backend/tests/agent/test_task_state_flow.py`

- [ ] **Step 1: Add failing tests**

Add tests that prove:

```python
async def test_task_state_writes_crop_cycle_setup_when_unit_name_missing(db_session):
    result = await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="帮我创建西瓜8424茬口，再新增20亩地",
            assistant_reply="还需要补充：种植单元名称。",
        ),
    )

    task = AgentTaskStateStore(db_session).get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
    )

    assert result.action == "created"
    assert task is not None
    assert task.task_type == "crop_cycle_setup"
    assert task.status == TaskStateStatus.WAITING_USER.value
    assert task.entities_json["crop_name"] == "西瓜"
    assert task.entities_json["variety"] == "8424"
    assert task.entities_json["area_mu"] == 20
    assert task.missing_information_json == ["种植单元名称"]
```

```python
async def test_task_state_crop_cycle_setup_accepts_unit_name_followup(db_session):
    store = AgentTaskStateStore(db_session)
    store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="crop_cycle_setup",
        goal="帮我创建西瓜8424茬口，再新增20亩地",
        entities={
            "crop_name": "西瓜",
            "variety": "8424",
            "area_mu": 20,
            "planting_unit": {"area_mu": 20, "should_create": True},
        },
        missing_information=["种植单元名称"],
        next_action="等待用户补充：种植单元名称",
        status=TaskStateStatus.WAITING_USER,
    )

    await update_task_state_after_turn(
        db_session,
        _turn(user_input="叫东棚", assistant_reply="收到，按东棚继续。"),
    )

    task = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
    )

    assert task.status == TaskStateStatus.ACTIVE.value
    assert task.missing_information_json == []
    assert task.entities_json["planting_unit"]["name"] == "东棚"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_task_state_flow.py::test_task_state_writes_crop_cycle_setup_when_unit_name_missing backend/tests/agent/test_task_state_flow.py::test_task_state_crop_cycle_setup_accepts_unit_name_followup -q
```

Expected: tests fail because task type and entity extraction are not implemented.

- [ ] **Step 3: Implement minimal extraction**

Implement helper functions in `task_state_updater.py`:

```python
def _is_crop_cycle_setup_intent(text: str) -> bool:
    return "茬口" in text and any(word in text for word in ("创建", "新建", "新增", "建"))


def _extract_crop_cycle_setup_entities(text: str) -> dict:
    # Extract crop_name via existing _extract_crop, variety via numeric cultivar token,
    # area_mu via number followed by 亩, and planting_unit.name from "叫X" follow-up.
```

For the first implementation, support the exact business patterns in the tests:

- crop from `_extract_crop`
- variety from `8424` style numeric cultivar token not followed by `亩`
- area from `20亩`
- unit name from `叫东棚`

- [ ] **Step 4: Make updater prefer crop_cycle_setup**

Update `_classify_task_type`, `_infer_missing_information_from_task_intent`, `_extract_entities`, and `_remaining_missing_after_user_reply` as needed so crop setup tasks keep structured entities and clear `种植单元名称` when user supplies a name.

- [ ] **Step 5: Run task state tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_task_state_flow.py -q
```

Expected: all task state tests pass.

## Task 2: Pending Plan Output Binding

**Files:**
- Modify: `backend/app/agent/executor/pending_actions.py`
- Test: `backend/tests/agent/test_pending_plan_executor.py`

- [ ] **Step 1: Add failing tests**

Add tests proving:

```python
async def test_pending_plan_resolves_from_step_cycle_id(db_session, monkeypatch):
    # Store a two-step runtime plan where create_planting_unit.cycle_id references
    # create_crop_cycle.id through {"$from_step": "create_crop_cycle", "path": "id"}.
    # Mock raw execution so step 1 returns {"id": 123, "reply": "已创建茬口"}.
    # Assert step 2 receives cycle_id=123.
```

```python
async def test_pending_plan_stops_when_from_step_binding_missing(db_session, monkeypatch):
    # Store a two-step runtime plan where step 2 references a missing id.
    # Assert step 2 is not executed and decision.status == "failed".
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_pending_plan_executor.py::test_pending_plan_resolves_from_step_cycle_id backend/tests/agent/test_pending_plan_executor.py::test_pending_plan_stops_when_from_step_binding_missing -q
```

Expected: tests fail because `$from_step` is passed through as a dict.

- [ ] **Step 3: Implement binding resolver**

Add pure helpers in `pending_actions.py`:

```python
def _resolve_step_param_bindings(params: dict, results_by_step: dict[str, object]) -> dict:
    resolved = {}
    for key, value in params.items():
        resolved[key] = _resolve_binding_value(value, results_by_step)
    return resolved


def _resolve_binding_value(value, results_by_step):
    if isinstance(value, dict) and "$from_step" in value:
        source = results_by_step.get(str(value["$from_step"]))
        return _read_result_path(source, str(value.get("path") or "id"))
    if isinstance(value, dict):
        return {key: _resolve_binding_value(item, results_by_step) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_binding_value(item, results_by_step) for item in value]
    return value
```

Raise `ValueError` with a clear Chinese message if the source step or path is missing.

- [ ] **Step 4: Store step results during execution**

Update `_confirm_pending_plan` to keep `results_by_step` and pass it into `_execute_pending_plan_step`. Before contract validation, resolve bindings in normalized params.

- [ ] **Step 5: Run pending plan executor tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_pending_plan_executor.py -q
```

Expected: all pending plan executor tests pass.

## Task 3: Crop Setup Runtime Planner

**Files:**
- Create: `backend/app/agent/runtime/crop_cycle_setup_planner.py`
- Modify: `backend/app/agent/runtime/tool_pending.py`
- Modify: `backend/app/infra/pending_action_presenter.py`
- Test: `backend/tests/agent/test_plan_draft_pending_execution.py`

- [ ] **Step 1: Add failing tests**

Add tests proving:

```python
async def test_crop_cycle_setup_two_step_plan_records_area():
    # Existing "帮我创建一个西瓜茬口8424，大概种植20亩地" case should produce
    # manage_crop_templates + manage_crop_cycle, with create_cycle area=20.
```

```python
async def test_crop_cycle_setup_three_step_plan_with_unit_name_from_task_state():
    # Given active_task_state metadata/entities with planting_unit.name=东棚,
    # a manage_crop_cycle.create_cycle tool call should produce:
    # manage_crop_templates -> manage_crop_cycle -> manage_planting_units.
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_plan_draft_pending_execution.py::test_crop_cycle_setup_two_step_plan_records_area backend/tests/agent/test_plan_draft_pending_execution.py::test_crop_cycle_setup_three_step_plan_with_unit_name_from_task_state -q
```

Expected: the two-step case lacks area or the three-step case is missing.

- [ ] **Step 3: Create planner module**

Create a focused module with pure functions:

```python
@dataclass(frozen=True)
class CropCycleSetupPlan:
    steps: list[dict]
    area_note: str = ""


def build_crop_cycle_setup_steps(tool_calls: list[dict], original_input: str, active_task_state: dict | None = None) -> CropCycleSetupPlan | None:
    # Return None unless this is a single manage_crop_cycle create_cycle call.
    # Build ensure template + create cycle.
    # Add create planting unit only when active task state has planting_unit.name.
```

- [ ] **Step 4: Integrate planner in tool_pending**

Replace the local `_crop_cycle_template_preflight_steps` logic with the new planner. Keep backwards-compatible behavior for the existing two-step test.

- [ ] **Step 5: Improve presenter text**

In `_format_plan_step`, add `manage_planting_units` create text:

```python
return f"创建种植单元：{name}（{area}亩）"
```

- [ ] **Step 6: Run runtime planning tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider backend/tests/agent/test_plan_draft_pending_execution.py -q
```

Expected: all tests pass.

## Task 4: Integration Verification

**Files:**
- Modify only if verification exposes defects.

- [ ] **Step 1: Run related tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend pytest -p no:cacheprovider \
  backend/tests/agent/test_task_state_flow.py \
  backend/tests/agent/test_plan_draft_pending_execution.py \
  backend/tests/agent/test_pending_plan_executor.py \
  backend/tests/agent/test_function_call_contract_regressions.py \
  backend/tests/test_mixed_tool_results.py -q
```

- [ ] **Step 2: Run lint and format check**

```bash
ruff check backend/app/application/chat/task_state_updater.py backend/app/agent/runtime/crop_cycle_setup_planner.py backend/app/agent/runtime/tool_pending.py backend/app/agent/executor/pending_actions.py backend/app/infra/pending_action_presenter.py backend/tests/agent/test_task_state_flow.py backend/tests/agent/test_plan_draft_pending_execution.py backend/tests/agent/test_pending_plan_executor.py
ruff format --check backend/app/application/chat/task_state_updater.py backend/app/agent/runtime/crop_cycle_setup_planner.py backend/app/agent/runtime/tool_pending.py backend/app/agent/executor/pending_actions.py backend/app/infra/pending_action_presenter.py backend/tests/agent/test_task_state_flow.py backend/tests/agent/test_plan_draft_pending_execution.py backend/tests/agent/test_pending_plan_executor.py
```

- [ ] **Step 3: Run project checks**

```bash
bash scripts/check-complexity-budget.sh
bash scripts/check-layer-deps.sh
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/application/chat/task_state_updater.py backend/app/agent/runtime/crop_cycle_setup_planner.py backend/app/agent/runtime/tool_pending.py backend/app/agent/executor/pending_actions.py backend/app/infra/pending_action_presenter.py backend/tests/agent/test_task_state_flow.py backend/tests/agent/test_plan_draft_pending_execution.py backend/tests/agent/test_pending_plan_executor.py docs/superpowers/plans/2026-07-24-crop-cycle-setup-task-planning.md
git commit -m "feat: 支持茬口创建任务规划"
```
