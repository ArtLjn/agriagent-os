# Data Flywheel Issue Candidates Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 Agent 数据飞轮的领域坏例候选规则，并让 bad case 能生成更可审查的 regression case 草稿。

**Architecture:** 保持当前轻量架构：DataFlywheel 列表仍由 MySQL turn 索引驱动，详情读取 JSONL event segment。规则检测继续集中在 `data_flywheel_issue_detector.py`，case 草稿增强集中在 `data_flywheel_case_builder.py`，API 只透传服务层结果。AI 自动标注不在本计划内实现，本计划只做确定性规则候选和 regression draft 证据增强。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, JSONL agent events, existing DataFlywheel service/API.

---

## Scope Check

本计划只覆盖后端确定性规则候选和 regression case 草稿增强：

- 包含：`disabled_worker_used`、`missing_wage`、`tool_error_ignored`、多写工具 pending 覆盖不足的候选检测。
- 包含：case draft 中保留 issue candidate 证据和结构化 issue assertions。
- 不包含：LLM-as-judge 自动预标注、前端 AI 预判 UI、dataset 版本管理、DB-backed simulation cases。

相关长期路线见：

- `/Users/ljn/Documents/demo/explore/docs/architecture/agent-data-flywheel-industrial-roadmap.md`
- `/Users/ljn/Documents/demo/explore/docs/superpowers/specs/2026-06-11-agent-data-flywheel-admin-design.md`

## Current Code Map

- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_issue_detector.py`
  - 负责从 user input、assistant reply、selected tools、event payload、pending lifecycle 中产出 `issue_candidates`。
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_case_builder.py`
  - 负责把 DataFlywheel sample detail 转成 `agent_case_drafts.case_json`。
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`
  - 负责允许标签枚举、样本列表、详情、导出和 case draft 编排。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_issue_detector.py`
  - 新增纯函数单测，快速覆盖规则检测，不依赖数据库。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`
  - 增加服务集成测试，确认事件写入后 list/detail/case draft 均带出候选和断言。
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_admin_data_flywheel.py`
  - 增加 API 回归测试，确认 admin API 透传新增候选和 case draft 证据。

## Dirty Worktree Warning

执行本计划前先运行：

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
```

当前仓库可能已有其他 session 的未提交改动。执行者只允许修改本计划列出的文件；不要回滚、删除、格式化或提交无关文件。

---

### Task 1: Add Focused Unit Tests For Issue Candidate Rules

**Files:**
- Create: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_issue_detector.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_issue_detector.py`

- [ ] **Step 1: Write the failing detector tests**

Create `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_issue_detector.py` with:

```python
"""数据飞轮问题候选规则检测测试。"""

from app.services.data_flywheel_issue_detector import detect_issue_candidates


def _candidate_types(candidates: list[dict[str, str]]) -> list[str]:
    return [item["type"] for item in candidates]


def test_detects_disabled_worker_used_from_tool_result() -> None:
    candidates = detect_issue_candidates(
        user_input="今天李一凡去5号棚收水稻，工资100一天",
        assistant_reply="已安排李一凡去5号棚收水稻。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "李一凡",
                        "unit_price": 100,
                    },
                    "result": {
                        "labor_entries": [
                            {
                                "worker_name": "李一凡",
                                "worker_status": "inactive",
                            }
                        ]
                    },
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert candidates == [
        {
            "type": "disabled_worker_used",
            "severity": "high",
            "reason": "已停用工人仍被安排到作业或工资记录中",
            "evidence": "李一凡",
            "suggested_label": "disabled_worker_used",
        }
    ]


def test_detects_missing_wage_when_work_order_has_workers_without_wage_policy() -> None:
    candidates = detect_issue_candidates(
        user_input="今天王大妈去5号棚收水稻",
        assistant_reply="已安排王大妈去5号棚收水稻。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "收水稻",
                    },
                    "result": {"id": 9},
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert candidates == [
        {
            "type": "missing_wage",
            "severity": "high",
            "reason": "作业包含工人，但没有工资单价、已付金额、不计工资或欠款策略",
            "evidence": "王大妈",
            "suggested_label": "missing_wage",
        }
    ]


def test_no_missing_wage_when_no_wage_policy_is_explicit() -> None:
    candidates = detect_issue_candidates(
        user_input="今天王大妈帮忙巡棚，不计工资",
        assistant_reply="已记录王大妈巡棚，本次不计工资。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "巡棚",
                        "wage_policy": "no_wage",
                    },
                    "result": {"id": 10},
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert "missing_wage" not in _candidate_types(candidates)


def test_detects_pending_missed_for_each_uncovered_write_tool() -> None:
    candidates = detect_issue_candidates(
        user_input="停用李一凡，再安排王大妈去5号棚收水稻，工资100一天",
        assistant_reply="已停用李一凡，并已安排王大妈去5号棚收水稻。",
        selected_tools=["manage_workers", "create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "manage_workers",
                    "params": {"action": "deactivate", "name": "李一凡"},
                    "result": {"id": 3},
                },
            },
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {"workers": "王大妈", "unit_price": 100},
                    "result": {"id": 9},
                },
            },
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "manage_workers"}],
                },
            }
        ],
    )

    pending_candidates = [
        item for item in candidates if item["type"] == "pending_missed"
    ]
    assert pending_candidates == [
        {
            "type": "pending_missed",
            "severity": "high",
            "reason": "router 选择了写操作工具，但 pending lifecycle 中没有对应的确认计划",
            "evidence": "create_operation_work_order",
            "suggested_label": "pending_missed",
        }
    ]


def test_detects_tool_error_ignored_with_specific_label() -> None:
    candidates = detect_issue_candidates(
        user_input="给王大妈记一笔工资100元",
        assistant_reply="已保存工资：王大妈 应付100元。",
        selected_tools=["manage_wages"],
        events=[
            {
                "event_type": "tool.call.failed",
                "payload": {
                    "tool_name": "manage_wages",
                    "error": "新增工资需要关联茬口 cycle_id。",
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {"steps": [{"skill_name": "manage_wages"}]},
            }
        ],
    )

    assert {
        "type": "tool_error_ignored",
        "severity": "medium",
        "reason": "工具调用失败后，回复仍呈现为已完成",
        "evidence": "manage_wages",
        "suggested_label": "tool_error_ignored",
    } in candidates
```

- [ ] **Step 2: Run detector tests to verify they fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_issue_detector.py -q
```

Expected:

- `test_detects_disabled_worker_used_from_tool_result` fails because no `disabled_worker_used` candidate exists.
- `test_detects_missing_wage_when_work_order_has_workers_without_wage_policy` fails because no `missing_wage` candidate exists.
- `test_detects_tool_error_ignored_with_specific_label` fails because current suggested label is `bad_reply`.

- [ ] **Step 3: Implement minimal detector helpers**

Modify `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_issue_detector.py`.

Add constants near the existing term constants:

```python
DISABLED_WORKER_STATUS_TERMS = (
    "inactive",
    "disabled",
    "deactivated",
    "已停用",
    "停用",
    "离职",
)
WORKER_FIELD_KEYS = (
    "worker",
    "workers",
    "worker_name",
    "worker_names",
    "labor_entries",
)
WAGE_FIELD_KEYS = (
    "unit_price",
    "default_unit_price",
    "paid_amount",
    "payable_amount",
    "unpaid_amount",
    "quantity",
)
NO_WAGE_FIELD_KEYS = ("no_wage", "wage_policy")
NO_WAGE_VALUES = ("none", "no_wage", "free", "不计工资", "无工资")
WORK_ORDER_TOOLS = ("create_operation_work_order", "manage_wages")
```

In `detect_issue_candidates`, after `pending_missed` and before `failed_tools`, add:

```python
    disabled_workers = _disabled_worker_evidence(events)
    if disabled_workers:
        candidates.append(
            _candidate(
                "disabled_worker_used",
                "high",
                "已停用工人仍被安排到作业或工资记录中",
                ", ".join(disabled_workers),
                "disabled_worker_used",
            )
        )

    missing_wage_workers = _missing_wage_evidence(events)
    if missing_wage_workers:
        candidates.append(
            _candidate(
                "missing_wage",
                "high",
                "作业包含工人，但没有工资单价、已付金额、不计工资或欠款策略",
                ", ".join(missing_wage_workers),
                "missing_wage",
            )
        )
```

Change the existing `tool_error_ignored` candidate suggested label from `"bad_reply"` to `"tool_error_ignored"`:

```python
                "tool_error_ignored",
```

Add these helpers at the end of the file:

```python
def _disabled_worker_evidence(events: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if not _is_worker_write_payload(payload):
            continue
        names.extend(_disabled_worker_names(payload))
    return _unique(names)


def _missing_wage_evidence(events: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if not _is_work_order_payload(payload):
            continue
        if _has_wage_policy(payload):
            continue
        worker_names = _worker_names(payload)
        if worker_names:
            names.extend(worker_names)
    return _unique(names)


def _is_worker_write_payload(payload: dict[str, Any]) -> bool:
    tool_name = str(payload.get("tool_name") or "").lower()
    return tool_name in WORK_ORDER_TOOLS or tool_name == "manage_workers"


def _is_work_order_payload(payload: dict[str, Any]) -> bool:
    tool_name = str(payload.get("tool_name") or "").lower()
    return tool_name in WORK_ORDER_TOOLS


def _disabled_worker_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        status = _status_text(value)
        current_name = _name_text(value)
        names: list[str] = []
        if status and _is_disabled_status(status):
            names.append(current_name or status)
        for item in value.values():
            names.extend(_disabled_worker_names(item))
        return names
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_disabled_worker_names(item))
        return names
    return []


def _worker_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        names: list[str] = []
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in WORKER_FIELD_KEYS and isinstance(item, str):
                names.extend(_split_names(item))
            elif key_text in {"name", "worker_name"} and isinstance(item, str):
                names.extend(_split_names(item))
            else:
                names.extend(_worker_names(item))
        return names
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_worker_names(item))
        return names
    return []


def _has_wage_policy(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in WAGE_FIELD_KEYS and item not in (None, "", 0, "0"):
                return True
            if key_text in NO_WAGE_FIELD_KEYS and _is_no_wage_value(item):
                return True
            if _has_wage_policy(item):
                return True
        return False
    if isinstance(value, list):
        return any(_has_wage_policy(item) for item in value)
    return False


def _status_text(value: dict[str, Any]) -> str | None:
    for key in ("status", "worker_status", "state"):
        if value.get(key) not in (None, ""):
            return str(value[key])
    return None


def _name_text(value: dict[str, Any]) -> str | None:
    for key in ("worker_name", "name"):
        if value.get(key) not in (None, ""):
            return str(value[key]).strip()
    return None


def _is_disabled_status(value: str) -> bool:
    normalized = value.lower()
    return any(term in normalized for term in DISABLED_WORKER_STATUS_TERMS)


def _is_no_wage_value(value: Any) -> bool:
    if value is True:
        return True
    normalized = str(value or "").strip().lower()
    return normalized in NO_WAGE_VALUES


def _split_names(value: str) -> list[str]:
    separators = [",", "，", "、", ";", "；"]
    text = value
    for separator in separators:
        text = text.replace(separator, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
```

- [ ] **Step 4: Run detector tests to verify they pass**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_issue_detector.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit Task 1**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/services/test_data_flywheel_issue_detector.py backend/app/services/data_flywheel_issue_detector.py
git commit -m "feat: 增强数据飞轮领域坏例候选规则"
```

---

### Task 2: Allow New Data Flywheel Labels

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py`
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`

- [ ] **Step 1: Write the failing label allow-list test**

Append this test after `test_invalid_label_and_farm_mismatch_raise_value_error` in `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`:

```python
def test_new_issue_candidate_labels_can_be_saved(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    tool_error_label = add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        label="tool_error_ignored",
        annotator_id="admin-1",
    )
    unclear_label = add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        label="unclear_intent",
        annotator_id="admin-1",
    )

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert tool_error_label["label"] == "tool_error_ignored"
    assert unclear_label["label"] == "unclear_intent"
    assert detail["quality_labels"] == ["tool_error_ignored", "unclear_intent"]
    db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_new_issue_candidate_labels_can_be_saved -q
```

Expected:

```text
ValueError: INVALID_LABEL
```

- [ ] **Step 3: Add the labels to the allow-list**

Modify `ALLOWED_LABELS` in `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_service.py` to include:

```python
    "tool_error_ignored",
    "unclear_intent",
```

The resulting set should contain these labels:

```python
ALLOWED_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "pending_missed",
    "hallucinated_execution",
    "tool_error_ignored",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "off_topic",
    "sensitive_info_leak",
    "unclear_intent",
    "not_actionable",
}
```

- [ ] **Step 4: Run the label test to verify it passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_new_issue_candidate_labels_can_be_saved -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit Task 2**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/data_flywheel_service.py backend/tests/services/test_data_flywheel_service.py
git commit -m "feat: 扩展数据飞轮质量标签枚举"
```

---

### Task 3: Add Service Integration Tests For Domain Issue Candidates

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_issue_detector.py`

- [ ] **Step 1: Write failing service integration tests**

Append these tests after `test_issue_candidates_detect_hallucinated_execution_and_sensitive_leak`:

```python
def test_issue_candidates_detect_disabled_worker_and_missing_wage_from_events(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        include_pending=True,
        session_id="sess-worker-risk",
        user_input="今天李一凡和王大妈去5号棚收水稻",
        assistant_reply="已安排李一凡和王大妈去5号棚收水稻。",
        request_id="worker-risk-1",
        router_tools=["create_operation_work_order"],
        tool_events=[
            (
                "tool.call.finished",
                {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "李一凡，王大妈",
                        "operation_type": "收水稻",
                    },
                    "result": {
                        "id": 9,
                        "labor_entries": [
                            {
                                "worker_name": "李一凡",
                                "worker_status": "inactive",
                            },
                            {
                                "worker_name": "王大妈",
                                "worker_status": "active",
                            },
                        ],
                    },
                },
            )
        ],
    )
    sample_id = f"turn:1:sess-worker-risk:{turn.id}"

    samples = list_samples(db, farm_id=1, q="worker-risk-1")
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert [item["type"] for item in samples["items"][0]["issue_candidates"]] == [
        "disabled_worker_used",
        "missing_wage",
    ]
    assert detail["issue_candidates"] == samples["items"][0]["issue_candidates"]
    assert detail["issue_candidates"][0]["evidence"] == "李一凡"
    assert detail["issue_candidates"][1]["evidence"] == "李一凡, 王大妈"
    db.close()


def test_issue_candidates_do_not_flag_missing_wage_when_unit_price_exists(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        include_pending=True,
        session_id="sess-wage-ok",
        user_input="今天王大妈去5号棚收水稻，工资100一天",
        assistant_reply="已安排王大妈去5号棚收水稻，工资100元。",
        request_id="wage-ok-1",
        router_tools=["create_operation_work_order"],
        tool_events=[
            (
                "tool.call.finished",
                {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "收水稻",
                        "unit_price": 100,
                    },
                    "result": {
                        "id": 10,
                        "labor_entries": [
                            {
                                "worker_name": "王大妈",
                                "worker_status": "active",
                            }
                        ],
                    },
                },
            )
        ],
    )
    sample_id = f"turn:1:sess-wage-ok:{turn.id}"

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert "missing_wage" not in [
        item["type"] for item in detail["issue_candidates"]
    ]
    db.close()
```

- [ ] **Step 2: Run service integration tests to verify failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest \
  tests/services/test_data_flywheel_service.py::test_issue_candidates_detect_disabled_worker_and_missing_wage_from_events \
  tests/services/test_data_flywheel_service.py::test_issue_candidates_do_not_flag_missing_wage_when_unit_price_exists \
  -q
```

Expected:

- First test fails before Task 1 implementation.
- Second test protects against false positive after Task 1 implementation.

- [ ] **Step 3: If Task 1 is already implemented, only adjust evidence ordering**

If the first test fails because evidence order differs, update `_worker_names()` and `_unique()` usage so `params.workers` preserves user order and result worker names do not duplicate it. The expected evidence must remain:

```text
李一凡, 王大妈
```

- [ ] **Step 4: Run service integration tests to verify pass**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest \
  tests/services/test_data_flywheel_service.py::test_issue_candidates_detect_disabled_worker_and_missing_wage_from_events \
  tests/services/test_data_flywheel_service.py::test_issue_candidates_do_not_flag_missing_wage_when_unit_price_exists \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit Task 3**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/services/test_data_flywheel_service.py backend/app/services/data_flywheel_issue_detector.py
git commit -m "test: 覆盖数据飞轮领域坏例候选集成"
```

---

### Task 4: Preserve Issue Candidates In Case Drafts

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_case_builder.py`
- Test: `/Users/ljn/Documents/demo/explore/backend/tests/services/test_data_flywheel_service.py`

- [ ] **Step 1: Write the failing case draft test**

Append this test after `test_build_case_draft_from_sample`:

```python
def test_build_case_draft_preserves_issue_candidate_assertions(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        include_pending=True,
        session_id="sess-case-issues",
        user_input="今天李一凡和王大妈去5号棚收水稻",
        assistant_reply="已安排李一凡和王大妈去5号棚收水稻。",
        request_id="case-issues-1",
        router_tools=["create_operation_work_order"],
        tool_events=[
            (
                "tool.call.finished",
                {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "李一凡，王大妈",
                        "operation_type": "收水稻",
                    },
                    "result": {
                        "id": 9,
                        "labor_entries": [
                            {
                                "worker_name": "李一凡",
                                "worker_status": "inactive",
                            },
                            {
                                "worker_name": "王大妈",
                                "worker_status": "active",
                            },
                        ],
                    },
                },
            )
        ],
    )
    sample_id = f"turn:1:sess-case-issues:{turn.id}"
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="disabled_worker_used")
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="missing_wage")
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="needs_regression")

    draft = build_case_draft(
        db,
        farm_id=1,
        sample_id=sample_id,
        target_type="evaluation_replay",
        created_by="admin-1",
    )

    assert draft["case_json"]["metadata"]["issue_candidates"] == [
        {
            "type": "disabled_worker_used",
            "severity": "high",
            "reason": "已停用工人仍被安排到作业或工资记录中",
            "evidence": "李一凡",
            "suggested_label": "disabled_worker_used",
        },
        {
            "type": "missing_wage",
            "severity": "high",
            "reason": "作业包含工人，但没有工资单价、已付金额、不计工资或欠款策略",
            "evidence": "李一凡, 王大妈",
            "suggested_label": "missing_wage",
        },
    ]
    assert draft["case_json"]["issue_assertions"] == [
        {
            "type": "disabled_worker_used",
            "expected": "停用或离职工人不得被安排到作业或工资记录中",
            "evidence": "李一凡",
        },
        {
            "type": "missing_wage",
            "expected": "包含工人的作业必须明确工资、已付金额、不计工资或欠款策略",
            "evidence": "李一凡, 王大妈",
        },
    ]
    db.close()
```

- [ ] **Step 2: Run the case draft test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_build_case_draft_preserves_issue_candidate_assertions -q
```

Expected:

```text
KeyError: 'issue_candidates'
```

or:

```text
KeyError: 'issue_assertions'
```

- [ ] **Step 3: Implement case draft issue metadata**

Modify `build_case_json()` in `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_case_builder.py`.

Change the `metadata` block to include `issue_candidates`:

```python
        "metadata": {
            "source": "data_flywheel",
            "source_sample_id": sample_id,
            "source_session_id": sample["session_id"],
            "source_request_id": sample["request_id"],
            "quality_labels": quality_labels,
            "issue_candidates": detail.get("issue_candidates", []),
        },
```

Add a top-level field next to `reply_assertions`:

```python
        "issue_assertions": _issue_assertions(detail),
```

Add this helper below `_reply_assertions()`:

```python
def _issue_assertions(detail: dict[str, Any]) -> list[dict[str, str]]:
    assertions: list[dict[str, str]] = []
    for candidate in detail.get("issue_candidates", []):
        issue_type = candidate.get("type")
        expected = _expected_for_issue(issue_type)
        if not expected:
            continue
        assertions.append(
            {
                "type": str(issue_type),
                "expected": expected,
                "evidence": str(candidate.get("evidence") or ""),
            }
        )
    return assertions


def _expected_for_issue(issue_type: str | None) -> str | None:
    expected_by_type = {
        "disabled_worker_used": "停用或离职工人不得被安排到作业或工资记录中",
        "missing_wage": "包含工人的作业必须明确工资、已付金额、不计工资或欠款策略",
        "pending_missed": "写操作必须先创建 pending plan，用户确认后才能执行",
        "hallucinated_execution": "没有成功写工具调用时，回复不得声称已完成写入",
        "tool_error_ignored": "工具失败时回复必须说明失败或要求补充信息，不得伪装成功",
        "wrong_tool_selection": "router 必须选择与用户意图匹配的 skill",
    }
    return expected_by_type.get(issue_type)
```

- [ ] **Step 4: Run the case draft test to verify it passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/services/test_data_flywheel_service.py::test_build_case_draft_preserves_issue_candidate_assertions -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit Task 4**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/data_flywheel_case_builder.py backend/tests/services/test_data_flywheel_service.py
git commit -m "feat: 保留数据飞轮 case 草稿问题断言"
```

---

### Task 5: Add Admin API Regression Coverage

**Files:**
- Modify: `/Users/ljn/Documents/demo/explore/backend/tests/api/test_admin_data_flywheel.py`
- Modify: `/Users/ljn/Documents/demo/explore/backend/app/services/data_flywheel_case_builder.py`

- [ ] **Step 1: Write the failing API test**

Append this test after `test_build_case_draft_returns_source_sample_metadata`:

```python
def test_build_case_draft_api_returns_issue_candidate_assertions(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "needs_regression"},
            headers=admin_headers(),
        )
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["case_json"]["metadata"]["issue_candidates"] == [
        {
            "type": "pending_missed",
            "severity": "high",
            "reason": "router 选择了写操作工具，但 pending lifecycle 中没有对应的确认计划",
            "evidence": "create_operation_work_order",
            "suggested_label": "pending_missed",
        }
    ]
    assert data["case_json"]["issue_assertions"] == [
        {
            "type": "pending_missed",
            "expected": "写操作必须先创建 pending plan，用户确认后才能执行",
            "evidence": "create_operation_work_order",
        }
    ]
```

- [ ] **Step 2: Run the API test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/api/test_admin_data_flywheel.py::test_build_case_draft_api_returns_issue_candidate_assertions -q
```

Expected:

```text
KeyError: 'issue_candidates'
```

or:

```text
KeyError: 'issue_assertions'
```

- [ ] **Step 3: Ensure Task 4 implementation is available through API**

No API route change should be necessary because `/admin/data-flywheel/samples/{sample_id}/case-draft` already returns `draft["case_json"]`. If this test still fails after Task 4, inspect `/Users/ljn/Documents/demo/explore/backend/app/api/admin_data_flywheel.py` and confirm the response is not filtering out `case_json` fields.

Expected route behavior:

```python
return build_case_draft(
    db,
    farm_id=farm_id,
    sample_id=sample_id,
    target_type=body.target_type,
    created_by=current_user_id,
)
```

- [ ] **Step 4: Run the API test to verify it passes**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/api/test_admin_data_flywheel.py::test_build_case_draft_api_returns_issue_candidate_assertions -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit Task 5**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/api/test_admin_data_flywheel.py backend/app/services/data_flywheel_case_builder.py
git commit -m "test: 覆盖数据飞轮 case 草稿 API 证据"
```

---

### Task 6: Run Focused Regression Suite

**Files:**
- Verify only.

- [ ] **Step 1: Run focused service tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest \
  tests/services/test_data_flywheel_issue_detector.py \
  tests/services/test_data_flywheel_service.py \
  -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run focused API tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/api/test_admin_data_flywheel.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 3: Run diff safety checks**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git diff --check
git status --short
```

Expected:

- `git diff --check` prints no errors.
- `git status --short` shows only files intentionally touched by this plan plus pre-existing unrelated dirty files.

- [ ] **Step 4: Commit final verification notes if any docs were updated**

If no docs were changed during execution, skip this commit. If implementation required updating the industrial roadmap or DataFlywheel design, commit only those docs:

```bash
cd /Users/ljn/Documents/demo/explore
git add docs/architecture/agent-data-flywheel-industrial-roadmap.md docs/superpowers/specs/2026-06-11-agent-data-flywheel-admin-design.md
git commit -m "docs: 同步数据飞轮规则候选落地说明"
```

## Self-Review

- Spec coverage: The plan covers deterministic issue candidates, new label allow-list, service/API propagation, and regression case draft evidence. It does not cover LLM-as-judge because the roadmap explicitly places that after rules and human confirmation.
- Placeholder scan: The plan contains concrete file paths, exact test code, exact implementation snippets, and exact commands. It does not contain open-ended implementation placeholders.
- Type consistency: `issue_candidates` remains `list[dict[str, str]]`; `issue_assertions` is introduced as `list[dict[str, str]]`; label names match the industrial roadmap and service allow-list.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-data-flywheel-issue-candidates-regression.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in one session using executing-plans, batch execution with checkpoints.

Recommended choice for this repo state: Subagent-Driven, because the worktree already has unrelated dirty files and each task can be reviewed independently before moving on.
