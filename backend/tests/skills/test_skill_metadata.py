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
    get_skill_call_metadata,
    get_skill_metadata,
    metadata_to_dict,
    resolve_skill_capability_metadata,
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


class _ManageWorkOrdersSkill:
    def name(self):
        return "manage_work_orders"


class _WriteSkillWithMetadata:
    def name(self):
        return "create_cost_record"

    def metadata(self):
        return {
            "permission_level": "write_confirm",
            "risk_level": "medium",
            "cache_invalidation": ["custom_group"],
        }


class _WriteSkillWithExplicitRegistryOverlap:
    def name(self):
        return "create_cost_record"

    def metadata(self):
        return {
            "permission_level": "write_confirm",
            "risk_level": "medium",
            "context_dependencies": ["explicit_context"],
            "evaluation_tags": ["explicit_tag"],
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
    assert "cost_records" in metadata.context_dependencies
    assert "get_farm_status" in metadata.cache_invalidation
    assert metadata.confirmation_schema.risk_notes == []
    assert metadata.enabled is True
    assert metadata.disabled_reason is None
    assert metadata.metadata_incomplete is False


def test_manage_work_orders_permission_depends_on_operation():
    skill = _ManageWorkOrdersSkill()

    assert (
        get_skill_call_metadata(
            skill,
            {"operation": "create_work_order"},
        ).permission_level
        == SkillPermissionLevel.WRITE_CONFIRM
    )
    assert (
        get_skill_call_metadata(
            skill,
            {"operation": "query_work_orders"},
        ).permission_level
        == SkillPermissionLevel.READ
    )
    assert (
        get_skill_call_metadata(
            skill,
            {"operation": "update_work_order"},
        ).permission_level
        == SkillPermissionLevel.WRITE_CONFIRM
    )


def test_known_write_skill_metadata_uses_governed_cache_invalidation():
    metadata = get_skill_metadata(_WriteSkillWithMetadata())

    assert metadata.cache_invalidation == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]


def test_explicit_skill_metadata_overrides_registry_defaults():
    metadata = get_skill_metadata(_WriteSkillWithExplicitRegistryOverlap())

    assert metadata.context_dependencies == ["explicit_context"]
    assert metadata.evaluation_tags == ["explicit_tag"]
    assert metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_registry_operation_risk_maps_to_runtime_risk():
    class _DeleteCropCycleSkill:
        def name(self):
            return "delete_crop_cycle"

    metadata = get_skill_metadata(_DeleteCropCycleSkill())

    assert metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM
    assert metadata.risk_level == SkillRiskLevel.HIGH


def test_manage_settings_legacy_metadata_uses_shared_capability_operations():
    class _GetUserSettingsSkill:
        def name(self):
            return "get_user_settings"

    class _ManageUserSettingsSkill:
        def name(self):
            return "manage_user_settings"

    query_metadata = get_skill_metadata(_GetUserSettingsSkill())
    update_metadata = get_skill_metadata(_ManageUserSettingsSkill())

    assert query_metadata.capability == "manage_settings"
    assert query_metadata.operation == "query_settings"
    assert query_metadata.operation_risk == "read"
    assert query_metadata.permission_level == SkillPermissionLevel.READ
    assert update_metadata.capability == "manage_settings"
    assert update_metadata.operation == "update_settings"
    assert update_metadata.operation_risk == "write_confirm"
    assert update_metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_manage_workers_legacy_metadata_uses_shared_capability_operations():
    class _GetWorkersSkill:
        def name(self):
            return "get_workers"

    class _ManageWorkersSkill:
        def name(self):
            return "manage_workers"

    query_metadata = get_skill_metadata(_GetWorkersSkill())
    manage_metadata = get_skill_metadata(_ManageWorkersSkill())

    assert query_metadata.capability == "manage_workers"
    assert query_metadata.operation == "query_workers"
    assert query_metadata.operation_risk == "read"
    assert query_metadata.permission_level == SkillPermissionLevel.READ
    assert manage_metadata.capability == "manage_workers"
    assert manage_metadata.operation == "manage_worker"
    assert manage_metadata.operation_risk == "write_confirm"
    assert manage_metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_manage_planting_units_legacy_metadata_uses_shared_capability_operations():
    class _GetPlantingUnitsSkill:
        def name(self):
            return "get_planting_units"

    class _ManagePlantingUnitsSkill:
        def name(self):
            return "manage_planting_units"

    query_metadata = get_skill_metadata(_GetPlantingUnitsSkill())
    manage_metadata = get_skill_metadata(_ManagePlantingUnitsSkill())

    assert query_metadata.capability == "manage_planting_units"
    assert query_metadata.operation == "query_units"
    assert query_metadata.operation_risk == "read"
    assert query_metadata.permission_level == SkillPermissionLevel.READ
    assert manage_metadata.capability == "manage_planting_units"
    assert manage_metadata.operation == "manage_units"
    assert manage_metadata.operation_risk == "write_confirm"
    assert manage_metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_manage_cost_categories_legacy_metadata_uses_shared_capability_operations():
    class _GetCostCategoriesSkill:
        def name(self):
            return "get_cost_categories"

    class _ManageCostCategoriesSkill:
        def name(self):
            return "manage_cost_categories"

    query_metadata = get_skill_metadata(_GetCostCategoriesSkill())
    manage_metadata = get_skill_metadata(_ManageCostCategoriesSkill())

    assert query_metadata.capability == "manage_cost_categories"
    assert query_metadata.operation == "query_categories"
    assert query_metadata.operation_risk == "read"
    assert query_metadata.permission_level == SkillPermissionLevel.READ
    assert manage_metadata.capability == "manage_cost_categories"
    assert manage_metadata.operation == "manage_category"
    assert manage_metadata.operation_risk == "write_confirm"
    assert manage_metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_manage_farm_logs_legacy_metadata_uses_shared_capability_operations():
    class _LogFarmActivitySkill:
        def name(self):
            return "log_farm_activity"

    class _GetRecentFarmLogsSkill:
        def name(self):
            return "get_recent_farm_logs"

    query_metadata = get_skill_metadata(_GetRecentFarmLogsSkill())
    create_metadata = get_skill_metadata(_LogFarmActivitySkill())

    assert query_metadata.capability == "manage_farm_logs"
    assert query_metadata.operation == "query_logs"
    assert query_metadata.operation_risk == "read"
    assert query_metadata.permission_level == SkillPermissionLevel.READ
    assert create_metadata.capability == "manage_farm_logs"
    assert create_metadata.operation == "create_log"
    assert create_metadata.operation_risk == "write_confirm"
    assert create_metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM


def test_manage_farm_logs_canonical_operation_overrides_self_alias():
    query_metadata = resolve_skill_capability_metadata(
        "manage_farm_logs", "query_logs"
    )
    manage_metadata = resolve_skill_capability_metadata(
        "manage_farm_logs", "manage_log"
    )

    assert query_metadata is not None
    assert query_metadata["capability"] == "manage_farm_logs"
    assert query_metadata["operation"] == "query_logs"
    assert query_metadata["operation_risk"] == "read"
    assert manage_metadata is not None
    assert manage_metadata["operation"] == "manage_log"
    assert manage_metadata["operation_risk"] == "write_confirm"


def test_manage_user_settings_physical_skill_operation_overrides_update_alias():
    query_metadata = resolve_skill_capability_metadata(
        "manage_user_settings", "query_settings"
    )
    update_metadata = resolve_skill_capability_metadata(
        "manage_user_settings", "update_settings"
    )
    legacy_query_metadata = resolve_skill_capability_metadata("get_user_settings")
    legacy_update_metadata = resolve_skill_capability_metadata("manage_user_settings")

    assert query_metadata is not None
    assert query_metadata["capability"] == "manage_settings"
    assert query_metadata["operation"] == "query_settings"
    assert query_metadata["operation_risk"] == "read"
    assert query_metadata["permission_level"] == SkillPermissionLevel.READ
    assert update_metadata is not None
    assert update_metadata["operation"] == "update_settings"
    assert update_metadata["operation_risk"] == "write_confirm"
    assert legacy_query_metadata is not None
    assert legacy_query_metadata["operation"] == "query_settings"
    assert legacy_query_metadata["operation_risk"] == "read"
    assert legacy_update_metadata is not None
    assert legacy_update_metadata["operation"] == "update_settings"
    assert legacy_update_metadata["operation_risk"] == "write_confirm"


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
