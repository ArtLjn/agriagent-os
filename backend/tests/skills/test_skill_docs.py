"""Skill 文档结构测试。"""

from pathlib import Path


SKILL_DOC_REQUIRED_SECTIONS = [
    "## 何时使用",
    "## 不要使用",
    "## 参数推断",
    "## 缺参策略",
    "## 示例",
]


def test_all_skill_docs_use_hybrid_instruction_style():
    """所有 Skill 文档都应同时保留机器元数据和面向模型的行为说明。"""
    skill_root = Path(__file__).parents[2] / "app" / "agent" / "skills"
    docs = sorted(skill_root.glob("*/skill.md"))

    assert docs, "未发现 skill.md"
    missing = {}
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        sections = [s for s in SKILL_DOC_REQUIRED_SECTIONS if s not in text]
        if sections:
            missing[str(doc.relative_to(skill_root))] = sections

    assert not missing
