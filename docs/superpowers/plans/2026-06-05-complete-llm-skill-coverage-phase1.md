# Complete LLM Skill Coverage Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有 19 个已注册 Skill 全部进入可发现、可治理、可拒绝、可审计的运行时闭环。

**Architecture:** Phase 1 不新增普通用户业务 Skill，也不做 Admin Skill 扩展；它先修补现有 Skill 注册表、selector、chain map、metadata 和 Tool Executor 的一致性。核心做法是把“已注册 Skill 是否有选择路径、链路策略、启用状态、权限 metadata”变成测试可审计的契约，再按契约补齐现有 19 个 Skill。

**Tech Stack:** Python 3.11, pytest, Pydantic v2, FastAPI settings, LangChain StructuredTool, skillify, OpenSpec。

## Execution Status

- Completed: Runtime coverage audit, selector/chain coverage, runtime metadata enablement, disabled Skill executor rejection, pending-action write registry alignment, and trusted farm-context tenant isolation.
- Completed hardening: `farm-status` and `crop-cycle` no longer default to farm 1; `crop-cycle` filters `cycle_id` lookups by `farm_id`; Skill cache keys include `farm_id`.
- Verified: targeted Phase 1 tests, OpenSpec validation, and Harness full verification passed during implementation.
- Deferred: coverage matrix, missing ordinary-user Skills, Admin Skills, and broader evaluation/diagnostics remain Phase 2/3 work.

---

## Scope Check

OpenSpec `complete-llm-skill-coverage` 覆盖多个子系统：现有 Skill 闭环、覆盖矩阵、新增普通用户 Skill、Admin Skill、评测诊断。为了让每份计划都能独立交付，本计划只覆盖 Phase 1：

- 覆盖审计基础：对应 OpenSpec tasks 1.1-1.5。
- 现有 Skill 运行时覆盖：对应 tasks 2.1-2.5。
- 现有 Skill metadata 完整性：对应 tasks 3.1-3.5 的运行时字段部分。
- Tool Executor disabled/external/admin/metadata precedence：对应 tasks 4.1-4.5。
- 用户隔离硬门槛：所有现有 Skill 必须只使用服务端注入的可信 `SkillContext.farm_id/farm_uid`，不得默认写入或读取 1 号农场，不得接受 LLM 传入的租户边界参数。
- Phase 1 验证：对应 tasks 9.1-9.3 与相关 targeted tests。

Phase 2 应单独处理覆盖矩阵和普通用户缺失 Skill。Phase 3 应单独处理 Admin Skill 与敏感能力策略。

## File Structure

- Create: `backend/tests/skills/test_skill_runtime_coverage.py`
  - 运行时注册表审计：检查 19 个 Skill、selector 覆盖、chain map 覆盖、写权限、disabled reason。
- Modify: `backend/app/agent/tool_selector.py`
  - 补齐 5 个缺失 Skill 的触发规则，新增 helper 判断 Skill 是否启用，补齐 `TOOL_CHAIN_MAP`。
- Modify: `backend/tests/test_tool_selector.py`
  - 扩展工具清单到 19 个，新增作业单、人工应付、人工结算、作业单更新选择测试。
- Modify: `backend/tests/test_tool_chain_map.py`
  - 让 chain map 测试覆盖所有已注册 Skill。
- Modify: `backend/app/agent/skills/metadata.py`
  - 增加 `business_domain`、`enabled`、`disabled_reason`、`production_ready` 字段；用中央映射补齐现有 19 个 Skill 的默认 metadata。
- Modify: `backend/tests/skills/test_skill_metadata.py`
  - 验证新增 metadata 字段、disabled `web_search`、19 个 Skill 的 production metadata。
- Modify: `backend/app/api/admin_config.py`
  - `/admin/skills` 继续返回 metadata；新增字段通过 `metadata_to_dict()` 自动出现。
- Modify: `backend/tests/api/test_admin_config.py`
  - 验证 admin Skill 列表暴露 enablement 和 domain 字段。
- Modify: `backend/app/agent/runtime/tool_executor.py`
  - 在参数校验前拒绝 disabled Skill；external network 权限通过 metadata enablement 治理；显式 metadata 继续优先于 legacy fallback。
- Modify: `backend/tests/agent/test_tool_executor_metadata.py`
  - 增加 disabled rejection、external network enabled execution、disabled trace status 测试。
- Modify: `backend/app/agent/skills/farm-status/scripts/main.py`
  - 去掉 `farm_id=1` 默认兜底，改为 `require_farm_context()`。
- Modify: `backend/app/agent/skills/crop-cycle/scripts/main.py`
  - 去掉 `farm_id=1` 默认兜底，改为 `require_farm_context()`。
- Modify: `backend/tests/skills/test_farm_status.py`
  - 更新缺上下文测试，要求失败且不访问 DB。
- Modify: `backend/tests/skills/test_crop_cycle.py`
  - 增加缺上下文测试，要求失败且不访问 DB。

### Task 1: Runtime Coverage Audit

**Files:**
- Create: `backend/tests/skills/test_skill_runtime_coverage.py`
- Test: `backend/tests/skills/test_skill_runtime_coverage.py`

- [ ] **Step 1: Write failing audit tests**

Create `backend/tests/skills/test_skill_runtime_coverage.py`:

```python
"""Skill 运行时覆盖审计测试。"""

import pytest

from app.agent.skills import get_skill_manager
from app.agent.skills.metadata import (
    SkillPermissionLevel,
    get_skill_metadata,
)
from app.agent.tool_selector import QUERY_TRIGGERS, TOOL_CHAIN_MAP, WRITE_PATTERNS

pytestmark = pytest.mark.no_db


EXPECTED_REGISTERED_SKILLS = {
    "get_cost_analytics",
    "get_cost_summary",
    "create_cost_record",
    "create_crop_cycle",
    "create_crop_template",
    "create_operation_work_order",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_operation_work_orders",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "get_weather_forecast",
    "web_search",
}

EXPECTED_WRITE_SKILLS = {
    "create_cost_record",
    "create_crop_cycle",
    "create_crop_template",
    "create_operation_work_order",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
}


def _registered_skills() -> dict[str, object]:
    manager = get_skill_manager()
    result = {}
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill is not None:
            result[skill_def.name] = skill
    return result


def test_registered_skill_inventory_is_expected() -> None:
    skills = _registered_skills()

    assert set(skills) == EXPECTED_REGISTERED_SKILLS


def test_enabled_registered_skills_have_selector_coverage() -> None:
    skills = _registered_skills()
    selector_names = set(WRITE_PATTERNS) | set(QUERY_TRIGGERS)
    missing = {
        name
        for name, skill in skills.items()
        if get_skill_metadata(skill).enabled and name not in selector_names
    }

    assert missing == set()


def test_enabled_registered_skills_have_chain_policy() -> None:
    skills = _registered_skills()
    missing = {
        name
        for name, skill in skills.items()
        if get_skill_metadata(skill).enabled and name not in TOOL_CHAIN_MAP
    }

    assert missing == set()


def test_write_skills_use_write_confirm_permission() -> None:
    skills = _registered_skills()
    wrong_permission = {
        name: get_skill_metadata(skills[name]).permission_level
        for name in EXPECTED_WRITE_SKILLS
        if get_skill_metadata(skills[name]).permission_level
        != SkillPermissionLevel.WRITE_CONFIRM
    }

    assert wrong_permission == {}


def test_disabled_skills_have_disabled_reason() -> None:
    skills = _registered_skills()
    disabled = {
        name: get_skill_metadata(skill).disabled_reason
        for name, skill in skills.items()
        if not get_skill_metadata(skill).enabled
    }

    assert disabled == {
        "web_search": "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"
    }
```

- [ ] **Step 2: Run audit tests to verify current failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/skills/test_skill_runtime_coverage.py -q
```

Expected: FAIL. The failure should report missing selector coverage for `create_operation_work_order`, `get_labor_payables`, `get_operation_work_orders`, `settle_labor_payment`, `update_operation_work_order`, missing chain entries, or missing metadata fields before later tasks are implemented.

- [ ] **Step 3: Commit failing audit tests**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/skills/test_skill_runtime_coverage.py
git commit -m "test(skill): 增加运行时覆盖审计"
```

### Task 2: Selector And Chain Coverage

**Files:**
- Modify: `backend/app/agent/tool_selector.py`
- Modify: `backend/tests/test_tool_selector.py`
- Modify: `backend/tests/test_tool_chain_map.py`
- Test: `backend/tests/test_tool_selector.py`
- Test: `backend/tests/test_tool_chain_map.py`
- Test: `backend/tests/skills/test_skill_runtime_coverage.py`

- [ ] **Step 1: Extend selector tests**

In `backend/tests/test_tool_selector.py`, replace `ALL_TOOL_NAMES` with:

```python
ALL_TOOL_NAMES = [
    "get_cost_analytics",
    "get_cost_summary",
    "create_cost_record",
    "create_crop_cycle",
    "create_crop_template",
    "create_operation_work_order",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_operation_work_orders",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "get_weather_forecast",
    "web_search",
]

ENABLED_TOOL_NAMES = [name for name in ALL_TOOL_NAMES if name != "web_search"]
```

In the same file, update fallback assertions that currently expect `ALL_TOOL_NAMES` so disabled `web_search` is excluded:

```python
def test_planting_advice_with_intent_phrase_does_not_write(self):
    result = select_tools("我想种小麦要注意什么", _make_tools())
    assert result == ENABLED_TOOL_NAMES
```

Apply the same replacement for `test_greeting_returns_all`, `test_planting_advice_returns_all`, `test_how_to_plant_new_crop_returns_all`, `test_planting_attention_returns_all`, `test_all_tools_present`, and `test_empty_message_returns_all`.

Add these tests under `TestWritePatternMatching`:

```python
def test_create_operation_work_order_with_labor_detail(self):
    result = select_tools("今天东大棚4个工人给西瓜授粉，每人200，先付老王200", _make_tools())
    assert result == ["create_operation_work_order"]


def test_settle_labor_payment_partial_payment(self):
    result = select_tools("给老王补付300人工", _make_tools())
    assert result == ["settle_labor_payment"]


def test_update_operation_work_order_correction(self):
    result = select_tools("刚才那条授粉记录不是付老王，是付老李200", _make_tools())
    assert result == ["update_operation_work_order"]
```

Add these tests under `TestQueryKeywordMatching`:

```python
def test_labor_payable_query_prefers_labor_skill(self):
    result = select_tools("老王还欠多少人工钱", _make_tools())
    assert result[0] == "get_labor_payables"
    assert "get_cost_summary" not in result


def test_operation_work_order_query(self):
    result = select_tools("最近玉米授粉作业有哪些", _make_tools())
    assert result == ["get_operation_work_orders"]
```

- [ ] **Step 2: Run selector tests to verify failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/test_tool_selector.py -q
```

Expected: FAIL. The new cases should fail because the five Skill trigger groups are not yet present and `ALL_TOOL_NAMES` fallback expectations need implementation support.

- [ ] **Step 3: Implement selector coverage**

In `backend/app/agent/tool_selector.py`, extend `WRITE_PATTERNS` with:

```python
    "create_operation_work_order": [
        re.compile(r"(?:授粉|压蔓|留瓜|垫瓜|采收|装车|打杈|绑蔓|整枝).*(?:工人|每人|人工|作业|干活)"),
        re.compile(r"(?:创建|新建|记录).*(?:作业单|农事作业|用工)"),
        re.compile(r"(?:东大棚|西大棚|地块|棚).*(?:工人|每人|人工).*(?:\d+\s*(?:元|块|人))"),
    ],
    "settle_labor_payment": [
        re.compile(r"(?:补付|支付|结算|付清|结清).*(?:人工|工钱|工资)"),
        re.compile(r"(?:给|付给).{1,12}(?:\d+\s*(?:元|块|百|千)).*(?:人工|工钱|工资)"),
    ],
    "update_operation_work_order": [
        re.compile(r"(?:刚才|上一条|那条|这条).*(?:不是|改成|改为|改到|更正|纠正).*(?:作业|记录|授粉|人工|工人|付)"),
        re.compile(r"(?:修改|更改|调整|纠正).*(?:作业单|农事作业|用工记录)"),
    ],
```

Extend `QUERY_TRIGGERS` with:

```python
    "get_labor_payables": {
        "人工钱",
        "工钱",
        "工资",
        "未付人工",
        "欠人工",
        "还欠多少人工",
        "人工欠款",
    },
    "get_operation_work_orders": {
        "作业单",
        "农事作业",
        "授粉作业",
        "作业有哪些",
        "用工记录",
        "最近授粉",
        "最近采收",
    },
```

Replace the hardcoded disabled filtering section with helper functions near `DISABLED_SKILLS`:

```python
DISABLED_SKILLS: set[str] = {
    "web_search",  # SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用
}


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    if metadata is not None and hasattr(metadata, "enabled"):
        return bool(metadata.enabled)
    return tool.name not in DISABLED_SKILLS
```

Then change the first line inside `select_tools()` from:

```python
    all_tools = [t for t in all_tools if t.name not in DISABLED_SKILLS]
```

to:

```python
    all_tools = [t for t in all_tools if _tool_enabled(t)]
```

After the existing `update_crop_cycle` candidate reduction, add:

```python
    if "get_labor_payables" in candidates:
        candidates.difference_update({"get_cost_summary"})

    if "get_operation_work_orders" in candidates:
        candidates.difference_update({"get_recent_farm_logs", "get_farm_status"})

    if "settle_labor_payment" in candidates:
        candidates.difference_update({"settle_debt", "create_cost_record"})

    if "update_operation_work_order" in candidates:
        candidates.difference_update({"create_operation_work_order", "log_farm_activity"})
```

- [ ] **Step 4: Update chain map tests**

In `backend/tests/test_tool_chain_map.py`, replace `expected_keys` with:

```python
expected_keys = {
    "get_cost_analytics",
    "get_cost_summary",
    "create_cost_record",
    "create_crop_cycle",
    "create_crop_template",
    "create_operation_work_order",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_operation_work_orders",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "get_weather_forecast",
    "web_search",
}
```

Extend the `query_tools` list with:

```python
"get_labor_payables",
"get_operation_work_orders",
```

Extend `write_tools` with:

```python
"create_operation_work_order",
"settle_labor_payment",
"update_crop_cycle",
"update_operation_work_order",
```

Add:

```python
def test_labor_payables_chain(self):
    result = expand_by_chain({"get_labor_payables"})
    assert "get_farm_status" in result


def test_operation_work_orders_chain(self):
    result = expand_by_chain({"get_operation_work_orders"})
    assert "get_farm_status" in result
```

- [ ] **Step 5: Implement full chain map**

In `backend/app/agent/tool_selector.py`, replace `TOOL_CHAIN_MAP` with:

```python
TOOL_CHAIN_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["get_farm_status"],
    "get_cost_summary": ["get_farm_status"],
    "get_cost_analytics": ["get_farm_status"],
    "get_crop_cycle_info": ["get_farm_status"],
    "get_recent_farm_logs": ["get_farm_status"],
    "get_labor_payables": ["get_farm_status"],
    "get_operation_work_orders": ["get_farm_status"],
    "create_cost_record": [],
    "create_crop_cycle": [],
    "create_crop_template": [],
    "create_operation_work_order": [],
    "log_farm_activity": [],
    "settle_debt": [],
    "settle_labor_payment": [],
    "update_crop_cycle": [],
    "update_crop_stage": [],
    "update_operation_work_order": [],
    "get_farm_status": [],
    "web_search": [],
}
```

- [ ] **Step 6: Run selector and chain tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/test_tool_selector.py tests/test_tool_chain_map.py tests/skills/test_skill_runtime_coverage.py -q
```

Expected: selector and chain tests PASS. Runtime coverage may still FAIL on metadata fields until Task 3.

- [ ] **Step 7: Commit selector and chain coverage**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/tool_selector.py backend/tests/test_tool_selector.py backend/tests/test_tool_chain_map.py
git commit -m "feat(agent): 补齐现有 Skill 选择与链路覆盖"
```

### Task 3: Skill Metadata Completion

**Files:**
- Modify: `backend/app/agent/skills/metadata.py`
- Modify: `backend/tests/skills/test_skill_metadata.py`
- Modify: `backend/tests/api/test_admin_config.py`
- Test: `backend/tests/skills/test_skill_metadata.py`
- Test: `backend/tests/api/test_admin_config.py`
- Test: `backend/tests/skills/test_skill_runtime_coverage.py`

- [ ] **Step 1: Add metadata field tests**

In `backend/tests/skills/test_skill_metadata.py`, extend `_CustomSkill.metadata()` with:

```python
            "business_domain": "admin",
            "enabled": True,
            "disabled_reason": "",
            "production_ready": True,
```

Add these tests:

```python
class _KnownLaborSkill:
    def name(self):
        return "settle_labor_payment"


def test_known_skill_metadata_includes_runtime_governance_fields():
    metadata = get_skill_metadata(_KnownLaborSkill())

    assert metadata.business_domain == "labor"
    assert metadata.enabled is True
    assert metadata.disabled_reason == ""
    assert metadata.production_ready is True
    assert metadata.metadata_incomplete is False


def test_web_search_metadata_is_disabled_with_reason():
    metadata = get_skill_metadata(_ExternalNetworkSkill())

    assert metadata.permission_level == SkillPermissionLevel.EXTERNAL_NETWORK
    assert metadata.business_domain == "external_network"
    assert metadata.enabled is False
    assert metadata.disabled_reason == "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"
    assert metadata.production_ready is False
```

Add this test after registry metadata tests:

```python
def test_all_runtime_skills_have_complete_known_metadata():
    from app.agent.skills import get_skill_manager

    manager = get_skill_manager()
    missing = {}
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        metadata = get_skill_metadata(skill)
        if metadata.business_domain == "general" or metadata.metadata_incomplete:
            missing[skill_def.name] = metadata.model_dump(mode="json")

    assert missing == {}
```

- [ ] **Step 2: Run metadata tests to verify failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/skills/test_skill_metadata.py -q
```

Expected: FAIL because `SkillMetadata` does not yet define `business_domain`, `enabled`, `disabled_reason`, or `production_ready`.

- [ ] **Step 3: Implement metadata fields and central defaults**

In `backend/app/agent/skills/metadata.py`, update `SkillMetadata`:

```python
class SkillMetadata(BaseModel):
    """Skill runtime metadata。"""

    permission_level: SkillPermissionLevel = SkillPermissionLevel.READ
    risk_level: SkillRiskLevel = SkillRiskLevel.LOW
    context_dependencies: list[str] = Field(default_factory=list)
    cache_invalidation: list[str] = Field(default_factory=list)
    confirmation_schema: ConfirmationSchema = Field(default_factory=ConfirmationSchema)
    evaluation_tags: list[str] = Field(default_factory=list)
    business_domain: str = "general"
    enabled: bool = True
    disabled_reason: str = ""
    production_ready: bool = False
    metadata_incomplete: bool = False
```

Add these constants below `_EXTERNAL_NETWORK_SKILLS`:

```python
_DISABLED_SKILL_REASONS = {
    "web_search": "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用",
}

_SKILL_DOMAINS = {
    "get_cost_analytics": "ledger",
    "get_cost_summary": "ledger",
    "create_cost_record": "ledger",
    "settle_debt": "ledger",
    "create_crop_cycle": "crop_cycle",
    "create_crop_template": "crop_template",
    "get_crop_cycle_info": "crop_cycle",
    "update_crop_cycle": "crop_cycle",
    "update_crop_stage": "crop_cycle",
    "get_recent_farm_logs": "farm_log",
    "log_farm_activity": "farm_log",
    "get_farm_status": "farm_status",
    "create_operation_work_order": "planting_operation",
    "get_operation_work_orders": "planting_operation",
    "update_operation_work_order": "planting_operation",
    "get_labor_payables": "labor",
    "settle_labor_payment": "labor",
    "get_weather_forecast": "weather",
    "web_search": "external_network",
}

_READ_SKILLS = {
    "get_cost_analytics",
    "get_cost_summary",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_operation_work_orders",
}

_WRITE_CONFIRM_SKILLS = {
    "create_cost_record",
    "create_crop_cycle",
    "create_crop_template",
    "create_operation_work_order",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
}

_CONTEXT_DEPENDENCIES = {
    "get_cost_analytics": ["ledger"],
    "get_cost_summary": ["ledger"],
    "create_cost_record": ["ledger"],
    "settle_debt": ["ledger"],
    "create_crop_cycle": ["crop_templates"],
    "create_crop_template": [],
    "get_crop_cycle_info": ["active_cycles"],
    "update_crop_cycle": ["active_cycles"],
    "update_crop_stage": ["active_cycles"],
    "get_recent_farm_logs": ["farm_logs", "active_cycles"],
    "log_farm_activity": ["active_cycles"],
    "get_farm_status": ["farm_status"],
    "create_operation_work_order": ["active_cycles", "planting_units", "workers"],
    "get_operation_work_orders": ["active_cycles", "planting_units", "workers"],
    "update_operation_work_order": ["active_cycles", "planting_units", "workers"],
    "get_labor_payables": ["workers", "unpaid_labor"],
    "settle_labor_payment": ["workers", "unpaid_labor"],
    "get_weather_forecast": ["user_settings", "weather"],
    "web_search": ["external_network"],
}
```

Add this helper:

```python
def _known_skill_defaults(skill_name: str) -> dict[str, Any] | None:
    if skill_name not in _SKILL_DOMAINS:
        return None

    if skill_name in _WRITE_CONFIRM_SKILLS:
        permission_level = SkillPermissionLevel.WRITE_CONFIRM
        risk_level = SkillRiskLevel.MEDIUM
        evaluation_tags = ["write", _SKILL_DOMAINS[skill_name]]
        confirmation_schema = _DEFAULT_WRITE_CONFIRMATION
    elif skill_name in _EXTERNAL_NETWORK_SKILLS:
        permission_level = SkillPermissionLevel.EXTERNAL_NETWORK
        risk_level = SkillRiskLevel.LOW
        evaluation_tags = ["read", "external_network"]
        confirmation_schema = ConfirmationSchema()
    else:
        permission_level = SkillPermissionLevel.READ
        risk_level = SkillRiskLevel.LOW
        evaluation_tags = ["read", _SKILL_DOMAINS[skill_name]]
        confirmation_schema = ConfirmationSchema()

    disabled_reason = _DISABLED_SKILL_REASONS.get(skill_name, "")
    enabled = disabled_reason == ""
    return {
        "permission_level": permission_level,
        "risk_level": risk_level,
        "context_dependencies": _CONTEXT_DEPENDENCIES.get(skill_name, []),
        "cache_invalidation": get_cache_groups_for_skill(skill_name),
        "confirmation_schema": confirmation_schema,
        "evaluation_tags": evaluation_tags,
        "business_domain": _SKILL_DOMAINS[skill_name],
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "production_ready": enabled,
        "metadata_incomplete": False,
    }
```

Replace `get_skill_metadata()` with:

```python
def get_skill_metadata(skill: Any) -> SkillMetadata:
    """从 Skill 读取 metadata，缺失时提供兼容默认值。"""
    skill_name = _get_skill_name(skill)
    known_defaults = _known_skill_defaults(skill_name)
    raw_metadata = _call_metadata(skill)

    if known_defaults is not None:
        merged = dict(known_defaults)
        if raw_metadata is not None:
            merged.update(raw_metadata)
        metadata = SkillMetadata.model_validate(merged)
        metadata.metadata_incomplete = False
        return metadata

    if raw_metadata is not None:
        metadata = SkillMetadata.model_validate(raw_metadata)
        metadata.metadata_incomplete = False
        metadata.production_ready = metadata.enabled
        return metadata

    if skill_name in WRITE_SKILLS:
        return SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            risk_level=SkillRiskLevel.MEDIUM,
            cache_invalidation=get_cache_groups_for_skill(skill_name),
            confirmation_schema=_DEFAULT_WRITE_CONFIRMATION,
            evaluation_tags=["write"],
            business_domain="general",
            enabled=True,
            disabled_reason="",
            production_ready=False,
            metadata_incomplete=True,
        )

    permission_level = (
        SkillPermissionLevel.EXTERNAL_NETWORK
        if skill_name in _EXTERNAL_NETWORK_SKILLS
        else SkillPermissionLevel.READ
    )
    return SkillMetadata(
        permission_level=permission_level,
        risk_level=SkillRiskLevel.LOW,
        evaluation_tags=["read"],
        business_domain="general",
        enabled=True,
        disabled_reason="",
        production_ready=False,
        metadata_incomplete=True,
    )
```

- [ ] **Step 4: Update settings exports if imports fail**

If the test run reports import errors for `SkillMetadata.model_dump` or Pydantic serialization, run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python - <<'PY'
from app.agent.skills.metadata import SkillMetadata
print(SkillMetadata().model_dump(mode="json"))
PY
```

Expected: prints JSON-like metadata containing `business_domain`, `enabled`, `disabled_reason`, and `production_ready`. If this command passes, no settings export change is needed.

- [ ] **Step 5: Update admin config tests**

In `backend/tests/api/test_admin_config.py`, extend metadata assertions in `TestListSkills.test_returns_skill_list`:

```python
assert "business_domain" in metadata
assert "enabled" in metadata
assert "disabled_reason" in metadata
assert "production_ready" in metadata
```

Add:

```python
def test_returns_disabled_web_search_reason(self, db_session) -> None:
    ensure_admin_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).get("/admin/skills", headers=admin_headers())

    assert resp.status_code == 200
    items = {item["name"]: item for item in resp.json()["items"]}
    metadata = items["web_search"]["metadata"]
    assert metadata["enabled"] is False
    assert metadata["disabled_reason"] == "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"
```

- [ ] **Step 6: Run metadata and admin tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/skills/test_skill_metadata.py tests/api/test_admin_config.py tests/skills/test_skill_runtime_coverage.py -q
```

Expected: PASS for metadata/admin tests. Runtime coverage should now PASS if Task 2 was completed.

- [ ] **Step 7: Commit metadata completion**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/skills/metadata.py backend/tests/skills/test_skill_metadata.py backend/tests/api/test_admin_config.py
git commit -m "feat(skill): 补齐现有 Skill 运行时元数据"
```

### Task 4: Tool Executor Disabled Skill Governance

**Files:**
- Modify: `backend/app/agent/runtime/tool_executor.py`
- Modify: `backend/tests/agent/test_tool_executor_metadata.py`
- Test: `backend/tests/agent/test_tool_executor_metadata.py`

- [ ] **Step 1: Add Tool Executor tests**

In `backend/tests/agent/test_tool_executor_metadata.py`, add:

```python
@pytest.mark.asyncio
async def test_disabled_skill_rejects_before_validation_and_records_disabled_trace():
    class RequiredArgs(BaseModel):
        required_name: str

    tool = SimpleNamespace(
        name="web_search",
        args_schema=RequiredArgs,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK,
            enabled=False,
            disabled_reason="SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用",
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "web_search",
                        "args": {},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch(
        "app.agent.runtime.tool_executor.get_collector",
        return_value=collector,
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "工具调用失败：web_search 当前已禁用。"
    tool.ainvoke.assert_not_awaited()
    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "disabled",
        "permission_level": "external_network",
        "disabled_reason": "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用",
    }


@pytest.mark.asyncio
async def test_external_network_permission_executes_when_enabled():
    tool = SimpleNamespace(
        name="external_lookup",
        args_schema=None,
        ainvoke=AsyncMock(return_value="外部查询结果"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK,
            enabled=True,
            business_domain="external_network",
            production_ready=True,
        ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "external_lookup",
                        "args": {"query": "番茄价格"},
                    }
                ],
            )
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch(
        "app.agent.runtime.tool_executor.get_collector",
        return_value=collector,
    ):
        result = await _parallel_tool_node(state)

    assert result["messages"][0].content == "外部查询结果"
    tool.ainvoke.assert_awaited_once_with({"query": "番茄价格"})
    assert collector.record.call_args.kwargs["output_data"] == {
        "status": "success",
        "reply_preview": "外部查询结果",
        "permission_level": "external_network",
    }
```

- [ ] **Step 2: Run executor tests to verify failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/agent/test_tool_executor_metadata.py -q
```

Expected: FAIL because disabled Skill rejection does not yet exist and validation currently runs before disabled rejection.

- [ ] **Step 3: Update permission decision model**

In `backend/app/agent/runtime/tool_executor.py`, replace `_PermissionDecision` with:

```python
@dataclass(frozen=True)
class _PermissionDecision:
    permission_level: str
    requires_confirmation: bool = False
    reject_message: str | None = None
    trace_status: str = "rejected"
    disabled_reason: str = ""
```

At the start of the `if metadata is not None:` block inside `_permission_decision()`, add:

```python
        enabled = getattr(metadata, "enabled", True)
        if enabled is False:
            disabled_reason = str(getattr(metadata, "disabled_reason", ""))
            return _PermissionDecision(
                permission_level=getattr(
                    getattr(metadata, "permission_level", None),
                    "value",
                    getattr(metadata, "permission_level", SkillPermissionLevel.READ.value),
                ),
                reject_message=f"工具调用失败：{skill_name} 当前已禁用。",
                trace_status="disabled",
                disabled_reason=disabled_reason,
            )
```

- [ ] **Step 4: Move rejection before parameter validation**

Inside `_call_one()` in `backend/app/agent/runtime/tool_executor.py`, move the `if permission_decision.reject_message is not None:` block so it appears immediately after:

```python
permission_decision = _permission_decision(tool, name, state)
```

Replace that rejection block with:

```python
        if permission_decision.reject_message is not None:
            logger.warning(
                "Skill 权限拒绝 | name=%s | permission_level=%s | status=%s",
                name,
                permission_decision.permission_level,
                permission_decision.trace_status,
            )
            output_data = {
                "status": permission_decision.trace_status,
                "permission_level": permission_decision.permission_level,
            }
            if permission_decision.disabled_reason:
                output_data["disabled_reason"] = permission_decision.disabled_reason
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=output_data,
                duration_ms=0,
            )
            return ToolMessage(
                content=permission_decision.reject_message,
                tool_call_id=tool_call_id,
            )
```

Remove the old identical rejection block that appears after Pydantic validation.

- [ ] **Step 5: Run executor tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/agent/test_tool_executor_metadata.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit executor governance**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/runtime/tool_executor.py backend/tests/agent/test_tool_executor_metadata.py
git commit -m "feat(agent): 增加禁用 Skill 执行治理"
```

### Task 5: Skill Tenant Isolation Gate

**Files:**
- Modify: `backend/app/agent/skills/farm-status/scripts/main.py`
- Modify: `backend/app/agent/skills/crop-cycle/scripts/main.py`
- Modify: `backend/tests/skills/test_farm_status.py`
- Modify: `backend/tests/skills/test_crop_cycle.py`
- Test: `backend/tests/skills/test_skill_context_isolation.py`
- Test: `backend/tests/skills/test_farm_status.py`
- Test: `backend/tests/skills/test_crop_cycle.py`

- [ ] **Step 1: Add farm status isolation test**

In `backend/tests/skills/test_farm_status.py`, replace tests that expect default `farm_id=1` when context is missing with this failure test:

```python
@pytest.mark.asyncio
async def test_missing_context_farm_id_fails_without_db_access(mock_session):
    context = MagicMock(spec=[])

    result = await FarmStatusSkill().execute({}, context)

    assert result.status == ResultStatus.ERROR
    assert "缺少可信农场上下文" in result.reply
    mock_session.assert_not_called()
```

If the file currently patches `SessionLocal` under a different fixture name, keep the existing fixture and assert that the patched DB factory was not called.

- [ ] **Step 2: Add crop cycle isolation test**

In `backend/tests/skills/test_crop_cycle.py`, add a missing-context test using the existing import style in that file. The required test body is:

```python
@pytest.mark.asyncio
async def test_missing_context_farm_id_fails_without_db_access():
    with patch("app.agent.skills.crop-cycle.scripts.main.SessionLocal") as session:
        result = await CropCycleSkill().execute({}, SkillContext())

    assert result.status == ResultStatus.ERROR
    assert "缺少可信农场上下文" in result.reply
    session.assert_not_called()
```

If direct `patch()` with the hyphenated module path is invalid, load the module the same way the existing test file loads `CropCycleSkill`, then patch that loaded module's `SessionLocal`. The required assertion remains: missing context returns `ResultStatus.ERROR` and does not open `SessionLocal`.

- [ ] **Step 3: Run isolation tests to verify failures**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/skills/test_farm_status.py tests/skills/test_crop_cycle.py tests/skills/test_skill_context_isolation.py -q
```

Expected: FAIL because `farm-status` and `crop-cycle` still default to farm 1.

- [ ] **Step 4: Fix farm-status trusted context**

In `backend/app/agent/skills/farm-status/scripts/main.py`, import `require_farm_context`:

```python
from app.agent.skills.context import require_farm_context
```

Replace:

```python
farm_id = getattr(context, "farm_id", 1) or 1
```

with:

```python
farm_id, context_error = require_farm_context(context, "查询农场状态")
if context_error is not None:
    return context_error
```

- [ ] **Step 5: Fix crop-cycle trusted context**

In `backend/app/agent/skills/crop-cycle/scripts/main.py`, import `require_farm_context`:

```python
from app.agent.skills.context import require_farm_context
```

Replace:

```python
farm_id = getattr(context, "farm_id", 1) or 1
```

with:

```python
farm_id, context_error = require_farm_context(context, "查询茬口")
if context_error is not None:
    return context_error
```

- [ ] **Step 6: Run isolation tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest tests/skills/test_farm_status.py tests/skills/test_crop_cycle.py tests/skills/test_skill_context_isolation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit tenant isolation fixes**

```bash
cd /Users/ljn/Documents/demo/explore
git add \
  backend/app/agent/skills/farm-status/scripts/main.py \
  backend/app/agent/skills/crop-cycle/scripts/main.py \
  backend/tests/skills/test_farm_status.py \
  backend/tests/skills/test_crop_cycle.py
git commit -m "fix(skill): 强制使用可信农场上下文"
```

### Task 6: Phase 1 Verification And OpenSpec Sync

**Files:**
- Modify: `openspec/changes/complete-llm-skill-coverage/tasks.md`
- Test: backend targeted tests
- Test: OpenSpec validation

- [ ] **Step 1: Run Phase 1 targeted tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m pytest \
  tests/skills/test_skill_context_isolation.py \
  tests/skills/test_farm_status.py \
  tests/skills/test_crop_cycle.py \
  tests/skills/test_skill_runtime_coverage.py \
  tests/test_tool_selector.py \
  tests/test_tool_chain_map.py \
  tests/skills/test_skill_metadata.py \
  tests/api/test_admin_config.py \
  tests/agent/test_tool_executor_metadata.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting and lint**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format .
```

Expected: `ruff check` exits 0 and `ruff format` reports files left unchanged or reformatted.

- [ ] **Step 3: Run OpenSpec validation**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
openspec validate complete-llm-skill-coverage --strict
```

Expected: `Change 'complete-llm-skill-coverage' is valid`.

- [ ] **Step 4: Mark completed Phase 1 OpenSpec tasks**

In `openspec/changes/complete-llm-skill-coverage/tasks.md`, check only these tasks:

```markdown
- [x] 1.1 Add a registered Skill coverage audit test that loads the runtime Skill registry and reports enabled Skill names, permission levels, metadata completeness, selector coverage, chain policy coverage, and evaluation coverage.
- [x] 1.2 Add a selector parity test that fails when an enabled registered Skill has no selector trigger, intent classifier target, or explicit fallback policy.
- [x] 1.3 Add a chain policy parity test that fails when an enabled registered Skill has no `TOOL_CHAIN_MAP` entry or equivalent registry-derived chain policy.
- [x] 1.4 Add a write permission audit that fails when any write Skill is missing explicit `permission_level=write_confirm` metadata.
- [x] 1.5 Add disabled Skill audit support so intentionally disabled Skills require a machine-readable disabled reason.
- [x] 2.1 Extend `tool_selector` triggers for `create_operation_work_order`, `get_operation_work_orders`, `get_labor_payables`, `settle_labor_payment`, and `update_operation_work_order`.
- [x] 2.2 Add selector regression tests for work order creation, work order query, work order correction, labor payable query, and labor payment settlement.
- [x] 2.3 Update `TOOL_CHAIN_MAP` or equivalent chain policy for all 19 registered Skills.
- [x] 2.4 Add chain expansion tests for labor and work order query Skills that require farm or planting context.
- [x] 2.5 Ensure `web_search` disabled state is represented as configuration or registry metadata rather than selector-only hardcoding.
- [x] 3.1 Add metadata fields for business domain, enabled state, disabled reason, and production readiness.
- [x] 3.2 Complete metadata for all existing read Skills, including context dependencies and evaluation tags.
- [x] 3.3 Complete metadata for all existing write Skills, including confirmation schema and cache invalidation groups.
- [x] 3.4 Complete metadata for `external_network` Skills, including enablement and failure policy.
- [x] 3.5 Update `/admin/skills` output tests to include coverage and enablement metadata.
- [x] 4.1 Add Tool Executor disabled-Skill rejection before parameter validation or external access.
- [x] 4.2 Add Tool Executor external-network permission checks using configuration and metadata.
- [x] 4.3 Preserve explicit metadata precedence over legacy write Skill fallback.
- [x] 4.4 Add trace output for disabled Skill rejection with status `disabled` and disabled reason.
- [x] 4.5 Add tests for disabled `web_search`, enabled external-network execution, admin rejection, and metadata precedence.
- [x] 9.1 Run `openspec validate complete-llm-skill-coverage --strict`.
- [x] 9.2 Run backend targeted tests for skills, agent runtime, selector, evaluation, diagnostics, and admin config.
- [x] 9.3 Run `ruff check . && ruff format .` from the backend directory.
```

Leave tasks 3.6, 5.x, 6.x, 7.x, 8.x, 9.4, and 9.5 unchecked for later phases.

- [ ] **Step 5: Commit Phase 1 completion**

```bash
cd /Users/ljn/Documents/demo/explore
git add \
  backend/app/agent/tool_selector.py \
  backend/app/agent/skills/metadata.py \
  backend/app/agent/skills/farm-status/scripts/main.py \
  backend/app/agent/skills/crop-cycle/scripts/main.py \
  backend/app/agent/runtime/tool_executor.py \
  backend/tests/test_tool_selector.py \
  backend/tests/test_tool_chain_map.py \
  backend/tests/skills/test_skill_runtime_coverage.py \
  backend/tests/skills/test_skill_context_isolation.py \
  backend/tests/skills/test_farm_status.py \
  backend/tests/skills/test_crop_cycle.py \
  backend/tests/skills/test_skill_metadata.py \
  backend/tests/api/test_admin_config.py \
  backend/tests/agent/test_tool_executor_metadata.py \
  openspec/changes/complete-llm-skill-coverage/tasks.md
git commit -m "feat(skill): 完成现有 Skill 运行时覆盖闭环"
```

## Self-Review

Spec coverage:

- `Registered Skill selection coverage`: Task 2 adds selector tests and implementation for work order, labor payable, work order update, and labor settlement.
- `Selection audit parity with registry`: Task 1 adds selector and chain audit tests.
- `Skill 权限分级`: Task 4 keeps metadata precedence and adds disabled/external-network behavior.
- `Disabled Skill execution behavior`: Task 4 covers disabled rejection and trace status.
- `Enabled Skill metadata completeness`: Task 3 adds metadata fields and known-skill defaults for the 19 existing Skills.
- `Skill enablement state`: Task 3 exposes enabled/disabled reason through metadata and admin API tests.
- `Skill domain taxonomy`: Task 3 adds domain mapping and tests labor domain.
- 用户隔离硬门槛：Task 5 removes farm 1 fallback from read Skills that still had it and requires trusted `SkillContext`.

Known phase gaps:

- Coverage matrix requirements are not implemented in this plan; they belong to Phase 2.
- New ordinary-user missing Skills are not implemented in this plan; they belong to Phase 2 after the matrix.
- Admin Skill expansion and sensitive capability policy are not implemented in this plan; they belong to Phase 3.
- Evaluation report aggregation and diagnostics root-cause classification are not implemented in this plan; they belong to a later plan after coverage matrix data exists.
- Full cross-user database fixture coverage for every existing Skill is not completed in this plan; Task 5 closes known farm 1 fallback paths and preserves existing per-Skill isolation tests for write operations.

Placeholder scan:

- This plan contains no `TBD`, `TODO`, or unspecified implementation steps.
- Every code-changing task includes the exact file and concrete code block to add or replace.

Type consistency:

- `SkillMetadata.business_domain`, `enabled`, `disabled_reason`, and `production_ready` are introduced in Task 3 and used by Task 2 selector helper, Task 3 admin API tests, and Task 4 Tool Executor tests.
- `_PermissionDecision.trace_status` and `_PermissionDecision.disabled_reason` are introduced before use in Tool Executor trace output.
