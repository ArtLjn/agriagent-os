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
    farm_id: int
    farm_uid: str | None
    intent: str
    user_id: str | None
    session_id: str | None
    user_role: NotRequired[str | None]
    system_prompt: NotRequired[str | None]
    context_bundle: NotRequired[ContextBundle | None]
    selected_tool_names: NotRequired[list[str] | None]
    router_decision: NotRequired[RouterDecision | None]
    plan_draft: NotRequired[dict | None]
    plan_ir: NotRequired[object | None]
    active_task_state: NotRequired[dict | None]
    task_state_relevance: NotRequired[dict | None]
    task_state_context_should_inject: NotRequired[bool]
    task_state_routing_input: NotRequired[str | None]
    trace_round_index: NotRequired[int | None]

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

## 6. Planning / PendingPlan 接口

```python
# agent/task_graph/models.py
class PlanIR(BaseModel):
    ir_id: str
    task_type: str
    steps: list[PlanIRStep]
    planner_version: str
    context_hash: str
    response_contract: dict

class PlanIRStep(BaseModel):
    step_id: str
    capability: str | None
    operation: str | None
    inputs: dict
    depends_on: list[str]
    side_effect: str

# agent/runtime/planning/execution_plan.py
@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    capability: str
    operation: str
    skill_name: str
    params: dict
    depends_on: list[str]
    requires_confirmation: bool
    side_effect: str

@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    source_ir_id: str
    task_type: str
    steps: list[ExecutionStep]
    validation_version: str = "execution-plan-v1"

def compile_plan_ir_to_execution_plan(plan_ir: PlanIR, *, registry: SkillRegistry | None = None) -> ExecutionPlan:
    """PlanIR → Runtime 可执行合同；未知 capability / operation fail-closed。"""

def pending_steps_from_execution_plan(plan: ExecutionPlan) -> list[dict]:
    """ExecutionPlan → pending_plan_service 可存储 steps。"""

# agent/runtime/plan_ir_pending.py
def build_plan_ir_pending_plan_candidate(state: AgentState) -> PlanIRPendingPlanCandidate | PlanIRPendingPlanBlocked | None:
    """从 state.plan_ir 构建 PendingPlan candidate；非法计划返回 blocked。"""
```

边界：

- `PlanIR` 面向 Planner，描述“为什么、怎么拆、依赖和风险”，不直接执行。
- `ExecutionPlan` 面向 Runtime，描述“哪个 skill、参数、顺序、是否需要确认”。
- `PendingPlan` 面向数据库和用户确认，保存状态、TTL、确认结果和执行结果。
- `task_graph/runtime` 不再作为在线执行 Runtime，只保留 legacy 兼容标记。

## 7. Reflector 接口

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

## 8. Prompt 接口

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

## 9. Context 接口

```python
# context/builder.py
def build_runtime_context_bundle(
    db: Session,
    request: ContextBuildRequest,
    memory_context: MemoryView | None = None,
    context_pack: ContextPack | None = None,
) -> ContextBundle:
    """构建 Runtime 消费的 ContextBundle。"""

@dataclass(frozen=True)
class ContextBuildRequest:
    intent: str = "chat"
    query: str = ""
    selected_tool_names: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    selected_skill_metadata: dict[str, dict] = field(default_factory=dict)
    farm_id: int = 0
    user_id: str | None = None
    session_id: str | None = None
    include_retrieval: bool = False
    task_state_should_inject: bool = True

@dataclass
class ContextBundle:
    blocks: list[ContextBlock]
    token_budget: int
    token_estimate: int
    compressed_blocks: list[ContextBlock]
    dropped_blocks: list[ContextBlock]
    metadata: dict
```

## 10. Memory 接口

```python
# memory/service.py
class MemoryService:
    async def build_context(self, request: MemoryContextRequest) -> MemoryView: ...
    async def observe(self, event: ObservationEvent) -> None: ...
    async def search(self, query: MemoryQuery) -> list[MemoryRecord]: ...
    async def store(self, record: MemoryRecord) -> None: ...
    async def consolidate(self, session_id: str) -> ConsolidationResult: ...
```

## 11. Skill 接口

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

## 12. TaskState 更新接口

```python
# application/chat/task_state_updater.py
@dataclass(frozen=True)
class TurnResult:
    intent: str = ""
    task_type: str = ""
    entities: dict[str, object] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    plan_result: dict[str, object] | None = None
    execution_result: dict[str, object] | None = None
    facts: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class TaskStateTurn:
    farm_id: int
    user_id: str | None
    session_id: str | None
    user_input: str
    assistant_reply: str
    pending_action: object | None = None
    pending_plan: object | None = None
    pending_decision_handled: bool = False
    turn_result: TurnResult | None = None

async def update_task_state_after_turn(db: Session, turn: TaskStateTurn) -> TaskStateUpdateResult:
    """优先基于 TurnResult 结构化结果更新 TaskState；pending 确认链路跳过。"""
```

`TurnResult` 是未来 TaskState 更新的首选输入。兼容期允许基于助手回复做保守文本解析，但新增 Planner / Executor 能提供结构化结果时，不能再反向正则解析自然语言回复。

## 13. Trace 接口

```python
# infra/trace_collector.py
class TraceCollector:
    def start_span(self, node: str, input_summary: dict) -> Span: ...
    def end_span(self, span: Span, output_summary: dict, error: dict | None = None) -> None: ...
    def emit(self, event: TraceEvent) -> None: ...
```

## 14. Final Response 接口

Final Response 接口用于把 ReAct 内部消息投影为用户可见回复上下文。它是防止 function call JSON 泄漏的核心边界。

```python
# agent/runtime/final_context.py
@dataclass(frozen=True)
class ToolResultSummary:
    tool_name: str
    operation: str | None
    status: str
    permission_level: str
    summary: str
    facts: dict[str, object]
    error_code: str | None = None

@dataclass(frozen=True)
class FinalResponseConstraints:
    forbid_tools: bool = True
    forbid_json: bool = True
    forbid_function_call_format: bool = True
    language: str = "zh-CN"

@dataclass(frozen=True)
class FinalResponseRequest:
    user_query: str
    tool_results: list[ToolResultSummary]
    context_blocks: list[dict[str, object]]
    constraints: FinalResponseConstraints
    trace_meta: dict[str, object]

class FinalContextBuilder:
    def build(self, state: AgentState) -> FinalResponseRequest:
        """从 AgentState 构建 final 阶段上下文，不透传原始 AIMessage.tool_calls。"""
```

约束：

- final 阶段 LLM 调用必须使用 `tools=[]` 和 `tool_choice="none"`。
- `FinalContextBuilder` 不返回原始 `AIMessage(tool_calls)`。
- `FinalContextBuilder` 不返回原始 `ToolMessage`，只返回 `ToolResultSummary`。
- final prompt 只消费 `FinalResponseRequest`，不直接消费 ReAct 消息历史。
- Output Guard 发现 JSON / function call 泄漏时，必须写 trace 并按 [15_Agent运行协议与防泄漏设计](../01_正式设计/15_Agent运行协议与防泄漏设计.md) 处理。

## 15. 调用链全景

```
HTTP Request
  → domains/conversation/routes.py
  → application/chat/use_case.py 或 stream_chat.py
    → ConversationService.save_user_message
    → pending plan / pending action 检查
    → AgentTaskStateStore.get_active_task
    → evaluate_task_state_relevance
      → low relevance: 不注入 active task，Router 只看原始输入
      → high relevance: task_state_routing_input + task_state_should_inject=True
    → agent/runtime/loop.py
      → Guardrails.check_input
      → SkillRouter.route
      → build_runtime_context_bundle
        → ContextPack / MemorySelector / TaskStateSelector / KnowledgeSelector
      → PromptComposer.compose
      → stream_agent_loop / run_agent_loop
        → LLM call
        → state.plan_ir 存在时：PlanIR → ExecutionPlan → PendingPlan candidate
        → ToolExecutor.execute
          → Skill.execute
            → domains.<domain>.service
        → Reflector.check
        → FinalContextBuilder.build
        → Final Agent(tools=[], tool_choice=none)
        → OutputGuard.check_final_response
      → Guardrails.filter_output
    → ConversationService.save_assistant_message
    → update_task_state_after_turn(TurnResult 优先，文本解析兜底)
    → MemoryService.observe
    → TraceCollector.emit
  → Response / SSE
```

## 16. 错误传递

| 层 | 错误类型 | 处理 |
| --- | --- | --- |
| API | HTTPException | 直接返回 |
| UseCase | UseCaseError | 转 HTTPException |
| Runtime | AgentLoopMaxStepsExceeded | 返回降级回复 |
| Planning adapter | PLAN_IR_INVALID / EXECUTION_PLAN_COMPILE_ERROR | fail-closed，返回合同阻断或澄清，不执行 Skill |
| ToolExecutor | SkillError | 转 ToolMessage（error） |
| Skill | ResultStatus.FAILED | 返回中文提示 |
| Memory | MemoryError | 跳过记忆，主流程继续 |
| Trace | TraceError | 静默丢弃（不影响主流程） |
| FinalContext | FINAL_CONTEXT_CONTRACT_VIOLATION | fail-closed，不调用 final LLM，写 trace |
| OutputGuard | FINAL_JSON_LEAK_DETECTED | 重试一次；仍失败则抽取自然语言或 fail-closed，写 DataFlywheel issue |

## 17. 相关文档

- [01_HTTP_API协议](./01_HTTP_API协议.md)
- [03_外部服务接口](./03_外部服务接口.md)
- [04_Skill接口契约](./04_Skill接口契约.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
- [01_正式设计/15_Agent运行协议与防泄漏设计](../01_正式设计/15_Agent运行协议与防泄漏设计.md)
- [01_正式设计/16_Agent日志与诊断设计](../01_正式设计/16_Agent日志与诊断设计.md)
