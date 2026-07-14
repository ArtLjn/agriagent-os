"""Skill 文档结构测试。"""

from pathlib import Path

import pytest
import yaml

from app.agent.skills.registry import load_skill_registry
from app.agent.skills.doc_validator import validate_skill_doc

pytestmark = pytest.mark.no_db


def test_validator_requires_runtime_strategy(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert "缺少章节：## Runtime 策略" in result.errors


def test_validator_accepts_tool_name_alias_for_snake_case_runtime(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo-skill
tool_name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert result.errors == []


def test_validator_accepts_quoted_tool_name_alias(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo-skill
tool_name: "demo_skill"
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert result.errors == []


def test_validator_requires_runtime_strategy_as_heading(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

示例提到 ## Runtime 策略，但这里不是标题。

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert "缺少章节：## Runtime 策略" in result.errors


def test_validator_rejects_non_snake_case_tool_name_alias(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo-skill
tool_name: demo-skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert "tool_name 必须是严格 snake_case" in result.errors


def test_all_existing_skill_docs_are_valid():
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    skill_docs = sorted(skills_dir.glob("*/skill.md"))

    assert skill_docs

    failures = []
    for skill_doc in skill_docs:
        result = validate_skill_doc(skill_doc)
        if result.errors:
            relative_path = skill_doc.relative_to(skills_dir)
            failures.append(f"{relative_path}: {', '.join(result.errors)}")

    assert failures == []


def test_all_existing_skill_docs_resolve_registry_aliases():
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    registry = load_skill_registry()
    failures = []

    for skill_doc in sorted(skills_dir.glob("*/skill.md")):
        front_matter = skill_doc.read_text(encoding="utf-8").split("---", 2)[1]
        metadata = yaml.safe_load(front_matter) or {}
        tool_name = str(metadata.get("tool_name") or metadata["name"])
        alias = registry.resolve_alias(tool_name)
        if alias is None:
            if tool_name not in registry.capabilities:
                failures.append(f"{skill_doc.parent.name}: 缺少 alias {tool_name}")
            continue
        if registry.get_operation(alias.capability, alias.operation) is None:
            failures.append(f"{skill_doc.parent.name}: alias 目标不存在 {alias.target}")

    assert failures == []


def test_registry_aliases_have_skill_docs():
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    registry = load_skill_registry()
    tool_names = _skill_doc_tool_names(skills_dir)
    documented_capabilities = {
        alias.capability
        for legacy_name, alias in registry.aliases.items()
        if legacy_name in tool_names
    }

    missing_docs = sorted(
        legacy_name
        for legacy_name, alias in registry.aliases.items()
        if legacy_name not in tool_names
        and alias.capability not in tool_names
        and alias.capability not in documented_capabilities
    )

    assert missing_docs == []


def test_skill_docs_do_not_conflict_with_registry_domain_or_capability():
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    registry = load_skill_registry()
    failures = []

    for skill_doc in sorted(skills_dir.glob("*/skill.md")):
        metadata = _skill_doc_metadata(skill_doc)
        tool_name = str(metadata.get("tool_name") or metadata["name"])
        alias = registry.resolve_alias(tool_name)
        capability = _doc_capability(registry, tool_name, alias)
        if metadata.get("domain") and metadata["domain"] != capability.domain:
            failures.append(
                f"{skill_doc.parent.name}: domain {metadata['domain']} "
                f"!= Registry {capability.domain}"
            )
        capability_name = alias.capability if alias is not None else capability.name
        if metadata.get("capability") and metadata["capability"] != capability_name:
            failures.append(
                f"{skill_doc.parent.name}: capability {metadata['capability']} "
                f"!= Registry {capability_name}"
            )

    assert failures == []


def test_hidden_or_disabled_skill_docs_disclose_disabled_state():
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    registry = load_skill_registry()
    failures = []

    for skill_doc in sorted(skills_dir.glob("*/skill.md")):
        metadata = _skill_doc_metadata(skill_doc)
        tool_name = str(metadata.get("tool_name") or metadata["name"])
        alias = registry.resolve_alias(tool_name)
        capability = _doc_capability(registry, tool_name, alias)
        if capability.status == "active":
            continue
        text = skill_doc.read_text(encoding="utf-8")
        if "禁用" not in text and "disabled" not in text.lower():
            failures.append(
                f"{skill_doc.parent.name}: Registry status={capability.status} "
                "但 skill.md 未说明禁用状态"
            )

    assert failures == []


def test_validator_rejects_empty_properties_when_parameter_inference_has_params(
    tmp_path,
):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
- “查今天的数据” -> date 必填。

## 缺参策略
缺少日期时追问。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“查今天的数据” -> `demo_skill(date="2026-06-05")`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert (
        "frontmatter parameters.properties 为空，但参数推断包含具体参数"
        in result.errors
    )


def test_validator_rejects_invalid_tool_name_even_when_name_is_snake_case(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo_skill
tool_name: demo-skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert "tool_name 必须是严格 snake_case" in result.errors


def _skill_doc_tool_names(skills_dir: Path) -> set[str]:
    tool_names = set()
    for skill_doc in sorted(skills_dir.glob("*/skill.md")):
        metadata = _skill_doc_metadata(skill_doc)
        tool_names.add(str(metadata.get("tool_name") or metadata["name"]))
    return tool_names


def _doc_capability(registry, tool_name: str, alias):
    if alias is not None:
        return registry.capabilities[alias.capability]
    return registry.capabilities[tool_name]


def _skill_doc_metadata(skill_doc: Path) -> dict:
    front_matter = skill_doc.read_text(encoding="utf-8").split("---", 2)[1]
    return yaml.safe_load(front_matter) or {}
