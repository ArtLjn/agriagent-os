"""业务根文件迁移兼容测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.prompt.registry import get_registry

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def _register_report_prompt_template():
    """报告兼容测试需要最小 prompt 模板。"""
    get_registry().register("report", "1.0", "测试报告模板 {{ current_date }}")
    yield


def test_new_business_modules_are_importable():
    """新业务落点应可直接导入。"""
    import app.application.advisor as advisor
    import app.application.report as report
    import app.platforms.evaluation.skill_coverage as skill_coverage

    assert advisor.invoke_advisor is not None
    assert report.generate_cycle_report is not None
    assert skill_coverage.list_skill_coverage_entries is not None


def test_legacy_advisor_public_api_reexports_new_objects():
    """旧 advisor 入口公开对象应转发到新模块对象。"""
    import app.agent.advisor as legacy_advisor
    import app.application.advisor as new_advisor

    assert legacy_advisor.build_advisor_agent is new_advisor.build_advisor_agent
    assert legacy_advisor.invoke_advisor is new_advisor.invoke_advisor
    assert legacy_advisor.stream_advisor is new_advisor.stream_advisor


def test_legacy_report_public_api_reexports_new_objects():
    """旧 report 入口公开对象应转发到新模块对象。"""
    import app.agent.report as legacy_report
    import app.application.report as new_report

    assert legacy_report.generate_cycle_report is new_report.generate_cycle_report


def test_legacy_skill_coverage_public_api_reexports_new_objects():
    """旧 skill_coverage 入口公开对象应转发到新模块对象。"""
    import app.agent.skill_coverage as legacy_coverage
    import app.platforms.evaluation.skill_coverage as new_coverage

    public_names = [
        "CoverageStatus",
        "SkillCoverageEntry",
        "list_skill_coverage_entries",
        "summarize_skill_coverage",
    ]
    for name in public_names:
        assert getattr(legacy_coverage, name) is getattr(new_coverage, name)


@pytest.mark.asyncio
async def test_legacy_advisor_patch_target_drives_new_execution():
    """patch 旧 advisor 图入口仍应影响新真实函数执行路径。"""
    import app.agent.advisor as legacy_advisor
    import app.application.advisor as new_advisor

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"messages": [MagicMock(content="迁移后回复")]}
    )

    with (
        patch("app.agent.advisor._get_advisor_graph", return_value=mock_graph),
        patch(
            "app.agent.advisor.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
    ):
        mock_pending.return_value = MagicMock(handled=False)
        result = await new_advisor.invoke_advisor("今天该做什么？", farm_id=1)

    assert legacy_advisor.invoke_advisor is new_advisor.invoke_advisor
    assert result == "迁移后回复"
    mock_pending.assert_awaited_once()
    mock_graph.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_report_patch_target_drives_new_execution():
    """patch 旧 report LLM 入口仍应影响新真实函数执行路径。"""
    import app.agent.report as legacy_report
    import app.application.report as new_report

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="报告内容"))

    with patch("app.agent.report._get_report_llm", return_value=mock_llm):
        result = await new_report.generate_cycle_report(cycle_id=1, farm_id=1)

    assert legacy_report.generate_cycle_report is new_report.generate_cycle_report
    assert result == "报告内容"
    mock_llm.ainvoke.assert_awaited_once()
