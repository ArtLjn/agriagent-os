"""Agent 回放用例 schema。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExpectedSkillCall:
    """期望的 skill/tool 调用。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    required: bool = True


@dataclass
class ExpectedWriteOperation:
    """期望写操作。"""

    table: str
    operation: str
    expected_count: int = 1
    match_fields: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


@dataclass
class ExpectedPendingAction:
    """期望 pending action。"""

    skill_name: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    confirmation_required: bool = True


@dataclass
class ConfirmationFlowStep:
    """用户确认流程步骤。"""

    user_input: str
    expected_status: str
    expected_pending_action: ExpectedPendingAction | None = None


@dataclass
class ExpectedDatabaseDiff:
    """期望数据库差异。"""

    table: str
    operation: str
    match_fields: dict[str, Any] = field(default_factory=dict)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplyAssertion:
    """回复断言。"""

    contains: str | None = None
    not_contains: str | None = None
    min_length: int = 0


@dataclass
class ContextExpectation:
    """上下文期望。"""

    user_context: dict[str, Any] = field(default_factory=dict)
    farm_context: dict[str, Any] = field(default_factory=dict)
    required_facts: list[str] = field(default_factory=list)
    expected_block_types: list[str] = field(default_factory=list)


@dataclass
class AgentReplayCase:
    """Agent 回放评测用例。"""

    case_id: str
    description: str
    user_input: str
    user_context: dict[str, Any] = field(default_factory=dict)
    context: ContextExpectation = field(default_factory=ContextExpectation)
    expected_skills: list[ExpectedSkillCall] = field(default_factory=list)
    expected_parameters: dict[str, Any] = field(default_factory=dict)
    expected_pending_action: ExpectedPendingAction | None = None
    confirmation_flow: list[ConfirmationFlowStep] = field(default_factory=list)
    expected_database_diff: list[ExpectedDatabaseDiff] = field(default_factory=list)
    expected_writes: list[ExpectedWriteOperation] = field(default_factory=list)
    reply_assertions: list[ReplyAssertion] = field(default_factory=list)
    category: str = "basic"
    metadata: dict[str, Any] = field(default_factory=dict)
