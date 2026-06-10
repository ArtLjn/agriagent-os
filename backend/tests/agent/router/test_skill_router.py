"""Skill Catalog 测试。"""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from app.agent.router.catalog import SkillCatalog

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_catalog_enriches_work_order_metadata() -> None:
    catalog = SkillCatalog.from_tools(
        [
            _tool(
                "create_operation_work_order",
                "创建农事作业单，可同时记录多个工人",
            )
        ]
    )

    candidate = catalog.get("create_operation_work_order")

    assert candidate is not None
    assert candidate.domain == "operation"
    assert candidate.risk == "write_confirm"
    assert "create_work_order" in candidate.intents
    assert "workers" in candidate.context_dependencies
    assert "今天李树去6号棚收水稻" in candidate.trigger_examples


def test_catalog_marks_disabled_tools() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": False})()

    catalog = SkillCatalog.from_tools([tool])

    assert catalog.get("web_search").enabled is False


def test_catalog_falls_back_to_disabled_skills() -> None:
    catalog = SkillCatalog.from_tools([_tool("web_search")])

    assert catalog.get("web_search").enabled is False


def test_catalog_metadata_enabled_overrides_disabled_skills() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()

    catalog = SkillCatalog.from_tools([tool])

    assert catalog.get("web_search").enabled is True


def test_catalog_defaults_write_skill_risk() -> None:
    catalog = SkillCatalog.from_tools([_tool("create_cost_record")])

    assert catalog.get("create_cost_record").risk == "write_confirm"


def test_catalog_estimates_schema_tokens_from_pydantic_fields() -> None:
    class WorkOrderArgs(BaseModel):
        worker_name: str = Field(
            description="工人姓名，用于从工人档案中匹配具体作业人员"
        )
        planting_unit_name: str = Field(
            description="种植单元名称，用于定位地块、大棚或棚区"
        )
        operation_type: str = Field(
            description="农事作业类型，例如采收、授粉、整枝、打杈、装车"
        )
        quantity: int = Field(description="作业数量或用工数量，必须是正整数")

    tool_with_schema = _tool("custom_schema_tool", "创建作业单")
    tool_with_schema.args_schema = WorkOrderArgs
    tool_without_schema = _tool("custom_schema_tool", "创建作业单")
    tool_without_schema.args_schema = None

    catalog_with_schema = SkillCatalog.from_tools([tool_with_schema])
    catalog_without_schema = SkillCatalog.from_tools([tool_without_schema])

    with_schema = catalog_with_schema.get("custom_schema_tool")
    without_schema = catalog_without_schema.get("custom_schema_tool")

    assert with_schema.schema_token_estimate > 300
    assert with_schema.schema_token_estimate > without_schema.schema_token_estimate
