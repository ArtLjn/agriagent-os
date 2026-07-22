"""ContextBundle 分区渲染器。"""

from app.context.document import ContextDocument, ContextSection
from app.context.models import ContextBundle


class ContextRenderer:
    """将 ContextBundle 渲染为分区化 prompt 和日志摘要。"""

    SECTION_NAMES: tuple[str, ...] = (
        "Role & Policies",
        "Task",
        "Evidence",
        "Context",
        "Output",
    )

    KEY_TO_SECTION: dict[str, str] = {
        "assistant_role": "Role & Policies",
        "assistant_policy": "Role & Policies",
        "policy": "Role & Policies",
        "role_policy": "Role & Policies",
        "pending_action": "Task",
        "active_task_state": "Task",
        "pending_action_pointer": "Task",
        "pending_plan_pointer": "Task",
        "temporary_task_state": "Task",
        "retrieval": "Evidence",
        "rag_knowledge": "Evidence",
        "tool_result_summary": "Evidence",
        "farm": "Context",
        "farm_profile": "Context",
        "cycle": "Context",
        "weather": "Context",
        "conversation": "Context",
        "conversation_summary": "Context",
        "short_term_recent": "Context",
        "short_term_summary": "Context",
        "user_settings": "Context",
        "output_contract": "Output",
        "citation_rule": "Output",
        "clarification_rule": "Output",
    }

    def section_name_for_key(self, key: str) -> str:
        """按 block key 解析分区，未知 key 归入 Context。"""
        return self.KEY_TO_SECTION.get(key, "Context")

    def render_document(self, bundle: ContextBundle) -> ContextDocument:
        """把 ContextBundle 转为稳定分区顺序的 ContextDocument。"""
        grouped = {name: [] for name in self.SECTION_NAMES}
        for block in bundle.blocks:
            grouped[self.section_name_for_key(block.key)].append(block)
        return ContextDocument(
            sections=tuple(
                ContextSection(name=name, blocks=tuple(grouped[name]))
                for name in self.SECTION_NAMES
            )
        )

    def render_prompt_text(self, bundle: ContextBundle) -> str:
        """渲染可注入模型的分区化上下文。"""
        return self.render_document(bundle).render_prompt_text()

    def debug_summary(self, bundle: ContextBundle) -> dict:
        """渲染日志友好的分区摘要，不包含正文。"""
        return self.render_document(bundle).debug_summary()


__all__ = ["ContextRenderer"]
