"""Skill 文档结构校验器。"""

from dataclasses import dataclass
from pathlib import Path
import re


REQUIRED_SECTIONS = [
    "## 何时使用",
    "## 不要使用",
    "## 参数推断",
    "## 缺参策略",
    "## Runtime 策略",
    "## 失败处理",
    "## 示例",
]

REQUIRED_FRONTMATTER_KEYS = [
    "name",
    "type",
    "description",
    "triggers",
    "parameters",
]

SNAKE_CASE_PATTERN = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"


@dataclass(frozen=True)
class SkillDocValidationResult:
    path: Path
    errors: list[str]


def validate_skill_doc(path: Path) -> SkillDocValidationResult:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    frontmatter = _extract_frontmatter(text)
    if frontmatter is None:
        errors.append("缺少 YAML frontmatter")
    else:
        for key in REQUIRED_FRONTMATTER_KEYS:
            if not re.search(rf"^{re.escape(key)}:", frontmatter, re.MULTILINE):
                errors.append(f"frontmatter 缺少字段：{key}")
        tool_name_match = re.search(
            r"^tool_name:\s*(\S+)\s*$", frontmatter, re.MULTILINE
        )
        if tool_name_match is not None:
            tool_name = tool_name_match.group(1).strip("\"'")
            if not re.fullmatch(SNAKE_CASE_PATTERN, tool_name):
                errors.append("tool_name 必须是严格 snake_case")
        elif re.search(r"^name:\s*[a-z0-9]+-[a-z0-9-]+", frontmatter, re.MULTILINE):
            errors.append("kebab-case name 必须提供 snake_case tool_name")
        if _has_empty_parameter_properties(frontmatter) and _section_has_parameters(
            text
        ):
            errors.append(
                "frontmatter parameters.properties 为空，但参数推断包含具体参数"
            )

    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^{re.escape(section)}\s*$", text, re.MULTILINE):
            errors.append(f"缺少章节：{section}")

    return SkillDocValidationResult(path=path, errors=errors)


def _extract_frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        return None
    return match.group(1)


def _has_empty_parameter_properties(frontmatter: str) -> bool:
    return (
        re.search(r"^\s*properties:\s*\{\}\s*$", frontmatter, re.MULTILINE) is not None
    )


def _section_has_parameters(text: str) -> bool:
    section = _extract_section(text, "## 参数推断", "## 缺参策略")
    if section is None:
        return False
    if re.search(r"无参数|不需要参数|无需参数", section):
        return False
    return any(
        re.search(pattern, section)
        for pattern in [
            r"`[^`]*[a-zA-Z_][a-zA-Z0-9_]*\s*=",
            r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?:必填|可选|=|:|：)",
            r"(?:参数|字段|筛选).*[:：].*[a-zA-Z_][a-zA-Z0-9_]*",
        ]
    )


def _extract_section(text: str, start_heading: str, end_heading: str) -> str | None:
    start = re.search(rf"^{re.escape(start_heading)}\s*$", text, re.MULTILINE)
    if start is None:
        return None
    end = re.search(
        rf"^{re.escape(end_heading)}\s*$",
        text[start.end() :],
        re.MULTILINE,
    )
    if end is None:
        return text[start.end() :]
    return text[start.end() : start.end() + end.start()]
