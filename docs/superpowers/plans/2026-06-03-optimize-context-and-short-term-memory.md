# 上下文与短时记忆优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 Agent 上下文从固定四字段注入升级为意图驱动的三层上下文策略，并把 session 短时记忆纳入统一 token 预算。

**Architecture:** 新增 `ContextPolicy` 作为 selector 选择和预算配置入口，`ContextBuilder` 继续负责执行 selector、应用 `TokenBudget` 和记录 trace。短时记忆通过 `MemoryContext` 转成 `ContextBlock`，Agent Runtime 保留旧 `farm_ctx` 兼容变量，同时将 `ContextBundle.render_text()` 作为动态上下文注入 system prompt。

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, LangChain messages, pytest, ruff, OpenSpec.

---

## Scope Check

本计划只实现 OpenSpec change `optimize-context-and-short-term-memory` 的第一阶段：策略、短时记忆 block、Runtime 接入、缓存失效和测试。长期记忆向量检索、LLM 生成会话摘要、外部 tokenizer 依赖不在本阶段实现。

## File Structure

- Create: `backend/app/context/policy.py`  
  负责 `ContextLayer`、`ContextBuildRequest`、`ContextPolicyResult` 和 `ContextPolicy`，只做规则决策，不查库。
- Create: `backend/app/context/invalidation.py`  
  负责统一清理 `FarmContextCache` 和 `PromptCache`。
- Modify: `backend/app/context/models.py`  
  给 `ContextBlock` 增加 `layer`、`intent_tags`、`required_reason`、`cache_scope` 的稳定 metadata 入口，并提供 `with_metadata()`。
- Modify: `backend/app/context/budget.py`  
  增强预算结果记录，标记 required 超预算风险。
- Modify: `backend/app/context/builder.py`  
  支持从 `ContextPolicy` 接收 selector 和预算，并提供 `build_runtime_context_bundle()`。
- Modify: `backend/app/context/selectors/memory.py`  
  支持 `MemoryContext` 输入，输出最近消息、会话摘要、pending action、临时任务状态和长期记忆命中 block。
- Modify: `backend/app/memory/models.py`  
  给 `PendingActionSnapshot` 增加 `expires_at` 和 `is_expired()`。
- Modify: `backend/app/memory/short_term/store.py`  
  读取 pending action 时过滤过期状态。
- Modify: `backend/app/agent/runtime/llm_support.py`  
  新增构建 runtime context bundle 的异步 helper，保留 `_get_farm_context()` 兼容入口。
- Modify: `backend/app/agent/runtime/nodes.py`  
  将动态上下文文本追加到 system prompt，并把 selected tools 传给 context policy。
- Modify: `backend/app/services/cost_service.py`、`backend/app/services/debt_service.py`、`backend/app/services/cycle_service.py`、`backend/app/services/log_service.py`、`backend/app/api/user_settings.py`  
  写操作成功后调用缓存失效 helper。
- Test: `backend/tests/context/test_policy.py`
- Test: `backend/tests/context/test_budget.py`
- Test: `backend/tests/context/test_builder.py`
- Test: `backend/tests/context/test_selectors.py`
- Test: `backend/tests/memory/test_memory_service.py`
- Test: `backend/tests/test_prompt_cache.py`
- Test: `backend/tests/test_graph_user_setting.py`

---

### Task 1: ContextPolicy 策略入口

**Files:**
- Create: `backend/app/context/policy.py`
- Modify: `backend/app/context/__init__.py`
- Test: `backend/tests/context/test_policy.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/context/test_policy.py` 新增：

```python
"""ContextPolicy 策略测试。"""

from app.context.policy import ContextBuildRequest, ContextLayer, ContextPolicy
from app.context.selectors import LedgerSelector, WeatherSelector


def _selector_names(result):
    return [selector.__class__.__name__ for selector in result.selectors]


def test_chat_policy_uses_hot_context_only_for_chitchat():
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="chat",
            selected_tool_names=[],
            farm_id=1,
            user_id="user-1",
            session_id="session-1",
        )
    )

    names = _selector_names(result)

    assert result.max_tokens == 512
    assert result.enabled_layers == {ContextLayer.HOT, ContextLayer.WORKING}
    assert "FarmSelector" in names
    assert "UserSettingsSelector" in names
    assert "CycleSelector" in names
    assert "LedgerSelector" not in names
    assert "WeatherSelector" not in names


def test_policy_enables_ledger_for_cost_tool():
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="query",
            selected_tool_names=["get_cost_summary"],
            farm_id=1,
            user_id="user-1",
            session_id="session-1",
        )
    )

    assert any(isinstance(selector, LedgerSelector) for selector in result.selectors)
    assert result.max_tokens == 900


def test_policy_enables_weather_for_weather_tool():
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="query",
            selected_tool_names=["get_weather_forecast"],
            farm_id=1,
            user_id="user-1",
            session_id="session-1",
        )
    )

    assert any(isinstance(selector, WeatherSelector) for selector in result.selectors)
    assert ContextLayer.RETRIEVAL in result.enabled_layers
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_policy.py -v
```

Expected: FAIL，错误包含 `ModuleNotFoundError: No module named 'app.context.policy'`。

- [ ] **Step 3: 实现 `policy.py`**

创建 `backend/app/context/policy.py`：

```python
"""Context 构建策略。"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.context.builder import ContextSelector
from app.context.selectors import (
    ConversationSelector,
    CycleSelector,
    FarmSelector,
    LedgerSelector,
    MemorySelector,
    RetrievalSelector,
    UserSettingsSelector,
    WeatherSelector,
)


class ContextLayer(StrEnum):
    """上下文分层。"""

    HOT = "hot"
    WORKING = "working"
    RETRIEVAL = "retrieval"


@dataclass(frozen=True, slots=True)
class ContextBuildRequest:
    """一次上下文构建请求。"""

    intent: str
    selected_tool_names: list[str]
    farm_id: int
    user_id: str | None = None
    session_id: str | None = None
    include_retrieval: bool = False


@dataclass(frozen=True, slots=True)
class ContextPolicyResult:
    """ContextPolicy 的选择结果。"""

    selectors: list[ContextSelector]
    max_tokens: int
    enabled_layers: set[ContextLayer] = field(default_factory=set)


class ContextPolicy:
    """根据意图和工具选择上下文 selector。"""

    LEDGER_TOOLS = {"get_cost_summary", "get_cost_analytics", "settle_debt"}
    WEATHER_TOOLS = {"get_weather_forecast"}
    FARM_TOOLS = {"get_farm_status", "get_crop_cycle_info"}

    def resolve(self, request: ContextBuildRequest) -> ContextPolicyResult:
        selected = set(request.selected_tool_names)
        selectors: list[ContextSelector] = [
            FarmSelector(),
            UserSettingsSelector(),
            CycleSelector(),
            MemorySelector(),
            ConversationSelector(),
        ]
        layers = {ContextLayer.HOT, ContextLayer.WORKING}
        max_tokens = 512

        if selected & self.LEDGER_TOOLS:
            selectors.append(LedgerSelector())
            layers.add(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        if selected & self.WEATHER_TOOLS:
            selectors.append(WeatherSelector())
            layers.add(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        if selected & self.FARM_TOOLS or request.intent in {"agent", "advice"}:
            layers.add(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        if request.include_retrieval:
            selectors.append(RetrievalSelector())
            layers.add(ContextLayer.RETRIEVAL)

        return ContextPolicyResult(
            selectors=selectors,
            max_tokens=max_tokens,
            enabled_layers=layers,
        )


__all__ = [
    "ContextBuildRequest",
    "ContextLayer",
    "ContextPolicy",
    "ContextPolicyResult",
]
```

更新 `backend/app/context/__init__.py`：

```python
"""Context 工程模块。"""

from app.context.builder import ContextBuilder
from app.context.budget import TokenBudget
from app.context.models import ContextBlock, ContextBundle
from app.context.policy import ContextBuildRequest, ContextLayer, ContextPolicy

__all__ = [
    "ContextBlock",
    "ContextBundle",
    "ContextBuilder",
    "ContextBuildRequest",
    "ContextLayer",
    "ContextPolicy",
    "TokenBudget",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_policy.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/context/policy.py backend/app/context/__init__.py backend/tests/context/test_policy.py
git commit -m "feat: add context policy"
```

---

### Task 2: ContextBlock 元数据与预算 trace

**Files:**
- Modify: `backend/app/context/models.py`
- Modify: `backend/app/context/budget.py`
- Test: `backend/tests/context/test_budget.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/context/test_budget.py`：

```python
def test_block_summary_includes_layer_and_cache_scope_metadata() -> None:
    block = ContextBlock(
        key="farm",
        source="farm",
        purpose="热上下文",
        content="农场：默认农场",
        priority=90,
        required=True,
        metadata={
            "layer": "hot",
            "intent_tags": ["chat"],
            "required_reason": "identity",
            "cache_scope": "farm",
        },
    )

    summary = block.summary()

    assert summary["layer"] == "hot"
    assert summary["intent_tags"] == ["chat"]
    assert summary["required_reason"] == "identity"
    assert summary["cache_scope"] == "farm"


def test_required_block_over_budget_is_marked_in_bundle_metadata() -> None:
    block = ContextBlock(
        key="system",
        source="prompt",
        purpose="系统规则",
        content="x" * 200,
        priority=100,
        token_estimate=120,
        required=True,
    )

    bundle = TokenBudget(max_tokens=30).apply([block])

    assert bundle.blocks == [block]
    assert bundle.metadata["over_budget_required_blocks"] == ["system"]
    assert bundle.metadata["budget_exceeded"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_budget.py -v
```

Expected: FAIL，错误包含缺少 `layer` 或缺少 `over_budget_required_blocks`。

- [ ] **Step 3: 扩展 `ContextBlock.summary()`**

在 `backend/app/context/models.py` 的 `ContextBlock` 中加入方法：

```python
    def with_metadata(self, **metadata: Any) -> "ContextBlock":
        """返回合并 metadata 的 block 副本。"""
        return ContextBlock(
            key=self.key,
            source=self.source,
            purpose=self.purpose,
            content=self.content,
            priority=self.priority,
            token_estimate=self.token_estimate,
            required=self.required,
            compressible=self.compressible,
            min_tokens=self.min_tokens,
            ttl_seconds=self.ttl_seconds,
            metadata={**self.metadata, **metadata},
            is_compressed=self.is_compressed,
            reason=self.reason,
        )
```

把 `summary()` 改为：

```python
    def summary(self) -> dict[str, Any]:
        """输出 trace 友好的摘要。"""
        return {
            "key": self.key,
            "source": self.source,
            "purpose": self.purpose,
            "priority": self.priority,
            "token_estimate": self.token_estimate or 0,
            "required": self.required,
            "compressed": self.is_compressed,
            "reason": self.reason,
            "layer": self.metadata.get("layer", ""),
            "intent_tags": self.metadata.get("intent_tags", []),
            "required_reason": self.metadata.get("required_reason", ""),
            "cache_scope": self.metadata.get("cache_scope", ""),
        }
```

- [ ] **Step 4: 扩展 `TokenBudget.apply()`**

把 `backend/app/context/budget.py` 的 `apply()` 替换为：

```python
    def apply(self, blocks: list[ContextBlock]) -> ContextBundle:
        """应用预算并返回 bundle。"""
        kept: list[ContextBlock] = []
        compressed: list[ContextBlock] = []
        dropped: list[ContextBlock] = []
        required_over_budget: list[str] = []
        used = 0

        ordered = sorted(blocks, key=lambda block: (-block.priority, block.key))
        for block in ordered:
            tokens = block.token_estimate or 0
            if used + tokens <= self.max_tokens:
                kept.append(block)
                used += tokens
                continue

            if block.required:
                kept.append(block)
                used += tokens
                required_over_budget.append(block.key)
                continue

            remaining = self.max_tokens - used
            if block.compressible and remaining >= block.min_tokens:
                compact = block.compressed_copy(remaining)
                kept.append(compact)
                compressed.append(compact)
                used += compact.token_estimate or 0
                continue

            dropped.append(block.with_reason("token_budget_exceeded"))

        return ContextBundle(
            blocks=kept,
            token_budget=self.max_tokens,
            token_estimate=used,
            compressed_blocks=compressed,
            dropped_blocks=dropped,
            metadata={
                "budget_exceeded": used > self.max_tokens,
                "over_budget_required_blocks": required_over_budget,
            },
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_budget.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/context/models.py backend/app/context/budget.py backend/tests/context/test_budget.py
git commit -m "feat: enrich context budget trace"
```

---

### Task 3: MemorySelector 支持短时记忆视图

**Files:**
- Modify: `backend/app/memory/models.py`
- Modify: `backend/app/memory/short_term/store.py`
- Modify: `backend/app/context/selectors/memory.py`
- Test: `backend/tests/memory/test_memory_service.py`
- Test: `backend/tests/context/test_selectors.py`

- [ ] **Step 1: 写 pending action 过期测试**

追加到 `backend/tests/memory/test_memory_service.py`：

```python
from datetime import UTC, datetime, timedelta


async def test_expired_pending_action_is_not_returned():
    service = InMemoryMemoryService()
    expired = PendingActionSnapshot(
        action_id="act-expired",
        name="create_cost",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    await service.short_term.set_pending_action(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        pending_action=expired,
    )

    context = await service.build_context("user-1", 1, "session-1")

    assert context.pending_action is None
```

- [ ] **Step 2: 写 MemorySelector 测试**

追加到 `backend/tests/context/test_selectors.py`：

```python
from app.memory.models import MemoryContext, MemoryMessage, PendingActionSnapshot


def test_memory_selector_builds_short_term_blocks_from_memory_context() -> None:
    context = MemoryContext(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        recent_messages=[
            MemoryMessage(role="user", content="明天天气怎么样"),
            MemoryMessage(role="assistant", content="我帮你查苏州天气。"),
        ],
        session_summary="用户最近在关注天气。",
        pending_action=PendingActionSnapshot(
            action_id="act-1",
            name="create_cost",
            payload={"amount": 20, "category": "肥料"},
        ),
    )

    blocks = MemorySelector().select(memory_context=context)
    by_key = {block.key: block for block in blocks}

    assert "short_term_recent" in by_key
    assert "明天天气怎么样" in by_key["short_term_recent"].content
    assert by_key["short_term_recent"].metadata["layer"] == "working"
    assert "short_term_summary" in by_key
    assert "pending_action" in by_key
    assert "create_cost" in by_key["pending_action"].content
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/memory/test_memory_service.py::test_expired_pending_action_is_not_returned tests/context/test_selectors.py::test_memory_selector_builds_short_term_blocks_from_memory_context -v
```

Expected: FAIL，错误包含 `expires_at` 参数不存在或 `short_term_recent` block 不存在。

- [ ] **Step 4: 扩展 pending action 模型**

修改 `backend/app/memory/models.py` 的 `PendingActionSnapshot`：

```python
@dataclass(frozen=True)
class PendingActionSnapshot:
    """等待用户确认的写操作快照。"""

    action_id: str
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        """判断 pending action 是否过期。"""
        if self.expires_at is None:
            return False
        current = now or utc_now()
        return current >= self.expires_at
```

- [ ] **Step 5: 过滤过期 pending action**

修改 `backend/app/memory/short_term/store.py` 的 `get_pending_action()`：

```python
    async def get_pending_action(
        self,
        user_id: str,
        farm_id: int,
        session_id: str | None,
    ) -> PendingActionSnapshot | None:
        key = self._key(user_id, farm_id, session_id)
        pending = self._pending_actions.get(key)
        if pending is not None and pending.is_expired():
            self._pending_actions.pop(key, None)
            return None
        return pending
```

- [ ] **Step 6: 实现 MemorySelector**

替换 `backend/app/context/selectors/memory.py`：

```python
"""Memory selector。"""

from app.context.models import ContextBlock
from app.memory.models import MemoryContext


class MemorySelector:
    """选择短时或长期记忆摘要。"""

    def select(
        self,
        memory_context: MemoryContext | None = None,
        memory_summary: str | None = None,
        memory_hits: list[str] | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        if memory_context is not None:
            return self._from_memory_context(memory_context)

        parts = []
        if memory_summary:
            parts.append(memory_summary)
        if memory_hits:
            parts.extend(memory_hits[:5])
        if not parts:
            return []
        return [
            ContextBlock(
                key="memory",
                source="memory",
                purpose="记忆摘要",
                content="\n".join(parts),
                priority=45,
                compressible=True,
                min_tokens=32,
                metadata={"layer": "retrieval"},
            )
        ]

    def _from_memory_context(self, memory_context: MemoryContext) -> list[ContextBlock]:
        blocks: list[ContextBlock] = []
        if memory_context.recent_messages:
            lines = [
                f"{message.role}：{message.content}"
                for message in memory_context.recent_messages
                if message.content
            ]
            blocks.append(
                ContextBlock(
                    key="short_term_recent",
                    source="memory.short_term",
                    purpose="最近对话",
                    content="\n".join(lines),
                    priority=70,
                    compressible=True,
                    min_tokens=48,
                    metadata={"layer": "working", "cache_scope": "session"},
                )
            )

        if memory_context.session_summary:
            blocks.append(
                ContextBlock(
                    key="short_term_summary",
                    source="memory.short_term",
                    purpose="会话摘要",
                    content=memory_context.session_summary,
                    priority=50,
                    compressible=True,
                    min_tokens=32,
                    metadata={"layer": "working", "cache_scope": "session"},
                )
            )

        if memory_context.pending_action:
            pending = memory_context.pending_action
            blocks.append(
                ContextBlock(
                    key="pending_action",
                    source="memory.short_term",
                    purpose="待确认操作",
                    content=f"待确认操作：{pending.name}；参数：{pending.payload}",
                    priority=95,
                    required=True,
                    compressible=False,
                    metadata={
                        "layer": "working",
                        "required_reason": "pending_action",
                        "cache_scope": "session",
                    },
                )
            )

        if memory_context.temporary_task_state:
            state = memory_context.temporary_task_state
            blocks.append(
                ContextBlock(
                    key="temporary_task_state",
                    source="memory.short_term",
                    purpose="临时任务状态",
                    content=f"任务状态：{state.task_id}={state.status}；数据：{state.data}",
                    priority=60,
                    compressible=True,
                    min_tokens=32,
                    metadata={"layer": "working", "cache_scope": "session"},
                )
            )

        return blocks


__all__ = ["MemorySelector"]
```

- [ ] **Step 7: 运行测试确认通过**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/memory/test_memory_service.py tests/context/test_selectors.py -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/memory/models.py backend/app/memory/short_term/store.py backend/app/context/selectors/memory.py backend/tests/memory/test_memory_service.py backend/tests/context/test_selectors.py
git commit -m "feat: add short term memory context blocks"
```

---

### Task 4: ContextBuilder 接入策略和 MemoryContext

**Files:**
- Modify: `backend/app/context/builder.py`
- Test: `backend/tests/context/test_builder.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/context/test_builder.py`：

```python
from app.context.policy import ContextBuildRequest, ContextPolicy
from app.memory.models import MemoryContext, MemoryMessage


def test_builder_builds_runtime_bundle_with_policy_and_memory(db_session) -> None:
    memory_context = MemoryContext(
        user_id="test-user-001",
        farm_id=1,
        session_id="session-1",
        recent_messages=[MemoryMessage(role="user", content="后天呢")],
    )
    builder = ContextBuilder(policy=ContextPolicy(), max_tokens=256)

    bundle = builder.build_runtime_context_bundle(
        db=db_session,
        request=ContextBuildRequest(
            intent="query",
            selected_tool_names=["get_cost_summary"],
            farm_id=1,
            user_id="test-user-001",
            session_id="session-1",
        ),
        memory_context=memory_context,
    )

    keys = [block.key for block in bundle.blocks]

    assert "farm" in keys
    assert "user_settings" in keys
    assert "cycle" in keys
    assert "ledger" in keys
    assert "short_term_recent" in keys
    assert bundle.metadata["policy"]["intent"] == "query"
    assert bundle.metadata["policy"]["selected_tool_names"] == ["get_cost_summary"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_builder.py::test_builder_builds_runtime_bundle_with_policy_and_memory -v
```

Expected: FAIL，错误包含 `unexpected keyword argument 'policy'` 或 `build_runtime_context_bundle` 不存在。

- [ ] **Step 3: 修改 ContextBuilder 构造和方法**

在 `backend/app/context/builder.py` 增加 imports：

```python
from app.context.policy import ContextBuildRequest, ContextPolicy
from app.memory.models import MemoryContext
```

修改 `__init__` 签名和字段：

```python
    def __init__(
        self,
        selectors: list[ContextSelector] | None = None,
        max_tokens: int = 1200,
        trace_collector: Any | None = None,
        policy: ContextPolicy | None = None,
    ) -> None:
        self.selectors = selectors or [
            FarmSelector(),
            CycleSelector(),
            UserSettingsSelector(),
            LedgerSelector(),
            WeatherSelector(),
            ConversationSelector(),
            MemorySelector(),
            RetrievalSelector(),
        ]
        self.budget = TokenBudget(max_tokens=max_tokens)
        self.trace_collector = trace_collector
        self.policy = policy
```

新增方法：

```python
    def build_runtime_context_bundle(
        self,
        db: Session,
        request: ContextBuildRequest,
        memory_context: MemoryContext | None = None,
        **kwargs,
    ) -> ContextBundle:
        """按 ContextPolicy 构建 Agent Runtime 上下文。"""
        policy = self.policy or ContextPolicy()
        policy_result = policy.resolve(request)
        previous_selectors = self.selectors
        previous_budget = self.budget
        self.selectors = policy_result.selectors
        self.budget = TokenBudget(max_tokens=policy_result.max_tokens)
        try:
            bundle = self.build(
                db=db,
                farm_id=request.farm_id,
                user_id=request.user_id,
                session_id=request.session_id,
                memory_context=memory_context,
                **kwargs,
            )
        finally:
            self.selectors = previous_selectors
            self.budget = previous_budget

        bundle.metadata["policy"] = {
            "intent": request.intent,
            "selected_tool_names": request.selected_tool_names,
            "enabled_layers": sorted(layer.value for layer in policy_result.enabled_layers),
        }
        return bundle
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context/test_builder.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/context/builder.py backend/tests/context/test_builder.py
git commit -m "feat: build runtime context bundle"
```

---

### Task 5: Agent Runtime 注入 ContextBundle

**Files:**
- Modify: `backend/app/agent/runtime/llm_support.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Test: `backend/tests/test_graph_user_setting.py`

- [ ] **Step 1: 写 runtime helper 测试**

追加到 `backend/tests/test_graph_user_setting.py`：

```python
async def test_runtime_context_bundle_contains_user_setting_and_policy(db_session):
    from app.agent.runtime.llm_support import _get_runtime_context_bundle
    from app.agent.prompt_cache import clear_all_caches

    clear_all_caches()

    bundle, farm_ctx = await _get_runtime_context_bundle(
        farm_id=1,
        intent="query",
        selected_tool_names=["get_cost_summary"],
        user_id="test-user-001",
        session_id="session-1",
    )

    keys = [block.key for block in bundle.blocks]

    assert farm_ctx["display_name"] == "测试用户"
    assert "farm" in keys
    assert "cycle" in keys
    assert "ledger" in keys
    assert bundle.metadata["policy"]["selected_tool_names"] == ["get_cost_summary"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_graph_user_setting.py::test_runtime_context_bundle_contains_user_setting_and_policy -v
```

Expected: FAIL，错误包含 `_get_runtime_context_bundle` 无法导入。

- [ ] **Step 3: 实现 runtime context helper**

在 `backend/app/agent/runtime/llm_support.py` 增加：

```python
async def _get_runtime_context_bundle(
    farm_id: int,
    intent: str,
    selected_tool_names: list[str],
    user_id: str | None = None,
    session_id: str | None = None,
) -> tuple:
    """构建 Runtime 使用的 ContextBundle 和兼容 farm_ctx。"""

    def _query() -> tuple:
        db = SessionLocal()
        try:
            context_builder_module = importlib.import_module(
                ".".join(["app", "context", "builder"])
            )
            policy_module = importlib.import_module(".".join(["app", "context", "policy"]))
            memory_service_module = importlib.import_module(".".join(["app", "memory", "service"]))

            context_builder = context_builder_module.ContextBuilder()
            request = policy_module.ContextBuildRequest(
                intent=intent,
                selected_tool_names=selected_tool_names,
                farm_id=farm_id,
                user_id=user_id,
                session_id=session_id,
            )
            memory_context = None
            if user_id:
                memory_service = memory_service_module.get_memory_service()
                import asyncio as _asyncio

                memory_context = _asyncio.run(
                    memory_service.build_context(
                        user_id=user_id,
                        farm_id=farm_id,
                        session_id=session_id,
                    )
                )
            bundle = context_builder.build_runtime_context_bundle(
                db=db,
                request=request,
                memory_context=memory_context,
            )
            farm_ctx = context_builder.build_farm_runtime_context(db=db, farm_id=farm_id)
            return bundle, farm_ctx
        finally:
            db.close()

    return await asyncio.to_thread(_query)
```

在 `__all__` 增加：

```python
    "_get_runtime_context_bundle",
```

- [ ] **Step 4: 将动态上下文追加到 system prompt**

修改 `backend/app/agent/runtime/nodes.py` imports：

```python
    _get_runtime_context_bundle,
```

在已算出 `selected_tools` 后、prompt cache 前增加：

```python
    selected_names_for_context = [t.name for t in selected_tools] if selected_tools else []
    context_bundle, farm_ctx = await _get_runtime_context_bundle(
        farm_id=farm_id,
        intent=intent,
        selected_tool_names=selected_names_for_context,
        user_id=state.get("user_id"),
        session_id=state.get("session_id"),
    )
    display_name = farm_ctx["display_name"]
    farm_location = farm_ctx["farm_location"]
```

删除或跳过原本更早的：

```python
    farm_ctx = await _get_farm_context(farm_id)
    display_name = farm_ctx["display_name"]
    farm_location = farm_ctx["farm_location"]
```

在 `system_text` 生成后追加：

```python
    dynamic_context = context_bundle.render_text()
    if dynamic_context:
        system_text = f"{system_text}\n\n<runtime_context>\n{dynamic_context}\n</runtime_context>"
```

更新 prompt_render trace：

```python
        input_data={
            "template": "system_base",
            "variables_count": 4,
            "context_blocks": [block.key for block in context_bundle.blocks],
        },
```

- [ ] **Step 5: 运行 runtime 测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_graph_user_setting.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/agent/runtime/llm_support.py backend/app/agent/runtime/nodes.py backend/tests/test_graph_user_setting.py
git commit -m "feat: inject runtime context bundle"
```

---

### Task 6: 缓存失效 helper 和写接口接入

**Files:**
- Create: `backend/app/context/invalidation.py`
- Modify: `backend/app/services/cost_service.py`
- Modify: `backend/app/services/debt_service.py`
- Modify: `backend/app/services/cycle_service.py`
- Modify: `backend/app/services/log_service.py`
- Modify: `backend/app/api/user_settings.py`
- Test: `backend/tests/test_prompt_cache.py`

- [ ] **Step 1: 写缓存失效测试**

追加到 `backend/tests/test_prompt_cache.py`：

```python
def test_invalidate_farm_context_clears_prompt_and_farm_context_cache():
    from app.context.invalidation import invalidate_farm_context

    prompt_cache = get_prompt_cache()
    farm_cache = get_farm_ctx_cache()
    prompt_cache.set(farm_id=1, date_str="2026-06-03", value="cached prompt")
    farm_cache.set(farm_id=1, value={"display_name": "旧称呼"})

    result = invalidate_farm_context(farm_id=1)

    assert result["prompt_invalidated"] >= 1
    assert result["farm_context_invalidated"] is True
    assert prompt_cache.get(farm_id=1, date_str="2026-06-03") is None
    assert farm_cache.get(farm_id=1) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_prompt_cache.py::test_invalidate_farm_context_clears_prompt_and_farm_context_cache -v
```

Expected: FAIL，错误包含 `No module named 'app.context.invalidation'`。

- [ ] **Step 3: 实现失效 helper**

创建 `backend/app/context/invalidation.py`：

```python
"""Context 和 Prompt 缓存失效入口。"""

from app.context.cache import get_farm_ctx_cache, get_prompt_cache


def invalidate_farm_context(farm_id: int) -> dict[str, int | bool]:
    """清理单个 farm 相关上下文缓存。"""
    prompt_invalidated = get_prompt_cache().invalidate(farm_id)
    farm_context_invalidated = get_farm_ctx_cache().invalidate(farm_id)
    return {
        "prompt_invalidated": prompt_invalidated,
        "farm_context_invalidated": farm_context_invalidated,
    }


__all__ = ["invalidate_farm_context"]
```

- [ ] **Step 4: 接入写服务**

在以下文件 import：

```python
from app.context.invalidation import invalidate_farm_context
```

在每个写操作 `db.commit()` 成功后调用：

```python
        invalidate_farm_context(farm_id)
```

覆盖这些函数：
- `backend/app/services/cost_service.py`: `create_record()`、`delete_record()`
- `backend/app/services/debt_service.py`: `create_debt_record()`、`settle_debt()`
- `backend/app/services/cycle_service.py`: `create_crop_cycle()`、`update_stage()`、`update_crop_cycle()`、`delete_crop_cycle()`
- `backend/app/services/log_service.py`: `create_log()`、`update_log()`、`delete_log()`
- `backend/app/api/user_settings.py`: `update_settings()` 在 `db.commit()` 后通过当前用户关联 farm 清理缓存

`user_settings.py` 中若已有 `farm` 依赖可直接用 `farm.id`；若没有，查询当前用户 farm：

```python
    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is not None:
        invalidate_farm_context(farm.id)
```

- [ ] **Step 5: 运行缓存测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/test_prompt_cache.py -v
```

Expected: PASS。

- [ ] **Step 6: 运行受影响服务测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/services/test_debt_service.py tests/services/test_conversation_service.py tests/context -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/context/invalidation.py backend/app/services/cost_service.py backend/app/services/debt_service.py backend/app/services/cycle_service.py backend/app/services/log_service.py backend/app/api/user_settings.py backend/tests/test_prompt_cache.py
git commit -m "feat: invalidate context caches on writes"
```

---

### Task 7: 集成验证和文档更新

**Files:**
- Modify: `docs/architecture/backend-architecture.md`
- Modify: `docs/architecture/overview.md`
- Verify: `openspec/changes/optimize-context-and-short-term-memory/tasks.md`

- [ ] **Step 1: 更新架构文档**

在 `docs/architecture/backend-architecture.md` 的 Context/Agent 相关章节加入：

```markdown
### Context 与短时记忆策略

Agent Runtime 使用三层上下文：

- 热上下文：每次注入，包含当前日期、季节、用户称呼、默认位置、坐标、当前 farm 和活跃茬口摘要。
- 工作记忆：session 级短时记忆，包含最近消息窗口、会话摘要、pending action 和临时任务状态。
- 按需检索上下文：由 intent 和 selected tools 触发，包括账务摘要、天气摘要、农事日志、长期记忆命中和外部检索结果。

`ContextPolicy` 负责选择 selector 和 token 预算，`ContextBuilder` 负责构建 `ContextBundle`，`TokenBudget` 负责保留、压缩或丢弃 block。详细业务数据仍通过 skills/tools 主动获取，避免全量注入导致 token 膨胀。
```

在 `docs/architecture/overview.md` 的 Agent 平台边界附近加入同样的短版说明：

```markdown
Context 工程边界：Agent 不直接拼接全量业务数据。Runtime 通过 `ContextPolicy -> ContextBuilder -> ContextBundle -> TokenBudget` 构建动态上下文；短时记忆由 Memory Service 提供 session 视图；详细账务、天气、日志和作物数据由 tool 按需查询。
```

- [ ] **Step 2: 更新 OpenSpec task 状态**

将 `openspec/changes/optimize-context-and-short-term-memory/tasks.md` 中完成的任务逐项从 `- [ ]` 改为 `- [x]`。只标记已经完成并通过测试的项。

- [ ] **Step 3: 运行后端重点测试**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
poetry run pytest tests/context tests/memory tests/test_graph_user_setting.py tests/test_prompt_cache.py -v
```

Expected: PASS。

- [ ] **Step 4: 运行 lint**

Run:

```bash
cd /Users/ljn/Documents/demo/explore/backend
ruff check .
ruff format .
```

Expected: `ruff check .` 无错误；`ruff format .` 不引入无关文件。

- [ ] **Step 5: 运行 OpenSpec 状态**

Run:

```bash
cd /Users/ljn/Documents/demo/explore
openspec status --change optimize-context-and-short-term-memory
```

Expected: artifacts complete，tasks 文件存在且可读。

- [ ] **Step 6: 提交**

```bash
cd /Users/ljn/Documents/demo/explore
git add docs/architecture/backend-architecture.md docs/architecture/overview.md openspec/changes/optimize-context-and-short-term-memory/tasks.md
git commit -m "docs: document context memory architecture"
```

---

## Self-Review

**Spec coverage:**  
`agent-context-policy` 由 Task 1、2、4、5 覆盖；`short-term-memory-policy` 由 Task 3、4、5 覆盖；`conversation-management` 的预算化历史注入由 Task 3、5 覆盖；`user-context-injection` 的准确来源和缺失处理由 Task 5、6 覆盖；`farm-context-injection` 的 selector/block 化和缓存失效由 Task 1、4、6 覆盖。

**Placeholder scan:**  
本计划没有 `TBD`、`TODO`、`implement later`、`fill in details` 这类占位内容。每个代码步骤包含实际文件、实际代码和可运行命令。

**Type consistency:**  
本计划统一使用 `ContextBuildRequest`、`ContextPolicyResult`、`ContextLayer`、`build_runtime_context_bundle()`、`_get_runtime_context_bundle()`、`invalidate_farm_context()`。后续任务引用的函数名与前序任务定义一致。
