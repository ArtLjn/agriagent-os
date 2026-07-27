"""ContextBundle 分区渲染器。"""

from app.context.core.document import ContextDocument, ContextSection
from app.context.core.models import ContextBundle
from app.context.core.registry import section_for_key


class ContextRenderer:
    """将 ContextBundle 渲染为分区化 prompt 和日志摘要。"""

    SECTION_NAMES: tuple[str, ...] = (
        "Role & Policies",
        "Task",
        "Evidence",
        "Context",
        "Output",
    )

    def section_name_for_key(self, key: str) -> str:
        """按 block key 解析分区，未知 key 归入 Context。"""
        return section_for_key(key)

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
