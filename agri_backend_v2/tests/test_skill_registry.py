"""SkillLoader 与 SkillRegistry 的目录加载和能力快照契约测试。"""

from pathlib import Path

import pytest

from agent.domains.harness.tools import loader
from agent.domains.harness.tools.base import OperationSkill, Skill
from agent.domains.harness.tools.registry import SkillRegistry, SkillRegistryError


def test_from_directory_loads_current_skill_catalog() -> None:
    registry = loader.load_registry()
    snapshot = registry.snapshot()

    assert len(registry.all()) == 59
    assert len(registry.exposed_tools()) == 58
    assert "get_weather" in snapshot["skill_names"]
    assert "commit_planting_plan" not in snapshot["exposed_tool_names"]
    assert snapshot["risk_levels"] == tuple(sorted(snapshot["risk_levels"]))


def test_shipped_routing_metadata_passes_standalone_validator():
    from scripts.validate_skill_metadata import validate_directories

    root = Path(__file__).parents[1]
    directories = [
        root / "agent" / "tools",
        *(
            path
            for path in (root / "businesses").glob("*/skills")
            if not path.parent.name.startswith(("_", "."))
        ),
    ]
    assert not validate_directories(directories)


def test_require_returns_structured_missing_skill_error() -> None:
    registry = SkillRegistry.from_skills([])

    with pytest.raises(SkillRegistryError, match="skill_missing.*missing") as exc_info:
        registry.require("missing")

    assert exc_info.value.code == "skill_missing"
    assert exc_info.value.skill_name == "missing"


@pytest.mark.parametrize(
    "routing",
    [
        None,
        [],
        {"unknown": []},
        {"use_when": "字符串"},
        {"examples": [1]},
        {"avoid_when": [" "]},
    ],
)
def test_invalid_routing_metadata_is_rejected(routing):
    skill = Skill()
    skill._meta = {"name": "example", "routing": routing}
    with pytest.raises(SkillRegistryError, match="invalid_routing_metadata"):
        SkillRegistry.from_skills([skill])


def test_operation_routing_overrides_without_mutating_source():
    source = Skill()
    source.mcp_tool = "notes"
    source._meta = {
        "name": "notes",
        "description": "备忘能力",
        "risk_level": "mixed",
        "parameters": {"type": "object", "properties": {}},
        "routing": {"use_when": ["管理笔记"], "avoid_when": ["气象预警"]},
        "operations": {
            "query": {
                "tool_name": "read_notes",
                "description": "读取笔记",
                "risk_level": "read",
                "routing": {"use_when": ["个人待办"], "examples": ["我有什么事情"]},
            }
        },
    }
    operation = OperationSkill(source, "query")
    registry = SkillRegistry.from_skills([operation])
    description = registry.exposed_tools()[0]["function"]["description"]
    assert "个人待办" in description and "气象预警" in description
    assert "管理笔记" not in description
    assert source.routing["use_when"] == ["管理笔记"]
    catalog = registry.router_catalog()[0]
    assert catalog["name"] == "notes"
    assert catalog["actions"][0]["routing"]["use_when"] == ["个人待办"]
    assert "parameters" not in catalog["actions"][0]


def test_shipped_memo_and_log_boundaries_reach_both_model_paths():
    registry = loader.load_registry()
    schemas = {
        tool["function"]["name"]: tool["function"] for tool in registry.exposed_tools()
    }
    memo = schemas["query_memos"]["description"]
    assert "个人事项" in memo and "气象预警" in memo
    assert "未归档" in memo and "创建时间不是事项日期" in memo
    assert "未来待办" in schemas["query_farm_logs"]["description"]
    assert "气象预警" in schemas["get_weather"]["description"]
    # 大类示例不要复制到创建/归档等每个动作中；动作各自保留明确描述。
    assert "我明天有啥事情" not in schemas["archive_memo"]["description"]
    assert "归档" in schemas["archive_memo"]["description"]
    catalog = {item["name"]: item for item in registry.router_catalog()}
    actions = {item["name"] for item in catalog["manage_memos"]["actions"]}
    assert {"query_memos", "create_memo", "archive_memo"} <= actions
    assert "commit_planting_plan" not in {
        action["name"] for item in catalog.values() for action in item["actions"]
    }
