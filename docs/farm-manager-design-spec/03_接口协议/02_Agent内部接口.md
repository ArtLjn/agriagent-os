# 02 — Agent 内部接口

> 状态：草稿 | 维护：BlockShip | 关联：[01_HTTP_API协议](./01_HTTP_API协议.md)、[01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)

---

## 1. 内部接口定义

Agent 内部接口是平台子域之间的 Python Protocol，不是 HTTP。规范这里以便子域边界对齐。

## 2. Application Use Case 接口

```python
# agent/application/chat_use_case.py
class ChatUseCase:
    async def execute(self, request: ChatRequest) -> ChatResponse:
        """同步对话。"""

# agent/application/stream_chat_use_case.py
class StreamChatUseCase:
    async def execute(self, request: ChatRequest) -> AsyncIterator[SSEEvent]:
        """流式对话，产出 SSE 事件。"""

# agent/application/daily_advice_use_case.py
class DailyAdviceUseCase:
    async def execute_for_farm(self, farm_id: int) -> DailyAdvice:
        """为指定农场生成每日建议。"""

# agent/application/history_use_case.py
class HistoryUseCase:
    async def list_sessions(self, farm_id: int, page: int, page_size: int) -> PageResult[SessionSummary]:
        """会话历史。"""
    async def get_session(self, session_id: str) -> SessionDetail:
        """单会话详情。"""
```

## 3. Runtime 接口

```python
# agent/runtime/graph_factory.py
class RuntimeGraph:
    async def ainvoke(self, state: RuntimeState) -> RuntimeState:
        """一次性执行整图。"""
    async def astream(self, state: RuntimeState) -> AsyncIterator[StreamEvent]:
        """流式执行，产出节点级事件。"""

# agent/runtime/state.py
class RuntimeState(TypedDict):
    messages: list[BaseMessage]
    tool_calls: list[ToolCall]
    pending: PendingAction | None
    reflection: ReflectionResult | None
    metadata: RuntimeMetadata

# agent/runtime/tool_executor.py
class ToolExecutor:
    async def execute(self, tool_call: ToolCall, context: SkillContext) -> ToolMessage:
        """执行单个 tool_call，返回 ToolMessage。"""
```

## 4. Planner 接口

```python
# agent/planner/
class Planner:
    async def plan(self, input: PlannerInput) -> PlannerOutput:
        """意图识别 + 工具候选。"""

class PlannerInput(BaseModel):
    user_message: str
    farm_id: int
    context_summary: ContextSummary

class PlannerOutput(BaseModel):
    intent: Intent
    candidates: list[str]          # Skill name 列表
    confidence: float
    reasoning: str
```

## 5. Executor 接口

```python
# agent/executor/
class SkillExecutor:
    async def execute(self, skill_name: str, params: dict, context: SkillContext) -> SkillResult:
        """调用 Skill。"""

class PendingManager:
    async def create(self, action: PendingActionCreate) -> PendingAction:
        """创建 Pending Action。"""
    async def confirm(self, pending_id: str) -> PendingActionResult:
        """确认并执行。"""
    async def cancel(self, pending_id: str) -> None:
        """取消。"""
    async def expire_outdated(self) -> int:
        """清理过期，返回清理数。"""
```

## 6. Reflector 接口

```python
# agent/reflector/
class Reflector:
    async def check(self, input: ReflectionInput) -> ReflectionResult:
        """对一次 tool_call + 回复做一致性检查。"""

class ReflectionInput(BaseModel):
    tool_calls: list[ToolCall]
    tool_results: list[ToolMessage]
    final_reply: str
    pending: PendingAction | None

class ReflectionResult(BaseModel):
    checks: list[CheckResult]
    triggered: bool
    trace_payload: dict       # 写入 reflection_trace 表
```

## 7. Prompt 接口

```python
# prompt/composer.py
class PromptComposer:
    def compose(self, request: PromptInput) -> ComposedPrompt:
        """组合最终 system prompt。"""

class PromptInput(BaseModel):
    persona: Persona
    context_bundle: ContextBundle
    intent: Intent
    candidates: list[str]
    tool_results: list[ToolMessage]

class ComposedPrompt(BaseModel):
    system: list[PromptBlock]    # 分块（便于 caching）
    system_text: str             # 完整拼接
    metadata: PromptMetadata     # token, snippet_versions
```

## 8. Context 接口

```python
# context/builder.py
class ContextBuilder:
    async def build(self, request: ContextBuildRequest) -> ContextBundle:
        """构建 ContextBundle。"""

class ContextBuildRequest(BaseModel):
    farm_id: int
    intent: Intent
    tool_names: list[str]
    session_id: str

class ContextBundle(BaseModel):
    farm: FarmFacts
    cycle: CycleFacts | None
    settings: UserSettingsFacts
    ledger: LedgerSnapshot | None
    weather: WeatherSnapshot | None
    conversation: ConversationSummary
    memory: MemoryView
    preload: PreloadKnowledge | None
    metadata: ContextMetadata
```

## 9. Memory 接口

```python
# memory/service.py
class MemoryService:
    async def build_context(self, request: MemoryContextRequest) -> MemoryView: ...
    async def observe(self, event: ObservationEvent) -> None: ...
    async def search(self, query: MemoryQuery) -> list[MemoryRecord]: ...
    async def store(self, record: MemoryRecord) -> None: ...
    async def consolidate(self, session_id: str) -> ConsolidationResult: ...
```

## 10. Skill 接口

```python
# agent/skills/base.py
class Skill(Protocol):
    def name(self) -> str: ...
    def description(self) -> str: ...
    def parameters_schema(self) -> dict: ...
    async def execute(self, params: dict, context: SkillContext) -> SkillResult: ...

class SkillContext(BaseModel):
    farm_id: int
    user_id: int
    session_id: str
    trace_id: str
    db: Session               # SQLAlchemy session
    memory: MemoryService     # 通过端口访问

class SkillResult(BaseModel):
    status: ResultStatus       # SUCCESS / FAILED / NEED_CLARIFY
    reply: str                 # 中文自然语言
    data: dict | None          # 结构化数据（前端可用）
    pending: PendingActionCreate | None  # 触发 Pending
```

## 11. Trace 接口

```python
# infra/trace_collector.py
class TraceCollector:
    def start_span(self, node: str, input_summary: dict) -> Span: ...
    def end_span(self, span: Span, output_summary: dict, error: dict | None = None) -> None: ...
    def emit(self, event: TraceEvent) -> None: ...
```

## 12. 调用链全景

```
HTTP Request
  → api/agent.py
  → ChatUseCase.execute
    → ConversationService.save_user_message
    → PendingManager.check_existing
    → Advisor.invoke
      → Guardrails.check_input
      → Planner.plan
      → ContextBuilder.build
        → MemoryService.build_context
      → PromptComposer.compose
      → RuntimeGraph.astream
        → LLM call
        → ToolExecutor.execute
          → Skill.execute
            → module.ports.<Domain>Port.<method>
        → Reflector.check
      → Guardrails.filter_output
    → ConversationService.save_assistant_message
    → MemoryService.observe
    → TraceCollector.emit
  → Response / SSE
```

## 13. 错误传递

| 层 | 错误类型 | 处理 |
| --- | --- | --- |
| API | HTTPException | 直接返回 |
| UseCase | UseCaseError | 转 HTTPException |
| Runtime | GraphRecursionError | 返回降级回复 |
| ToolExecutor | SkillError | 转 ToolMessage（error） |
| Skill | ResultStatus.FAILED | 返回中文提示 |
| Memory | MemoryError | 跳过记忆，主流程继续 |
| Trace | TraceError | 静默丢弃（不影响主流程） |

## 14. 相关文档

- [01_HTTP_API协议](./01_HTTP_API协议.md)
- [03_外部服务接口](./03_外部服务接口.md)
- [04_Skill接口契约](./04_Skill接口契约.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
