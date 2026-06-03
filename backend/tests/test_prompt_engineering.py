"""Prompt 工程化边界测试。"""

from datetime import date
from pathlib import Path

from app.prompt.composer import PromptComposer
from app.prompt.models import PromptInput, PromptLayer
from app.prompt.registry import PromptRegistry
from app.prompt.replay import PromptReplayCase, compare_prompt_versions
from app.prompt.renderer import render_prompt_input

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _composer() -> PromptComposer:
    reg = PromptRegistry()
    reg.reload(_PROMPTS_DIR)
    return PromptComposer(reg, _PROMPTS_DIR)


def test_registry_tracks_active_version_explicitly():
    reg = PromptRegistry()
    reg.register("system_base", "1.0", "版本一")
    reg.register("system_base", "2.0", "版本二")

    assert reg.active_version("system_base") == "1.0"
    assert reg.get("system_base") == "版本一"

    reg.set_active_version("system_base", "2.0")

    assert reg.active_version("system_base") == "2.0"
    assert reg.get("system_base") == "版本二"


def test_composer_exposes_layered_snippets_in_policy_order():
    composer = _composer()

    snippets = composer.list_layered_snippets("system_base")
    layers = [snippet.layer for snippet in snippets]

    assert PromptLayer.SAFETY in layers
    assert PromptLayer.ROLE in layers
    assert PromptLayer.CAPABILITY in layers
    assert PromptLayer.TOOL in layers
    assert PromptLayer.CONTEXT in layers
    assert PromptLayer.OUTPUT in layers
    assert PromptLayer.STYLE in layers
    assert layers.index(PromptLayer.SAFETY) < layers.index(PromptLayer.ROLE)
    assert layers.index(PromptLayer.CONTEXT) < layers.index(PromptLayer.OUTPUT)


def test_render_prompt_input_uses_structured_input_only():
    reg = PromptRegistry()
    reg.register(
        "cost_parse",
        "1.0",
        "今天 {{ current_date }}，描述 {{ description }}。",
    )

    prompt_input = PromptInput(
        variables={"description": "昨天买化肥200"},
        current_date=date(2026, 5, 29),
    )

    assert (
        render_prompt_input("cost_parse", prompt_input, registry=reg)
        == "今天 2026-05-29，描述 昨天买化肥200。"
    )


def test_system_prompt_snapshot_covers_layered_output():
    result = _composer().compose(
        "system_base",
        PromptInput(
            variables={
                "display_name": "老李",
                "farm_location": "苏州",
                "current_season": "夏季",
            },
            current_date=date(2026, 5, 29),
        ),
    )

    assert result.startswith("【语言规则】")
    assert "【安全护栏】" in result
    assert "【角色定义】" in result
    assert "【能力范围】" in result
    assert "【工具调用规范】" in result
    assert result.index("【时间信息】") < result.index("【回复格式】")
    assert "<location>苏州</location>" in result
    assert result.count("【语言规则】") == 1


def test_business_parse_prompt_snapshot_covers_cost_parse():
    result = _composer().compose(
        "cost_parse",
        PromptInput(
            variables={"description": "昨天买化肥花了200"},
            current_date=date(2026, 5, 29),
        ),
    )

    assert result.startswith("【语言规则】")
    assert "【任务说明】" in result
    assert "昨天买化肥花了200" in result
    assert '"record_date": "2026-05-28"' in result


def test_prompt_replay_can_compare_two_versions_manually():
    reg = PromptRegistry()
    reg.register("cost_parse", "1.0", "描述：{{ description }}")
    reg.register("cost_parse", "2.0", "记账描述：{{ description }}")
    case = PromptReplayCase(
        name="cost parse smoke",
        prompt_name="cost_parse",
        prompt_input=PromptInput(
            variables={"description": "人工费300"},
            current_date=date(2026, 5, 29),
        ),
    )

    result = compare_prompt_versions(reg, case, "1.0", "2.0")

    assert result.case_name == "cost parse smoke"
    assert result.base_version == "1.0"
    assert result.candidate_version == "2.0"
    assert result.base_output == "描述：人工费300"
    assert result.candidate_output == "记账描述：人工费300"
    assert result.changed is True
