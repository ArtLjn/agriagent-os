"""Context block 注册表。

注册表是 block key、Context 分类、prompt 分区和注入策略的事实源。
"""

from dataclasses import dataclass
from enum import StrEnum


class ContextCategory(StrEnum):
    """Context 六类一级分类。"""

    ROLE_POLICY = "role_policy"
    TASK = "task"
    EVIDENCE = "evidence"
    BUSINESS = "business"
    MEMORY = "memory"
    OUTPUT_CONTRACT = "output_contract"


@dataclass(frozen=True, slots=True)
class ContextBlockSpec:
    """单个 Context block 的注册元数据。"""

    key: str
    category: ContextCategory
    section: str
    default_priority: int
    required: bool = False
    compressible: bool = True
    min_tokens: int = 32
    trace_preview: bool = True
    prompt_allowed: bool = True


def _spec(
    key: str,
    category: ContextCategory,
    section: str,
    default_priority: int,
    *,
    required: bool = False,
    compressible: bool = True,
    min_tokens: int = 32,
    trace_preview: bool = True,
    prompt_allowed: bool = True,
) -> ContextBlockSpec:
    return ContextBlockSpec(
        key=key,
        category=category,
        section=section,
        default_priority=default_priority,
        required=required,
        compressible=compressible,
        min_tokens=min_tokens,
        trace_preview=trace_preview,
        prompt_allowed=prompt_allowed,
    )


_BLOCK_SPECS: tuple[ContextBlockSpec, ...] = (
    _spec("assistant_role", ContextCategory.ROLE_POLICY, "Role & Policies", 95),
    _spec(
        "assistant_policy",
        ContextCategory.ROLE_POLICY,
        "Role & Policies",
        95,
        prompt_allowed=False,
    ),
    _spec(
        "policy",
        ContextCategory.ROLE_POLICY,
        "Role & Policies",
        90,
        prompt_allowed=False,
    ),
    _spec(
        "role_policy",
        ContextCategory.ROLE_POLICY,
        "Role & Policies",
        90,
        prompt_allowed=False,
    ),
    _spec("active_task_state", ContextCategory.TASK, "Task", 90),
    _spec("pending_action", ContextCategory.TASK, "Task", 88, prompt_allowed=False),
    _spec("temporary_task_state", ContextCategory.TASK, "Task", 82),
    _spec("pending_action_pointer", ContextCategory.TASK, "Task", 85),
    _spec("pending_plan_pointer", ContextCategory.TASK, "Task", 85),
    _spec("last_confirmed_at", ContextCategory.TASK, "Task", 70),
    _spec("rag_knowledge", ContextCategory.EVIDENCE, "Evidence", 80),
    _spec("retrieval", ContextCategory.EVIDENCE, "Evidence", 78, prompt_allowed=False),
    _spec(
        "tool_result_summary",
        ContextCategory.EVIDENCE,
        "Evidence",
        76,
        prompt_allowed=False,
    ),
    _spec("farm", ContextCategory.BUSINESS, "Context", 70),
    _spec("farm_profile", ContextCategory.BUSINESS, "Context", 70),
    _spec("cycle", ContextCategory.BUSINESS, "Context", 68),
    _spec("ledger", ContextCategory.BUSINESS, "Context", 66),
    _spec("weather", ContextCategory.BUSINESS, "Context", 62, prompt_allowed=False),
    _spec("user_settings", ContextCategory.BUSINESS, "Context", 60),
    _spec(
        "current_crop_cycle_pointer",
        ContextCategory.BUSINESS,
        "Context",
        65,
    ),
    _spec("user_profile", ContextCategory.BUSINESS, "Context", 60),
    _spec("session_meta", ContextCategory.BUSINESS, "Context", 55),
    _spec(
        "planting_units",
        ContextCategory.BUSINESS,
        "Context",
        58,
        prompt_allowed=False,
    ),
    _spec(
        "operation_work_orders",
        ContextCategory.BUSINESS,
        "Context",
        58,
        prompt_allowed=False,
    ),
    _spec("workers", ContextCategory.BUSINESS, "Context", 56, prompt_allowed=False),
    _spec(
        "unpaid_labor",
        ContextCategory.BUSINESS,
        "Context",
        56,
        prompt_allowed=False,
    ),
    _spec(
        "cost_categories",
        ContextCategory.BUSINESS,
        "Context",
        54,
        prompt_allowed=False,
    ),
    _spec("short_term_recent", ContextCategory.MEMORY, "Context", 64),
    _spec("recent_messages", ContextCategory.MEMORY, "Context", 66),
    _spec(
        "short_term_summary",
        ContextCategory.MEMORY,
        "Context",
        62,
        prompt_allowed=False,
    ),
    _spec("conversation", ContextCategory.MEMORY, "Context", 60, prompt_allowed=False),
    _spec(
        "conversation_summary",
        ContextCategory.MEMORY,
        "Context",
        62,
    ),
    _spec("long_term_memory", ContextCategory.MEMORY, "Context", 64),
    _spec("memory", ContextCategory.MEMORY, "Context", 60, prompt_allowed=False),
    _spec(
        "output_contract",
        ContextCategory.OUTPUT_CONTRACT,
        "Output",
        92,
        required=True,
        compressible=False,
        prompt_allowed=False,
    ),
    _spec(
        "citation_rule",
        ContextCategory.OUTPUT_CONTRACT,
        "Output",
        88,
        required=True,
        compressible=False,
        prompt_allowed=False,
    ),
    _spec(
        "clarification_rule",
        ContextCategory.OUTPUT_CONTRACT,
        "Output",
        88,
        required=True,
        compressible=False,
        prompt_allowed=False,
    ),
)

BLOCK_REGISTRY: dict[str, ContextBlockSpec] = {spec.key: spec for spec in _BLOCK_SPECS}


def block_spec(key: str) -> ContextBlockSpec | None:
    """按 key 读取 block 注册信息，未知 key 返回 None。"""
    return BLOCK_REGISTRY.get(key)


def prompt_allowed_keys() -> frozenset[str]:
    """返回允许注入 prompt 的已注册 block key。"""
    return frozenset(key for key, spec in BLOCK_REGISTRY.items() if spec.prompt_allowed)


def section_for_key(key: str) -> str:
    """返回 block 所属 prompt 分区，未知 key 降级到 Context。"""
    spec = block_spec(key)
    if spec is None:
        return "Context"
    return spec.section


__all__ = [
    "BLOCK_REGISTRY",
    "ContextBlockSpec",
    "ContextCategory",
    "block_spec",
    "prompt_allowed_keys",
    "section_for_key",
]
