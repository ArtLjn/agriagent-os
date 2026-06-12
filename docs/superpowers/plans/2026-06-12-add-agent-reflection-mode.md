# Add Agent Reflection Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 farm-manager Agent 增加触发式 Reflection 控制层，在写操作、pending plan、工具结果和最终回复关键节点做结构化自检。

**Architecture:** 新增 `app.agent.reflector` 边界承载模型、策略、规则检查和 trace 记录；Runtime 与 Executor 只调用窄接口，不把反思逻辑继续塞进 `runtime/nodes.py` 或 pending action 旧入口。MVP 采用规则优先、触发式检查，避免每轮请求都增加 LLM critic 成本。

**Tech Stack:** FastAPI backend、LangGraph/LangChain messages、Pydantic v2、SQLAlchemy 测试夹具、pytest、unittest.mock。

---

## File Structure

Create:
- `backend/app/agent/reflector/__init__.py`：导出反思服务和模型。
- `backend/app/agent/reflector/models.py`：定义 `ReflectionTrigger`、`ReflectionDecision`、`ReflectionIssue`、`ReflectionResult`。
- `backend/app/agent/reflector/checks.py`：实现纯函数规则检查。
- `backend/app/agent/reflector/policy.py`：根据配置和请求状态判断是否触发反思。
- `backend/app/agent/reflector/service.py`：组合 policy/checks，并负责 trace 事件。
- `backend/tests/agent/test_reflector.py`：覆盖模型、策略和规则检查。
- `backend/tests/agent/test_reflection_pending_flow.py`：覆盖 pending action / pending plan 接入。
- `backend/tests/agent/test_reflection_runtime_flow.py`：覆盖工具后回复检查和低风险跳过。

Modify:
- `backend/app/core/settings/models.py`：新增 `ReflectionConfig`。
- `backend/app/core/settings/settings.py`：在 `Settings` 中挂载 `reflection` 配置。
- `backend/app/core/config.py`、`backend/app/core/settings/__init__.py`：导出 `ReflectionConfig`。
- `backend/app/agent/runtime/tool_executor.py`：pending action / pending plan 展示前调用反思服务。
- `backend/app/agent/executor/pending_actions.py`：用户确认执行前调用反思服务，写操作 fail-closed。
- `backend/app/agent/runtime/nodes.py`：工具结果到最终回复阶段调用反思服务，保持调用点薄。
- `backend/app/evaluation/diagnostics.py`：汇总 `reflection_check` 事件。
- `backend/tests/evaluation/test_diagnostics.py`：覆盖 reflection 诊断输出。

Do not modify:
- `.git/` 内部文件。
- 根目录临时脚本。
- 现有 API 契约。

---

### Task 1: Reflection Core Models And Checks

**Files:**
- Create: `backend/app/agent/reflector/__init__.py`
- Create: `backend/app/agent/reflector/models.py`
- Create: `backend/app/agent/reflector/checks.py`
- Create: `backend/app/agent/reflector/policy.py`
- Create: `backend/app/agent/reflector/service.py`
- Modify: `backend/app/core/settings/models.py`
- Modify: `backend/app/core/settings/settings.py`
- Modify: `backend/app/core/settings/__init__.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/agent/test_reflector.py`

- [ ] **Step 1: Write failing model and rule tests**

Create `backend/tests/agent/test_reflector.py`:

```python
from langchain_core.messages import ToolMessage

from app.agent.reflector import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
    ReflectorService,
)
from app.agent.reflector.checks import (
    check_required_tool_missing,
    check_tool_failure_success_reply,
    check_write_plan_consistency,
)
from app.agent.reflector.policy import ReflectionPolicy
from app.infra.pending_actions import PendingPlanStep


def test_reflection_result_serializes_trace_payload() -> None:
    issue = ReflectionIssue(
        code="missing_required_param",
        severity=ReflectionSeverity.BLOCKER,
        message="写操作缺少 amount 参数。",
        evidence={"field": "amount"},
        suggested_decision=ReflectionDecision.ASK_CLARIFICATION,
    )

    result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        decision=ReflectionDecision.ASK_CLARIFICATION,
        issues=[issue],
        reason="写操作参数不完整。",
    )

    assert result.has_blocker is True
    assert result.to_trace_payload() == {
        "trigger": "pre_write_plan",
        "decision": "ask_clarification",
        "reason": "写操作参数不完整。",
        "issues": [
            {
                "code": "missing_required_param",
                "severity": "blocker",
                "message": "写操作缺少 amount 参数。",
                "evidence": {"field": "amount"},
                "suggested_decision": "ask_clarification",
            }
        ],
        "metadata": {},
    }


def test_policy_skips_low_risk_chitchat() -> None:
    policy = ReflectionPolicy(enabled=True)

    assert policy.should_run(
        trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
        intent="greeting",
        selected_tools=[],
        tool_messages=[],
    ) is False


def test_policy_runs_for_write_trigger() -> None:
    policy = ReflectionPolicy(enabled=True)

    assert policy.should_run(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        intent="agent",
        selected_tools=["create_cost_record"],
        tool_messages=[],
    ) is True


def test_check_write_plan_consistency_blocks_empty_params() -> None:
    result = check_write_plan_consistency(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={},
        confirmation_text="确认记账：化肥 200元",
    )

    assert result.decision == ReflectionDecision.ASK_CLARIFICATION
    assert result.issues[0].code == "empty_write_params"


def test_check_write_plan_consistency_blocks_confirmation_mismatch() -> None:
    result = check_write_plan_consistency(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥"},
        confirmation_text="确认记账：化肥 300元",
    )

    assert result.decision == ReflectionDecision.BLOCK_WRITE
    assert result.issues[0].code == "confirmation_param_mismatch"
    assert result.issues[0].evidence["field"] == "amount"


def test_check_tool_failure_success_reply_rewrites_success_claim() -> None:
    tool_message = ToolMessage(
        content="工具调用失败：数据库连接失败",
        tool_call_id="tc-cost",
    )

    result = check_tool_failure_success_reply(
        tool_messages=[tool_message],
        final_text="已执行：记账成功。",
    )

    assert result.decision == ReflectionDecision.FALLBACK_RESPONSE
    assert result.issues[0].code == "failed_tool_success_reply"


def test_check_required_tool_missing_requests_retry() -> None:
    result = check_required_tool_missing(
        selected_tools=["get_farm_status"],
        tool_calls=[],
        final_text="你现在有两个茬口。",
    )

    assert result.decision == ReflectionDecision.REQUIRE_TOOL
    assert result.issues[0].code == "required_tool_missing"


def test_reflector_service_passes_valid_pending_plan() -> None:
    service = ReflectorService(policy=ReflectionPolicy(enabled=True))
    steps = [
        PendingPlanStep(
            step_id="create_worker",
            step_index=0,
            tool_name="manage_workers",
            params={"action": "create", "name": "王大妈"},
            depends_on=[],
        ),
        PendingPlanStep(
            step_id="create_work_order",
            step_index=1,
            tool_name="create_operation_work_order",
            params={"workers": "王大妈", "operation_type": "采收"},
            depends_on=["create_worker"],
        ),
    ]

    result = service.check_pending_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        steps=steps,
        confirmation_text="请确认将执行 2 步：创建工人，创建作业单",
    )

    assert result.decision == ReflectionDecision.PASS
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.agent.reflector'`.

- [ ] **Step 3: Implement settings model**

Modify `backend/app/core/settings/models.py` by adding:

```python
class ReflectionConfig(BaseModel):
    enabled: bool = True
    pre_write_plan: bool = True
    pre_execution: bool = True
    post_tool_result: bool = True
    fallback_guard: bool = True
```

Modify the import/export blocks in `backend/app/core/settings/settings.py`, `backend/app/core/settings/__init__.py`, and `backend/app/core/config.py` to include `ReflectionConfig`.

In `backend/app/core/settings/settings.py`, add this field to `Settings`:

```python
reflection: ReflectionConfig = ReflectionConfig()
```

- [ ] **Step 4: Implement reflection models**

Create `backend/app/agent/reflector/models.py`:

```python
"""Agent Reflection 结构化模型。"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReflectionTrigger(StrEnum):
    PRE_WRITE_PLAN = "pre_write_plan"
    PRE_EXECUTION = "pre_execution"
    POST_TOOL_RESULT = "post_tool_result"
    PRE_FINAL_RESPONSE = "pre_final_response"
    FALLBACK_GUARD = "fallback_guard"


class ReflectionDecision(StrEnum):
    PASS = "pass"
    ASK_CLARIFICATION = "ask_clarification"
    REQUIRE_TOOL = "require_tool"
    BLOCK_WRITE = "block_write"
    RETRY_GENERATION = "retry_generation"
    FALLBACK_RESPONSE = "fallback_response"


class ReflectionSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ReflectionIssue(BaseModel):
    code: str
    severity: ReflectionSeverity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_decision: ReflectionDecision = ReflectionDecision.PASS

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "suggested_decision": self.suggested_decision.value,
        }


class ReflectionResult(BaseModel):
    trigger: ReflectionTrigger
    decision: ReflectionDecision = ReflectionDecision.PASS
    issues: list[ReflectionIssue] = Field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == ReflectionSeverity.BLOCKER for issue in self.issues)

    @classmethod
    def passed(
        cls,
        trigger: ReflectionTrigger,
        *,
        reason: str = "反思检查通过。",
        metadata: dict[str, Any] | None = None,
    ) -> "ReflectionResult":
        return cls(
            trigger=trigger,
            decision=ReflectionDecision.PASS,
            reason=reason,
            metadata=metadata or {},
        )

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger.value,
            "decision": self.decision.value,
            "reason": self.reason,
            "issues": [issue.to_trace_payload() for issue in self.issues],
            "metadata": self.metadata,
        }
```

- [ ] **Step 5: Implement policy**

Create `backend/app/agent/reflector/policy.py`:

```python
"""Agent Reflection 触发策略。"""

from langchain_core.messages import ToolMessage

from app.agent.reflector.models import ReflectionTrigger


class ReflectionPolicy:
    """判断某个节点是否需要运行 Reflection。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        pre_write_plan: bool = True,
        pre_execution: bool = True,
        post_tool_result: bool = True,
        fallback_guard: bool = True,
    ) -> None:
        self.enabled = enabled
        self.pre_write_plan = pre_write_plan
        self.pre_execution = pre_execution
        self.post_tool_result = post_tool_result
        self.fallback_guard = fallback_guard

    def should_run(
        self,
        *,
        trigger: ReflectionTrigger,
        intent: str = "agent",
        selected_tools: list[str] | None = None,
        tool_messages: list[ToolMessage] | None = None,
    ) -> bool:
        if not self.enabled:
            return False

        if trigger == ReflectionTrigger.PRE_WRITE_PLAN:
            return self.pre_write_plan
        if trigger == ReflectionTrigger.PRE_EXECUTION:
            return self.pre_execution
        if trigger in {
            ReflectionTrigger.POST_TOOL_RESULT,
            ReflectionTrigger.PRE_FINAL_RESPONSE,
        }:
            if not self.post_tool_result:
                return False
            return bool(selected_tools or tool_messages)
        if trigger == ReflectionTrigger.FALLBACK_GUARD:
            return self.fallback_guard

        return intent not in {"greeting", "chitchat"}
```

- [ ] **Step 6: Implement checks**

Create `backend/app/agent/reflector/checks.py`:

```python
"""Agent Reflection 规则检查。"""

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from langchain_core.messages import ToolMessage

from app.agent.reflector.models import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.infra.pending_actions import PendingPlanStep, is_write_skill

_SUCCESS_HINTS = ("已执行", "成功", "已创建", "已保存", "已更新", "完成")
_FAILURE_HINTS = ("失败", "错误", "异常", "validation", "参数校验失败", "工具调用失败")
_BUSINESS_FACT_HINTS = ("有", "共", "当前", "总", "金额", "茬口", "工人", "欠款")


def check_write_plan_consistency(
    *,
    trigger: ReflectionTrigger,
    skill_name: str,
    params: dict,
    confirmation_text: str,
) -> ReflectionResult:
    if is_write_skill(skill_name) and not params:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.ASK_CLARIFICATION,
            code="empty_write_params",
            message=f"{skill_name} 是写操作，但参数为空。",
            evidence={"skill_name": skill_name},
        )

    mismatch = _find_confirmation_mismatch(params, confirmation_text)
    if mismatch is not None:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            code="confirmation_param_mismatch",
            message="确认文案与待执行参数不一致。",
            evidence=mismatch,
        )

    return ReflectionResult.passed(trigger)


def check_pending_plan_consistency(
    *,
    trigger: ReflectionTrigger,
    steps: list[PendingPlanStep],
    confirmation_text: str,
) -> ReflectionResult:
    if not steps:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            code="empty_pending_plan",
            message="待确认计划没有步骤。",
            evidence={},
        )

    step_ids = {step.step_id for step in steps}
    for step in steps:
        if is_write_skill(step.tool_name) and not step.params:
            return _single_issue(
                trigger=trigger,
                decision=ReflectionDecision.ASK_CLARIFICATION,
                code="empty_write_params",
                message=f"{step.tool_name} 是写操作，但参数为空。",
                evidence={"step_id": step.step_id, "tool_name": step.tool_name},
            )
        missing_deps = [dep for dep in step.depends_on if dep not in step_ids]
        if missing_deps:
            return _single_issue(
                trigger=trigger,
                decision=ReflectionDecision.BLOCK_WRITE,
                code="missing_plan_dependency",
                message="待确认计划存在不存在的依赖步骤。",
                evidence={"step_id": step.step_id, "missing_depends_on": missing_deps},
            )

    if str(len(steps)) not in confirmation_text:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            code="plan_confirmation_step_count_mismatch",
            message="确认文案中的步骤数量与实际计划不一致。",
            evidence={"steps": len(steps), "confirmation_text": confirmation_text[:120]},
        )

    return ReflectionResult.passed(trigger)


def check_tool_failure_success_reply(
    *,
    tool_messages: list[ToolMessage],
    final_text: str,
) -> ReflectionResult:
    failed = [
        str(message.content or "")
        for message in tool_messages
        if _contains_any(str(message.content or ""), _FAILURE_HINTS)
    ]
    if failed and _contains_any(final_text, _SUCCESS_HINTS):
        return _single_issue(
            trigger=ReflectionTrigger.POST_TOOL_RESULT,
            decision=ReflectionDecision.FALLBACK_RESPONSE,
            code="failed_tool_success_reply",
            message="工具结果失败，但最终回复声称成功。",
            evidence={"failed_tool_message": failed[0][:160], "final_text": final_text[:160]},
        )
    return ReflectionResult.passed(ReflectionTrigger.POST_TOOL_RESULT)


def check_required_tool_missing(
    *,
    selected_tools: list[str],
    tool_calls: list[dict],
    final_text: str,
) -> ReflectionResult:
    if not selected_tools:
        return ReflectionResult.passed(ReflectionTrigger.PRE_FINAL_RESPONSE)
    if tool_calls:
        return ReflectionResult.passed(ReflectionTrigger.PRE_FINAL_RESPONSE)
    if not _contains_any(final_text, _BUSINESS_FACT_HINTS):
        return ReflectionResult.passed(ReflectionTrigger.PRE_FINAL_RESPONSE)

    return _single_issue(
        trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
        decision=ReflectionDecision.REQUIRE_TOOL,
        code="required_tool_missing",
        message="Router 已选择工具，但回复直接给出了需要真实数据支撑的业务事实。",
        evidence={"selected_tools": selected_tools, "final_text": final_text[:160]},
    )


def _find_confirmation_mismatch(
    params: dict,
    confirmation_text: str,
) -> dict | None:
    for field in ("amount", "unit_price", "default_unit_price", "paid_amount"):
        value = params.get(field)
        if value in (None, ""):
            continue
        normalized = _normalize_decimal(value)
        if normalized is None:
            continue
        if _decimal_text_present(normalized, confirmation_text):
            continue
        return {
            "field": field,
            "param_value": str(value),
            "confirmation_text": confirmation_text[:160],
        }
    return None


def _normalize_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError):
        return None


def _decimal_text_present(value: Decimal, text: str) -> bool:
    candidates = {str(value), format(value, "f").rstrip("0").rstrip(".")}
    return any(candidate and candidate in text for candidate in candidates)


def _contains_any(text: str, hints: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in hints)


def _single_issue(
    *,
    trigger: ReflectionTrigger,
    decision: ReflectionDecision,
    code: str,
    message: str,
    evidence: dict,
) -> ReflectionResult:
    return ReflectionResult(
        trigger=trigger,
        decision=decision,
        reason=message,
        issues=[
            ReflectionIssue(
                code=code,
                severity=ReflectionSeverity.BLOCKER,
                message=message,
                evidence=evidence,
                suggested_decision=decision,
            )
        ],
    )
```

- [ ] **Step 7: Implement service and exports**

Create `backend/app/agent/reflector/service.py`:

```python
"""Agent Reflection 服务入口。"""

import time

from langchain_core.messages import ToolMessage

from app.agent.reflector.checks import (
    check_pending_plan_consistency,
    check_required_tool_missing,
    check_tool_failure_success_reply,
    check_write_plan_consistency,
)
from app.agent.reflector.models import ReflectionResult, ReflectionTrigger
from app.agent.reflector.policy import ReflectionPolicy
from app.core.config import settings
from app.infra.pending_actions import PendingPlanStep
from app.infra.trace_collector import get_collector


class ReflectorService:
    """组合反思策略、规则检查和 trace 记录。"""

    def __init__(self, policy: ReflectionPolicy | None = None) -> None:
        config = settings.reflection
        self.policy = policy or ReflectionPolicy(
            enabled=config.enabled,
            pre_write_plan=config.pre_write_plan,
            pre_execution=config.pre_execution,
            post_tool_result=config.post_tool_result,
            fallback_guard=config.fallback_guard,
        )

    def check_write_plan(
        self,
        *,
        trigger: ReflectionTrigger,
        skill_name: str,
        params: dict,
        confirmation_text: str,
        trace_metadata: dict | None = None,
    ) -> ReflectionResult:
        if not self.policy.should_run(
            trigger=trigger,
            selected_tools=[skill_name],
            tool_messages=[],
        ):
            return ReflectionResult.passed(trigger, reason="反思策略跳过。")
        return self._record(
            check_write_plan_consistency(
                trigger=trigger,
                skill_name=skill_name,
                params=params,
                confirmation_text=confirmation_text,
            ),
            trace_metadata=trace_metadata,
        )

    def check_pending_plan(
        self,
        *,
        trigger: ReflectionTrigger,
        steps: list[PendingPlanStep],
        confirmation_text: str,
        trace_metadata: dict | None = None,
    ) -> ReflectionResult:
        if not self.policy.should_run(
            trigger=trigger,
            selected_tools=[step.tool_name for step in steps],
            tool_messages=[],
        ):
            return ReflectionResult.passed(trigger, reason="反思策略跳过。")
        return self._record(
            check_pending_plan_consistency(
                trigger=trigger,
                steps=steps,
                confirmation_text=confirmation_text,
            ),
            trace_metadata=trace_metadata,
        )

    def check_tool_response(
        self,
        *,
        tool_messages: list[ToolMessage],
        final_text: str,
        selected_tools: list[str] | None = None,
        tool_calls: list[dict] | None = None,
        trace_metadata: dict | None = None,
    ) -> ReflectionResult:
        if not self.policy.should_run(
            trigger=ReflectionTrigger.POST_TOOL_RESULT,
            selected_tools=selected_tools or [],
            tool_messages=tool_messages,
        ):
            return ReflectionResult.passed(
                ReflectionTrigger.POST_TOOL_RESULT,
                reason="反思策略跳过。",
            )
        failure_result = check_tool_failure_success_reply(
            tool_messages=tool_messages,
            final_text=final_text,
        )
        if failure_result.decision.value != "pass":
            return self._record(failure_result, trace_metadata=trace_metadata)
        missing_tool_result = check_required_tool_missing(
            selected_tools=selected_tools or [],
            tool_calls=tool_calls or [],
            final_text=final_text,
        )
        return self._record(missing_tool_result, trace_metadata=trace_metadata)

    def _record(
        self,
        result: ReflectionResult,
        *,
        trace_metadata: dict | None = None,
    ) -> ReflectionResult:
        if trace_metadata:
            result.metadata.update(trace_metadata)
        start = time.time()
        get_collector().record(
            node_type="reflection_check",
            node_name=result.trigger.value,
            input_data=result.metadata,
            output_data=result.to_trace_payload(),
            start_time=start,
            end_time=time.time(),
        )
        return result
```

Create `backend/app/agent/reflector/__init__.py`:

```python
"""Agent Reflection 控制层。"""

from app.agent.reflector.models import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.agent.reflector.service import ReflectorService

__all__ = [
    "ReflectionDecision",
    "ReflectionIssue",
    "ReflectionResult",
    "ReflectionSeverity",
    "ReflectionTrigger",
    "ReflectorService",
]
```

- [ ] **Step 8: Run core tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflector.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit core reflection module**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/reflector backend/app/core/settings backend/app/core/config.py backend/tests/agent/test_reflector.py
git commit -m "feat: add agent reflection core"
```

Expected: commit succeeds.

---

### Task 2: Pre-Write Reflection For Pending Action And Pending Plan

**Files:**
- Modify: `backend/app/agent/runtime/tool_executor.py`
- Test: `backend/tests/agent/test_reflection_pending_flow.py`

- [ ] **Step 1: Write failing pending flow tests**

Create `backend/tests/agent/test_reflection_pending_flow.py`:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import _parallel_tool_node
from app.agent.reflector import ReflectionDecision, ReflectionResult, ReflectionTrigger
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import PENDING_MARKER, get_pending, get_pending_plan


def _write_tool(name: str):
    return SimpleNamespace(
        name=name,
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=[],
        ),
    )


@pytest.mark.asyncio
async def test_reflection_blocks_pending_action_before_confirmation() -> None:
    state = {
        "messages": [
            HumanMessage(content="记一笔账"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-cost",
                        "name": "create_cost_record",
                        "args": {},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "reflect-action",
    }

    block_result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        decision=ReflectionDecision.ASK_CLARIFICATION,
        reason="写操作参数不完整。",
    )

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[_write_tool("create_cost_record")],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
        patch(
            "app.agent.runtime.tool_executor.ReflectorService"
        ) as mock_reflector_cls,
    ):
        mock_reflector_cls.return_value.check_write_plan.return_value = block_result
        result = await _parallel_tool_node(state)

    assert "写操作参数不完整" in result["messages"][0].content
    assert PENDING_MARKER not in result["messages"][0].content
    assert get_pending(1, session_id="reflect-action") is None


@pytest.mark.asyncio
async def test_reflection_allows_pending_action_when_passed() -> None:
    state = {
        "messages": [
            HumanMessage(content="昨天买了200块化肥"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-cost",
                        "name": "create_cost_record",
                        "args": {"amount": 200, "category": "化肥"},
                    }
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "reflect-action-pass",
    }

    pass_result = ReflectionResult.passed(ReflectionTrigger.PRE_WRITE_PLAN)

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[_write_tool("create_cost_record")],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
        patch(
            "app.agent.runtime.tool_executor.ReflectorService"
        ) as mock_reflector_cls,
    ):
        mock_reflector_cls.return_value.check_write_plan.return_value = pass_result
        result = await _parallel_tool_node(state)

    assert PENDING_MARKER in result["messages"][0].content
    assert get_pending(1, session_id="reflect-action-pass") is not None


@pytest.mark.asyncio
async def test_reflection_blocks_pending_plan_before_storage() -> None:
    from app.agent.router import SkillRouter

    message = "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了"
    router_decision = SkillRouter().route(
        message,
        [
            SimpleNamespace(name="manage_workers", description=""),
            SimpleNamespace(name="create_operation_work_order", description=""),
        ],
    )
    state = {
        "messages": [
            HumanMessage(content=message),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "tc-worker", "name": "manage_workers", "args": {"name": "王大妈"}},
                    {
                        "id": "tc-order",
                        "name": "create_operation_work_order",
                        "args": {"workers": ["王大妈"], "operation_type": "采收"},
                    },
                ],
            ),
        ],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "session_id": "reflect-plan",
        "router_decision": router_decision,
    }

    block_result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        decision=ReflectionDecision.BLOCK_WRITE,
        reason="计划依赖异常。",
    )

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[_write_tool("manage_workers"), _write_tool("create_operation_work_order")],
        ),
        patch("app.agent.runtime.tool_executor.get_collector"),
        patch(
            "app.agent.runtime.tool_executor.ReflectorService"
        ) as mock_reflector_cls,
    ):
        mock_reflector_cls.return_value.check_pending_plan.return_value = block_result
        result = await _parallel_tool_node(state)

    assert "计划依赖异常" in result["messages"][0].content
    assert get_pending_plan(1, session_id="reflect-plan") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_pending_flow.py -v
```

Expected: FAIL because `app.agent.runtime.tool_executor.ReflectorService` is not imported and pending flows do not call reflection.

- [ ] **Step 3: Import reflection types in tool executor**

Modify `backend/app/agent/runtime/tool_executor.py` imports:

```python
from app.agent.reflector import ReflectionDecision, ReflectionTrigger, ReflectorService
```

- [ ] **Step 4: Add helper for block messages**

Add near `_normalize_text` in `backend/app/agent/runtime/tool_executor.py`:

```python
def _reflection_block_tool_message(
    result,
    tool_call_id: str,
) -> ToolMessage:
    """把 Reflection 阻断结果转成工具消息，阻止 pending 写入落库。"""
    reason = result.reason or "写操作未通过安全检查。"
    return ToolMessage(
        content=f"这条操作还没有执行。{reason}",
        tool_call_id=tool_call_id,
    )
```

- [ ] **Step 5: Gate pending plan storage**

In `_pending_plan_tool_message`, before `store_pending_plan(...)`, insert:

```python
    confirm_text = build_plan_confirm_message(pending_steps)
    reflection = ReflectorService().check_pending_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        steps=pending_steps,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "tool_names": sorted(step_tool_names),
        },
    )
    if reflection.decision != ReflectionDecision.PASS:
        return [
            _reflection_block_tool_message(reflection, tool_call["id"])
            for tool_call in tool_calls
        ]
```

Then remove the later duplicate `confirm_text = build_plan_confirm_message(pending_steps)` line so the existing message construction reuses `confirm_text`.

- [ ] **Step 6: Gate pending action storage**

In `_parallel_tool_node`, inside the `if permission_decision.requires_confirmation:` block, after `confirmation_context = build_confirmation_context(...)` and before `store_pending(...)`, insert:

```python
            confirm = build_confirm_message(
                name,
                confirmation_args,
                original_input=original_input,
            )
            reflection = ReflectorService().check_write_plan(
                trigger=ReflectionTrigger.PRE_WRITE_PLAN,
                skill_name=name,
                params=execution_args,
                confirmation_text=confirm,
                trace_metadata={
                    "farm_id": farm_id,
                    "session_id": session_id,
                    "tool_name": name,
                },
            )
            if reflection.decision != ReflectionDecision.PASS:
                collector.record(
                    node_type="skill_call",
                    node_name=name,
                    input_data=execution_args,
                    output_data={
                        "status": "reflection_blocked",
                        "reflection": reflection.to_trace_payload(),
                    },
                    duration_ms=0,
                )
                return _reflection_block_tool_message(reflection, tool_call_id)
```

Then change the later confirmation message assignment from:

```python
            confirm = build_confirm_message(
                name,
                confirmation_args,
                original_input=original_input,
            )
```

to reuse the `confirm` variable already computed.

- [ ] **Step 7: Run pending flow tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_pending_flow.py tests/agent/test_pending_plan_executor.py::test_runtime_tool_flow_stores_pending_plan_without_invoking_write_tools -v
```

Expected: PASS.

- [ ] **Step 8: Commit pre-write integration**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/runtime/tool_executor.py backend/tests/agent/test_reflection_pending_flow.py
git commit -m "feat: check reflection before pending writes"
```

Expected: commit succeeds.

---

### Task 3: Pre-Execution Reflection For Confirmed Pending Writes

**Files:**
- Modify: `backend/app/agent/executor/pending_actions.py`
- Test: `backend/tests/agent/test_reflection_pending_flow.py`

- [ ] **Step 1: Add failing pre-execution tests**

Append to `backend/tests/agent/test_reflection_pending_flow.py`:

```python
from app.agent.executor.pending_actions import handle_pending_action
from app.infra.pending_actions import store_pending, store_pending_plan


@pytest.mark.asyncio
async def test_reflection_blocks_confirmed_pending_action_execution() -> None:
    store_pending(
        farm_id=1,
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥"},
        original_input="昨天买了200块化肥",
        session_id="reflect-exec-action",
    )
    block_result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        decision=ReflectionDecision.BLOCK_WRITE,
        reason="执行前检查未通过。",
    )

    with (
        patch(
            "app.agent.executor.pending_actions.ReflectorService"
        ) as mock_reflector_cls,
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
    ):
        mock_reflector_cls.return_value.check_write_plan.return_value = block_result
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
            session_id="reflect-exec-action",
        )

    assert decision.handled is True
    assert decision.reply == "执行失败：执行前检查未通过。"
    mock_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_reflection_blocks_confirmed_pending_plan_execution() -> None:
    store_pending_plan(
        farm_id=1,
        session_id="reflect-exec-plan",
        raw_user_input="创建工人并安排作业",
        router_decision={"selected_tools": ["manage_workers", "create_operation_work_order"]},
        steps=[
            {
                "step_id": "create_worker",
                "tool_name": "manage_workers",
                "params": {"action": "create", "name": "王大妈"},
            },
            {
                "step_id": "create_work_order",
                "tool_name": "create_operation_work_order",
                "params": {"workers": "王大妈", "operation_type": "采收"},
                "depends_on": ["create_worker"],
            },
        ],
    )
    block_result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        decision=ReflectionDecision.BLOCK_WRITE,
        reason="计划执行前检查未通过。",
    )

    with (
        patch(
            "app.agent.executor.pending_actions.ReflectorService"
        ) as mock_reflector_cls,
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
    ):
        mock_reflector_cls.return_value.check_pending_plan.return_value = block_result
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            farm_uid="farm-uid-1",
            session_id="reflect-exec-plan",
        )

    assert decision.handled is True
    assert decision.reply == "执行失败：计划执行前检查未通过。"
    mock_execute.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_pending_flow.py::test_reflection_blocks_confirmed_pending_action_execution tests/agent/test_reflection_pending_flow.py::test_reflection_blocks_confirmed_pending_plan_execution -v
```

Expected: FAIL because executor does not import or call `ReflectorService`.

- [ ] **Step 3: Import reflection service in executor**

Modify imports in `backend/app/agent/executor/pending_actions.py`:

```python
from app.agent.reflector import ReflectionDecision, ReflectionTrigger, ReflectorService
```

- [ ] **Step 4: Add pre-execution helper functions**

Add before `_confirm_pending`:

```python
def _ensure_pending_action_reflection_passed(
    *,
    farm_id: int,
    pending: PendingAction,
    session_id: str | None,
) -> str | None:
    confirm_text = build_confirm_message(
        pending.skill_name,
        pending.params,
        original_input=pending.original_input,
    )
    reflection = ReflectorService().check_write_plan(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        skill_name=pending.skill_name,
        params=pending.params,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "action_id": pending.action_id,
            "tool_name": pending.skill_name,
        },
    )
    if reflection.decision == ReflectionDecision.PASS:
        return None
    return reflection.reason or "执行前检查未通过。"


def _ensure_pending_plan_reflection_passed(
    *,
    farm_id: int,
    plan: PendingPlan,
    session_id: str | None,
) -> str | None:
    confirm_text = build_plan_confirm_message(plan.steps)
    reflection = ReflectorService().check_pending_plan(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        steps=plan.steps,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "plan_id": plan.plan_id,
            "tool_names": [step.tool_name for step in plan.steps],
        },
    )
    if reflection.decision == ReflectionDecision.PASS:
        return None
    return reflection.reason or "计划执行前检查未通过。"
```

- [ ] **Step 5: Gate `_confirm_pending`**

At the top of `_confirm_pending`, before `_execute_write_skill(...)`, insert:

```python
    reflection_error = _ensure_pending_action_reflection_passed(
        farm_id=farm_id,
        pending=pending,
        session_id=session_id,
    )
    if reflection_error is not None:
        return PendingActionDecision.failed(f"执行失败：{reflection_error}")
```

- [ ] **Step 6: Gate `_confirm_pending_plan`**

At the top of `_confirm_pending_plan`, before `results: list[str] = []`, insert:

```python
    reflection_error = _ensure_pending_plan_reflection_passed(
        farm_id=farm_id,
        plan=plan,
        session_id=session_id,
    )
    if reflection_error is not None:
        return PendingActionDecision.failed(f"执行失败：{reflection_error}")
```

- [ ] **Step 7: Run pre-execution tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_pending_flow.py tests/agent/test_pending_plan_executor.py::test_handle_pending_plan_confirm_executes_steps_in_order tests/agent/test_pending_action_executor.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit pre-execution integration**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/executor/pending_actions.py backend/tests/agent/test_reflection_pending_flow.py
git commit -m "feat: guard pending execution with reflection"
```

Expected: commit succeeds.

---

### Task 4: Post-Tool Reflection Before Final Response

**Files:**
- Modify: `backend/app/agent/runtime/nodes.py`
- Test: `backend/tests/agent/test_reflection_runtime_flow.py`

- [ ] **Step 1: Write failing runtime reflection tests**

Create `backend/tests/agent/test_reflection_runtime_flow.py`:

```python
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.reflector import ReflectionDecision, ReflectionResult, ReflectionTrigger
from app.agent.runtime.nodes import _llm_node


@pytest.mark.asyncio
async def test_post_tool_reflection_replaces_success_reply_after_tool_failure() -> None:
    tool_msg = ToolMessage(
        content="工具调用失败：数据库连接失败",
        tool_call_id="tc-cost",
    )
    block_result = ReflectionResult(
        trigger=ReflectionTrigger.POST_TOOL_RESULT,
        decision=ReflectionDecision.FALLBACK_RESPONSE,
        reason="工具结果失败，但回复声称成功。",
    )

    with patch("app.agent.runtime.nodes.ReflectorService") as mock_reflector_cls:
        mock_reflector_cls.return_value.check_tool_response.return_value = block_result
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="记账"), tool_msg],
                "farm_id": 1,
                "intent": "agent",
                "selected_tool_names": ["create_cost_record"],
            }
        )

    reply = result["messages"][0].content
    assert reply == "这次工具执行没有成功：工具结果失败，但回复声称成功。"


@pytest.mark.asyncio
async def test_post_tool_reflection_skips_low_risk_direct_pending_path() -> None:
    pending_msg = ToolMessage(
        content="[PENDING_ACTION] 确认记账：化肥 200元，确认吗？",
        tool_call_id="tc-cost",
    )

    with patch("app.agent.runtime.nodes.ReflectorService") as mock_reflector_cls:
        result = await _llm_node(
            {
                "messages": [pending_msg],
                "farm_id": 1,
                "intent": "agent",
            }
        )

    assert "确认记账" in result["messages"][0].content
    mock_reflector_cls.assert_not_called()


@pytest.mark.asyncio
async def test_required_tool_missing_reflection_returns_safe_message() -> None:
    final_msg = AIMessage(content="你现在有两个茬口。", tool_calls=[])
    block_result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
        decision=ReflectionDecision.REQUIRE_TOOL,
        reason="需要调用工具获取真实数据。",
    )

    with patch("app.agent.runtime.nodes.ReflectorService") as mock_reflector_cls:
        mock_reflector_cls.return_value.check_tool_response.return_value = block_result
        checked = _apply_final_reflection(
            response=final_msg,
            tool_msgs=[],
            selected_tool_names=["get_farm_status"],
            original_tool_calls=[],
        )

    assert checked.content == "这次还没有查到真实数据，请换个说法再试一次。"
```

Also add this import at the top of the test file:

```python
from app.agent.runtime.nodes import _apply_final_reflection
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_runtime_flow.py -v
```

Expected: FAIL because `_apply_final_reflection` does not exist and `_llm_node` does not import `ReflectorService`.

- [ ] **Step 3: Import reflection in runtime nodes**

Modify `backend/app/agent/runtime/nodes.py` imports:

```python
from app.agent.reflector import ReflectionDecision, ReflectorService
```

- [ ] **Step 4: Add final reflection helper**

Add before `_llm_node` in `backend/app/agent/runtime/nodes.py`:

```python
def _apply_final_reflection(
    *,
    response: AIMessage,
    tool_msgs: list[ToolMessage],
    selected_tool_names: list[str],
    original_tool_calls: list[dict],
) -> AIMessage:
    """最终回复前的轻量 Reflection 检查。"""
    final_text = str(response.content or "")
    reflection = ReflectorService().check_tool_response(
        tool_messages=tool_msgs,
        final_text=final_text,
        selected_tools=selected_tool_names,
        tool_calls=original_tool_calls,
        trace_metadata={
            "selected_tools": selected_tool_names,
            "tool_message_count": len(tool_msgs),
        },
    )
    if reflection.decision == ReflectionDecision.PASS:
        return response
    if reflection.decision == ReflectionDecision.FALLBACK_RESPONSE:
        return AIMessage(
            content=f"这次工具执行没有成功：{reflection.reason}",
            response_metadata=response.response_metadata,
            id=response.id,
        )
    if reflection.decision == ReflectionDecision.REQUIRE_TOOL:
        return AIMessage(
            content="这次还没有查到真实数据，请换个说法再试一次。",
            response_metadata=response.response_metadata,
            id=response.id,
        )
    return response
```

- [ ] **Step 5: Call helper before logging final output**

In `_llm_node`, after the empty-content fallback block and before `logger.info("LLM 直接回复...")`, insert:

```python
            response = _apply_final_reflection(
                response=response,
                tool_msgs=normal_msgs,
                selected_tool_names=selected_tool_names,
                original_tool_calls=list(response.tool_calls or []),
            )
            content = response.content or ""
```

Keep the existing pending/direct-return early returns unchanged so they do not instantiate `ReflectorService`.

- [ ] **Step 6: Export helper for tests**

Update `__all__` in `backend/app/agent/runtime/nodes.py`:

```python
__all__ = [
    "_llm_node",
    "_parallel_tool_node",
    "_should_continue",
    "_apply_final_reflection",
]
```

- [ ] **Step 7: Run runtime reflection tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/agent/test_reflection_runtime_flow.py tests/test_mixed_tool_results.py tests/agent/test_runtime_router_binding.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit runtime reflection integration**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/runtime/nodes.py backend/tests/agent/test_reflection_runtime_flow.py
git commit -m "feat: reflect on final agent responses"
```

Expected: commit succeeds.

---

### Task 5: Reflection Trace And Diagnostics

**Files:**
- Modify: `backend/app/evaluation/diagnostics.py`
- Test: `backend/tests/core/test_trace_collector.py`
- Test: `backend/tests/evaluation/test_diagnostics.py`

- [ ] **Step 1: Add trace collector test**

Append to `backend/tests/core/test_trace_collector.py`:

```python
    def test_record_reflection_check_does_not_accumulate_token_stats(self) -> None:
        """reflection_check 只入 trace，不累计 token 统计。"""
        init_trace(farm_id=1, user_id="u1", call_type="chat")
        from app.infra.trace_collector import TraceCollector

        collector = TraceCollector.__new__(TraceCollector)
        collector._dao = MagicMock()
        collector._dao.record = MagicMock()
        collector._dao.accumulate_token_stats = MagicMock()
        collector.record(
            node_type="reflection_check",
            node_name="pre_write_plan",
            input_data={"tool_name": "create_cost_record"},
            output_data={"decision": "pass"},
        )

        collector._dao.record.assert_called_once()
        collector._dao.accumulate_token_stats.assert_not_called()
```

- [ ] **Step 2: Add diagnostics failing test**

Append to `backend/tests/evaluation/test_diagnostics.py`:

```python
def test_diagnostic_service_summarizes_reflection_checks() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="reflection_check",
                node_name="pre_write_plan",
                input_data={"tool_name": "create_cost_record"},
                output_data={
                    "trigger": "pre_write_plan",
                    "decision": "block_write",
                    "reason": "确认文案与待执行参数不一致。",
                    "issues": [
                        {
                            "code": "confirmation_param_mismatch",
                            "severity": "blocker",
                        }
                    ],
                },
            )
        ],
    )

    assert report.reflection_checks == [
        {
            "trigger": "pre_write_plan",
            "decision": "block_write",
            "reason": "确认文案与待执行参数不一致。",
            "issues": [
                {
                    "code": "confirmation_param_mismatch",
                    "severity": "blocker",
                }
            ],
            "input": {"tool_name": "create_cost_record"},
        }
    ]
    assert report.reflection_diagnostic == {
        "blocked": True,
        "decisions": ["block_write"],
        "issue_codes": ["confirmation_param_mismatch"],
    }
```

- [ ] **Step 3: Run tests to verify diagnostics fail**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/core/test_trace_collector.py::TestTraceCollector::test_record_reflection_check_does_not_accumulate_token_stats tests/evaluation/test_diagnostics.py::test_diagnostic_service_summarizes_reflection_checks -v
```

Expected: trace collector test PASS; diagnostics test FAIL because report has no reflection fields.

- [ ] **Step 4: Extend diagnostic report dataclass**

Modify `SkillDiagnosticReport` in `backend/app/evaluation/diagnostics.py`:

```python
    reflection_checks: list[dict[str, Any]] = field(default_factory=list)
    reflection_diagnostic: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 5: Parse reflection records**

In `build_report`, add this branch near other `elif record.node_type...` branches:

```python
            elif record.node_type == "reflection_check":
                report.reflection_checks.append(self._reflection_event(record))
```

After `report.context_dependency_diagnostic = ...`, add:

```python
        report.reflection_diagnostic = self._diagnose_reflection(report)
```

- [ ] **Step 6: Add reflection helper methods**

Add to `SkillDiagnosticService`:

```python
    @staticmethod
    def _reflection_event(record: Any) -> dict[str, Any]:
        output_data = record.output_data or {}
        return {
            "trigger": output_data.get("trigger") or record.node_name,
            "decision": output_data.get("decision") or "",
            "reason": output_data.get("reason") or "",
            "issues": output_data.get("issues") or [],
            "input": record.input_data or {},
        }

    @staticmethod
    def _diagnose_reflection(report: SkillDiagnosticReport) -> dict[str, Any]:
        decisions = [
            item.get("decision")
            for item in report.reflection_checks
            if item.get("decision")
        ]
        issue_codes = []
        for item in report.reflection_checks:
            for issue in item.get("issues") or []:
                code = issue.get("code")
                if code:
                    issue_codes.append(code)
        unique_decisions = sorted(set(decisions))
        unique_issue_codes = sorted(set(issue_codes))
        return {
            "blocked": any(
                decision in {"block_write", "ask_clarification", "require_tool"}
                for decision in decisions
            ),
            "decisions": unique_decisions,
            "issue_codes": unique_issue_codes,
        }
```

- [ ] **Step 7: Run diagnostics tests**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/core/test_trace_collector.py tests/evaluation/test_diagnostics.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit diagnostics**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/evaluation/diagnostics.py backend/tests/core/test_trace_collector.py backend/tests/evaluation/test_diagnostics.py
git commit -m "feat: expose reflection diagnostics"
```

Expected: commit succeeds.

---

### Task 6: Architecture Guards And Documentation

**Files:**
- Modify: `backend/tests/test_agent_runtime_architecture.py`
- Modify: `docs/architecture/overview.md`
- Modify: `openspec/changes/add-agent-reflection-mode/tasks.md`

- [ ] **Step 1: Add architecture guard test**

Append to `backend/tests/test_agent_runtime_architecture.py`:

```python
def test_reflection_logic_lives_in_reflector_boundary():
    """Reflection 策略和检查逻辑不得散落在 Runtime 或 Executor。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    guarded_files = [
        app_dir / "agent" / "runtime" / "nodes.py",
        app_dir / "agent" / "runtime" / "tool_executor.py",
        app_dir / "agent" / "executor" / "pending_actions.py",
    ]
    forbidden_names = {
        "ReflectionIssue",
        "ReflectionResult",
        "ReflectionPolicy",
        "check_write_plan_consistency",
        "check_pending_plan_consistency",
        "check_tool_failure_success_reply",
    }

    violations = []
    for file_path in guarded_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative_path = file_path.relative_to(app_dir)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name in forbidden_names:
                    violations.append(f"{relative_path}: defines {node.name}")

    assert violations == []
```

- [ ] **Step 2: Run architecture guard**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest tests/test_agent_runtime_architecture.py::test_reflection_logic_lives_in_reflector_boundary -v
```

Expected: PASS.

- [ ] **Step 3: Update architecture overview**

Modify `docs/architecture/overview.md` in the Agent 平台边界 section by adding Reflection:

```markdown
- `agent/reflector/` 负责触发式反思控制、写操作风险检查、工具结果一致性检查和 reflection trace payload；Runtime 和 Executor 只调用反思服务，不内联策略规则。
```

Modify the standard lifecycle block by changing:

```text
  → Executor 并行调用 Skill
  → Response Formatter / SSE 输出回复
```

to:

```text
  → Executor 并行调用 Skill
  → Reflection 检查写入风险、工具结果和最终回复一致性
  → Response Formatter / SSE 输出回复
```

- [ ] **Step 4: Update OpenSpec task checklist**

In `openspec/changes/add-agent-reflection-mode/tasks.md`, mark completed implementation groups as checked only after the corresponding code tasks pass. Do not mark all tasks at once.

- [ ] **Step 5: Commit guards and docs**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/tests/test_agent_runtime_architecture.py docs/architecture/overview.md openspec/changes/add-agent-reflection-mode/tasks.md
git commit -m "docs: document agent reflection boundary"
```

Expected: commit succeeds.

---

### Task 7: Final Verification

**Files:**
- Verify only; no source changes expected unless a command exposes a defect.

- [ ] **Step 1: Run focused reflection suite**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest \
  tests/agent/test_reflector.py \
  tests/agent/test_reflection_pending_flow.py \
  tests/agent/test_reflection_runtime_flow.py \
  tests/evaluation/test_diagnostics.py \
  tests/core/test_trace_collector.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run existing Agent regression tests touched by integration**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
pytest \
  tests/agent/test_pending_plan_executor.py \
  tests/agent/test_pending_action_executor.py \
  tests/agent/test_runtime_router_binding.py \
  tests/test_mixed_tool_results.py \
  tests/test_agent_runtime_architecture.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run architecture scripts**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
bash scripts/check-layer-deps.sh
bash scripts/check-guide-sensor-pairing.sh
```

Expected: both commands exit 0.

- [ ] **Step 4: Run lint if ruff is installed**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
ruff check backend/app/agent/reflector backend/app/agent/runtime backend/app/agent/executor backend/app/evaluation backend/tests/agent backend/tests/evaluation backend/tests/core
ruff format backend/app/agent/reflector backend/app/agent/runtime backend/app/agent/executor backend/app/evaluation backend/tests/agent backend/tests/evaluation backend/tests/core
```

Expected: `ruff check` exits 0 and `ruff format` reports files left formatted.

- [ ] **Step 5: Run OpenSpec status**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
openspec status --change add-agent-reflection-mode --json
```

Expected: JSON contains `"isComplete": true`.

- [ ] **Step 6: Inspect git status**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
git status --short
```

Expected: only intentional files are modified or the tree is clean after commits.

---

## Self-Review

Spec coverage:
- `agent-reflection-control` triggered checks: Tasks 1, 2, 3, 4 cover model, policy, pre-write, pre-execution, post-tool, low-risk skip, and fail-closed write behavior.
- `agent-platform-architecture` lifecycle and boundary: Task 6 adds architecture guard and docs.
- `write-skill-plan-execution` modified requirements: Tasks 2 and 3 add checks before pending display and before confirmed execution.
- Observability and Evaluation: Task 5 records and summarizes `reflection_check` events.

Placeholder scan:
- No `TBD`, deferred implementation, or unspecified test steps remain.
- Each code-changing step includes exact file paths and concrete code blocks.

Type consistency:
- `ReflectionTrigger`, `ReflectionDecision`, `ReflectionIssue`, `ReflectionResult`, `ReflectionSeverity`, and `ReflectorService` names are consistent across tests and implementation steps.
- Runtime and executor integrations both use `ReflectionDecision.PASS` as the allow condition.
