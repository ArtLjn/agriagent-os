"""Agent Runtime 边界。

Runtime 只承载图执行、节点协议和工具调用编排，不承担 Prompt 版本、
Context 选择、Memory 沉淀或评测报告职责。
"""

from app.agent.runtime.support import compile_advisor_graph

__all__ = ["compile_advisor_graph"]
