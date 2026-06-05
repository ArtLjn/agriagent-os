"""Skill metadata contract tests。"""

from app.agent import skills as skills_module
from app.agent.skills import (
    get_skill_manager,
    get_skill_registry,
    skills_to_langchain_tools,
)
from app.agent.skills.metadata import (
    SkillMetadata,
    SkillPermissionLevel,
    SkillRiskLevel,
    get_skill_metadata,
    metadata_to_dict,
)


class _ReadSkill:
    def name(self):
        return "get_farm_status"

    def description(self):
        return "读取农场状态"

    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, params, context):
        return None


class _WriteSkill:
    def name(self):
        return "create_cost_record"


class _WriteSkillWithMetadata:
    def name(self):
        return "create_cost_record"

    def metadata(self):
        return {
            "permission_level": "write_confirm",
            "risk_level": "medium",
            "cache_invalidation": ["custom_group"],
        }


class _ExternalNetworkSkill:
    def name(self):
        return "web_search"


class _CustomSkill:
    def name(self):
        return "custom_admin_task"

    def metadata(self):
        return {
            "permission_level": "admin",
            "risk_level": "high",
            "context_dependencies": ["farm", "ledger"],
            "cache_invalidation": ["get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["farm_id"],
                "changed_fields": ["status"],
                "inferred_fields": [],
                "editable_fields": ["status"],
            },
            "evaluation_tags": ["admin"],
            "enabled": False,
            "disabled_reason": "仅测试自定义覆盖",
        }


class _AttributeMetadataSkill:
    metadata = {
        "permission_level": "admin",
        "risk_level": "high",
        "context_dependencies": ["farm"],
    }

    def name(self):
        return "attribute_metadata_task"


class _SkillDefinition:
    name = "get_farm_status"


class _SkillManager:
    def __init__(self, skill):
        self._skill = skill

    def list_skills(self):
        return [_SkillDefinition()]

    def get_skill(self, name):
        return self._skill if name == "get_farm_status" else None


def test_default_read_skill_metadata():
    metadata = get_skill_metadata(_ReadSkill())

    assert metadata.permission_level == SkillPermissionLevel.READ
    assert metadata.risk_level == SkillRiskLevel.LOW
    assert metadata.enabled is True
    assert metadata.disabled_reason is None
    assert metadata.metadata_incomplete is False


def test_default_write_skill_metadata():
    metadata = get_skill_metadata(_WriteSkill())

    assert metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM
    assert metadata.risk_level == SkillRiskLevel.MEDIUM
    assert "get_farm_status" in metadata.cache_invalidation
    assert metadata.confirmation_schema.risk_notes == []
    assert metadata.enabled is True
    assert metadata.disabled_reason is None
    assert metadata.metadata_incomplete is False


def test_known_write_skill_metadata_uses_governed_cache_invalidation():
    metadata = get_skill_metadata(_WriteSkillWithMetadata())

    assert metadata.cache_invalidation == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]


def test_default_external_network_skill_metadata():
    metadata = get_skill_metadata(_ExternalNetworkSkill())

    assert metadata.permission_level == SkillPermissionLevel.EXTERNAL_NETWORK
    assert metadata.risk_level == SkillRiskLevel.LOW
    assert metadata.enabled is False
    assert metadata.disabled_reason == "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"
    assert metadata.metadata_incomplete is False


def test_custom_metadata_is_parsed():
    metadata = get_skill_metadata(_CustomSkill())

    assert isinstance(metadata, SkillMetadata)
    assert metadata.permission_level == SkillPermissionLevel.ADMIN
    assert metadata.risk_level == SkillRiskLevel.HIGH
    assert metadata.context_dependencies == ["farm", "ledger"]
    assert metadata.enabled is False
    assert metadata.disabled_reason == "仅测试自定义覆盖"
    assert metadata.metadata_incomplete is False


def test_attribute_metadata_is_parsed():
    metadata = get_skill_metadata(_AttributeMetadataSkill())

    assert metadata.permission_level == SkillPermissionLevel.ADMIN
    assert metadata.risk_level == SkillRiskLevel.HIGH
    assert metadata.context_dependencies == ["farm"]
    assert metadata.metadata_incomplete is False


def test_metadata_to_dict_includes_confirmation_risk_notes():
    metadata = metadata_to_dict(_ReadSkill())

    assert metadata["confirmation_schema"]["risk_notes"] == []
    assert metadata["enabled"] is True
    assert metadata["disabled_reason"] is None


def test_registered_runtime_skills_have_complete_metadata():
    manager = get_skill_manager()
    incomplete = {}
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill is not None:
            metadata = get_skill_metadata(skill)
            if metadata.metadata_incomplete:
                incomplete[skill_def.name] = metadata.model_dump(mode="json")

    assert incomplete == {}


def test_langchain_tool_has_skill_metadata(monkeypatch):
    monkeypatch.setattr("app.agent.skills.get_category_enum", lambda farm_id: [])

    tools = skills_to_langchain_tools(_SkillManager(_ReadSkill()))

    assert len(tools) == 1
    assert tools[0].skill_metadata.permission_level == SkillPermissionLevel.READ


def test_registry_skill_has_skill_metadata(monkeypatch):
    monkeypatch.setattr(skills_module, "_SKILL_REGISTRY", {})
    monkeypatch.setattr(
        "app.agent.skills.get_skill_manager",
        lambda: _SkillManager(_ReadSkill()),
    )

    registry = get_skill_registry()

    assert registry["get_farm_status"].skill_metadata.permission_level == (
        SkillPermissionLevel.READ
    )
