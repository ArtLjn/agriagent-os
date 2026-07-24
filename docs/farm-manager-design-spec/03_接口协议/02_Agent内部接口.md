# 02 — Agent 内部接口

> 状态：草稿 | 维护：BlockShip | 关联：[01_HTTP_API协议](./01_HTTP_API协议.md)、[01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)

---

## 1. 内部接口定义

Agent 内部接口是平台子域之间的 Python Protocol，不是 HTTP。规范这里以便子域边界对齐。

## 2. Application Use Case 接口

```python
# application/chat/use_case.py
async def chat(db: Session, request: ChatRequest, farm: Farm, request_id: str) -> ChatResponse:
    """同步对话。"""

# application/chat/stream_chat.py
async def stream_chat_events(
    db: Session,
    request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> AsyncIterator[dict]:
    """流式对话，产出 SSE 事件。"""

# application/advice/use_case.py
async def get_daily(db: Session, farm: Farm, cycle_id: int | None) -> DailyAdviceResponse:
    """获取每日建议。"""

# application/session/history.py
def list_conversation_items(db: Session, farm: Farm, limit: int) -> list[ConversationListItem]:
    """会话历史。"""
```

## 3. Runtime 接口

```python
# agent/runtime/loop.py
async def run_agent_loop(state: AgentState, max_steps: int = 15) -> AgentState:
    """一次性执行 ReAct loop。"""

async def stream_agent_loop(state: AgentState, max_steps: int = 15) -> AsyncIterator[dict[str, dict]]:
    """按节点增量流式执行 ReAct loop。"""

# agent/runtime/state.py
class AgentState(TypedDict):
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

## 4. Router 接口

```python
# agent/router/service.py
class SkillRouter:
    def route(self, message: str, tools: list[BaseTool]) -> RouterDecision:
        """意图识别 + 工具候选 + fallback 策略。"""

class RouterDecision(BaseModel):
    selected_tools: list[str]
    fallback: str | None
    reason: str
    clarification: str | None
    evidence: dict
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
# skillify Skill，由 app/skills/__init__.py 转为 LangChain StructuredTool
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
    pending: PendingActionCreate | None  # 需要确认时触发 Pending plan
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
  → domains/conversation/routes.py
  → application/chat/use_case.py 或 stream_chat.py
    → ConversationService.save_user_message
    → pending plan / pending action 检查
    → agent/runtime/loop.py
      → Guardrails.check_input
      → SkillRouter.route
      → ContextBuilder.build
        → MemoryService.build_context
      → PromptComposer.compose
      → stream_agent_loop / run_agent_loop
        → LLM call
        → ToolExecutor.execute
          → Skill.execute
            → domains.<domain>.service
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
| Runtime | AgentLoopMaxStepsExceeded | 返回降级回复 |
| ToolExecutor | SkillError | 转 ToolMessage（error） |
| Skill | ResultStatus.FAILED | 返回中文提示 |
| Memory | MemoryError | 跳过记忆，主流程继续 |
| Trace | TraceError | 静默丢弃（不影响主流程） |

## 14. 相关文档

- [01_HTTP_API协议](./01_HTTP_API协议.md)
- [03_外部服务接口](./03_外部服务接口.md)
- [04_Skill接口契约](./04_Skill接口契约.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
