"""分区化 Context 文档结构。"""

from dataclasses import dataclass
from typing import Any

from app.context.models import ContextBlock


@dataclass(frozen=True, slots=True)
class ContextSection:
    """Prompt 中的一个上下文分区。"""

    name: str
    blocks: tuple[ContextBlock, ...] = ()

    @property
    def token_estimate(self) -> int:
        """估算该分区使用的 token。"""
        return sum(block.token_estimate or 0 for block in self.blocks)

    def render_prompt_text(self) -> str:
        """渲染分区正文。"""
        rendered_blocks = [
            f"### {block.key}\n{block.content.strip()}"
            for block in self.blocks
            if block.content and block.content.strip()
        ]
        if not rendered_blocks:
            return ""
        return f"## {self.name}\n\n" + "\n\n".join(rendered_blocks)

    def debug_summary(self) -> dict[str, Any]:
        """输出日志友好的分区摘要，不包含正文。"""
        return {
            "name": self.name,
            "token_estimate": self.token_estimate,
            "blocks": [
                {
                    "key": block.key,
                    "source": block.source,
                    "token_estimate": block.token_estimate or 0,
                    "required": block.required,
                    "is_compressed": block.is_compressed,
                    "purpose": block.purpose,
                    "reason": block.reason,
                }
                for block in self.blocks
            ],
        }


@dataclass(frozen=True, slots=True)
class ContextDocument:
    """由 ContextBundle 渲染得到的分区化文档。"""

    sections: tuple[ContextSection, ...]

    def render_prompt_text(self) -> str:
        """渲染可注入 prompt 的分区文本。"""
        return "\n\n".join(
            section_text
            for section in self.sections
            if (section_text := section.render_prompt_text())
        )

    def debug_summary(self) -> dict[str, Any]:
        """输出日志友好的文档摘要，不包含正文。"""
        return {
            "sections": [
                section.debug_summary() for section in self.sections if section.blocks
            ]
        }


__all__ = ["ContextDocument", "ContextSection"]
