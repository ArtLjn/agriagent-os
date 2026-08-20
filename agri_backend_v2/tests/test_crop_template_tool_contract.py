"""作物模板 MCP 边界契约测试。"""

from __future__ import annotations

from contextlib import contextmanager

from business.tools import crop_templates
from agent.skills import loader


class _FakeDb:
    pass


def test_create_template_returns_structured_error_for_missing_duration(
    monkeypatch,
) -> None:
    called = False

    @contextmanager
    def fake_session_scope():
        yield _FakeDb()

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("无效阶段不应进入查重或写库")

    monkeypatch.setattr(crop_templates, "get_farm_id_from_headers", lambda: 1)
    monkeypatch.setattr(crop_templates, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        crop_templates.crop_service, "find_exact_duplicate", fail_if_called
    )

    result = crop_templates.manage_crop_templates(
        operation="create",
        name="西瓜8424",
        variety="早佳8424",
        category="瓜果类",
        stages=[{"name": "育苗期", "description": "种子发芽至 3-4 片真叶"}],
    )

    assert result == {
        "error": "invalid_stage_duration",
        "code": "invalid_stage_duration",
        "message": "stages[0].duration_days 必须是 1-3650 的整数",
        "retryable": False,
        "context": {"field": "stages[0].duration_days"},
    }
    assert called is False


def test_create_template_passes_complete_stage_contract_to_service(monkeypatch) -> None:
    captured = {}

    @contextmanager
    def fake_session_scope():
        yield _FakeDb()

    def fake_find_duplicate(*_args, **_kwargs):
        return None

    def fake_create(_db, **kwargs):
        captured.update(kwargs)
        return {"id": 42, "name": kwargs["name"], "stages": kwargs["stages"]}

    monkeypatch.setattr(crop_templates, "get_farm_id_from_headers", lambda: 1)
    monkeypatch.setattr(crop_templates, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        crop_templates.crop_service, "find_exact_duplicate", fake_find_duplicate
    )
    monkeypatch.setattr(
        crop_templates.crop_service, "create_crop_template", fake_create
    )

    result = crop_templates.manage_crop_templates(
        operation="create",
        name="西瓜8424",
        variety="早佳8424",
        category="瓜果类",
        stages=[
            {
                "name": "育苗期",
                "duration_days": 15,
                "order_index": 0,
                "key_tasks": "播种、温湿度管理",
                "description": "不会透传到写库层",
            }
        ],
    )

    assert result["id"] == 42
    assert captured["stages"] == [
        {
            "name": "育苗期",
            "duration_days": 15,
            "order_index": 0,
            "key_tasks": "播种、温湿度管理",
        }
    ]


def test_create_template_schema_requires_stage_duration_and_order() -> None:
    skill = next(
        skill
        for skill in loader.SkillLoader(loader._SKILLS_DIR).load_all()
        if skill.name == "create_crop_template"
    )
    stages = skill.parameters_schema["properties"]["stages"]

    assert stages["minItems"] == 1
    assert stages["items"]["required"] == ["name", "duration_days", "order_index"]
