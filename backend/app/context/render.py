"""Context 渲染兼容入口。"""

from app.context.document import ContextDocument, ContextSection
from app.context.renderer import ContextRenderer

__all__ = ["ContextDocument", "ContextRenderer", "ContextSection"]
