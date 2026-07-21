"""Context 分区渲染测试。"""

from app.context.models import ContextBlock, ContextBundle
from app.context.renderer import ContextRenderer


def _block(
    key: str,
    content: str,
    *,
    source: str = "test",
    token_estimate: int = 8,
    required: bool = False,
    is_compressed: bool = False,
) -> ContextBlock:
    return ContextBlock(
        key=key,
        source=source,
        purpose=f"{key} purpose",
        content=content,
        priority=50,
        token_estimate=token_estimate,
        required=required,
        is_compressed=is_compressed,
    )


def _bundle(blocks: list[ContextBlock]) -> ContextBundle:
    return ContextBundle(blocks=blocks, token_budget=500, token_estimate=64)


def test_renderer_renders_sections_in_stable_order() -> None:
    renderer = ContextRenderer()
    bundle = _bundle(
        [
            _block("output_contract", "必须输出 JSON"),
            _block("retrieval", "检索证据"),
            _block("pending_action", "待确认动作"),
            _block("farm", "农场上下文"),
            _block("assistant_role", "角色策略"),
        ]
    )

    text = renderer.render_prompt_text(bundle)

    section_positions = [
        text.index("## Role & Policies"),
        text.index("## Task"),
        text.index("## Evidence"),
        text.index("## Context"),
        text.index("## Output"),
    ]
    assert section_positions == sorted(section_positions)
    assert "### assistant_role\n角色策略" in text
    assert "### pending_action\n待确认动作" in text
    assert "### retrieval\n检索证据" in text
    assert "### farm\n农场上下文" in text
    assert "### output_contract\n必须输出 JSON" in text


def test_renderer_maps_common_keys_to_expected_sections() -> None:
    renderer = ContextRenderer()
    expected = {
        "pending_action": "Task",
        "temporary_task_state": "Task",
        "retrieval": "Evidence",
        "rag_knowledge": "Evidence",
        "tool_result_summary": "Evidence",
        "farm": "Context",
        "cycle": "Context",
        "weather": "Context",
        "conversation": "Context",
        "conversation_summary": "Context",
        "short_term_recent": "Context",
        "short_term_summary": "Context",
        "user_settings": "Context",
        "output_contract": "Output",
        "citation_rule": "Output",
        "clarification_rule": "Output",
    }

    for key, section_name in expected.items():
        assert renderer.section_name_for_key(key) == section_name


def test_renderer_falls_back_unknown_keys_to_context_without_dropping_content() -> None:
    renderer = ContextRenderer()
    bundle = _bundle([_block("unknown_signal", "未知但仍然有用的上下文")])

    document = renderer.render_document(bundle)
    text = document.render_prompt_text()

    assert document.sections[3].name == "Context"
    assert document.sections[3].blocks[0].key == "unknown_signal"
    assert "未知但仍然有用的上下文" in text


def test_renderer_debug_summary_keeps_metadata_without_large_content() -> None:
    renderer = ContextRenderer()
    long_content = "很长的正文" * 80
    bundle = _bundle(
        [
            _block(
                "retrieval",
                long_content,
                source="rag",
                token_estimate=123,
                required=True,
                is_compressed=True,
            )
        ]
    )

    summary = renderer.debug_summary(bundle)

    evidence = summary["sections"][0]
    assert evidence["name"] == "Evidence"
    assert evidence["token_estimate"] == 123
    assert evidence["blocks"] == [
        {
            "key": "retrieval",
            "source": "rag",
            "token_estimate": 123,
            "required": True,
            "is_compressed": True,
            "purpose": "retrieval purpose",
            "reason": "",
        }
    ]
    assert long_content not in str(summary)


def test_context_bundle_summary_includes_section_debug_view() -> None:
    bundle = _bundle([_block("output_contract", "必须给出引用")])

    summary = bundle.summary()

    assert summary["sections"][0]["name"] == "Output"
    assert summary["sections"][0]["blocks"][0]["key"] == "output_contract"


def test_context_bundle_summary_sections_are_not_overridden_by_metadata() -> None:
    bundle = _bundle([_block("retrieval", "证据内容")])
    bundle.metadata["sections"] = [{"name": "stale"}]

    summary = bundle.summary()

    assert summary["sections"][0]["name"] == "Evidence"
    assert summary["sections"][0]["blocks"][0]["key"] == "retrieval"
