import pytest

from app.domains.planting.crop_models import CropTemplate, GrowthStage
from app.domains.planting.crop_schemas import CropTemplateCreate, GrowthStageCreate
from app.domains.planting.crop_service import (
    create_crop_template,
    delete_crop_template,
    find_exact_duplicate,
    find_system_template_match,
    get_crop_template,
    get_crop_templates,
    get_system_template,
    import_system_template,
    list_system_templates,
    update_crop_template,
)


def _stage(name: str, duration_days: int, key_tasks: str | None, order_index: int):
    return GrowthStageCreate(
        name=name,
        duration_days=duration_days,
        order_index=order_index,
        key_tasks=key_tasks,
    )


def _template(
    name: str,
    variety: str | None,
    stages: list[GrowthStageCreate],
) -> CropTemplateCreate:
    return CropTemplateCreate(name=name, variety=variety, stages=stages)


def _create_system_template(
    db_session,
    name: str = "西瓜",
    variety: str | None = "8424",
    category: str | None = "水果",
) -> CropTemplate:
    template = CropTemplate(
        farm_id=None,
        name=name,
        variety=variety,
        category=category,
    )
    db_session.add(template)
    db_session.flush()
    db_session.add_all(
        [
            GrowthStage(
                crop_template_id=template.id,
                name="育苗期",
                duration_days=30,
                order_index=0,
                key_tasks="控温 保湿",
            ),
            GrowthStage(
                crop_template_id=template.id,
                name="定植期",
                duration_days=1,
                order_index=1,
                key_tasks="浇定根水",
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(template)
    return template


def test_find_exact_duplicate_hits_when_name_variety_and_stages_match(db_session):
    existing = create_crop_template(
        db_session,
        _template(
            "西瓜",
            "8424",
            [
                _stage("育苗期", 30, "控温 保湿", 0),
                _stage("定植期", 1, "浇定根水", 1),
            ],
        ),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety="8424",
        stages=[
            _stage("育苗期", 30, "控温 保湿", 0),
            _stage("定植期", 1, "浇定根水", 1),
        ],
    )

    assert duplicate is not None
    assert duplicate.id == existing.id


def test_find_exact_duplicate_ignores_same_name_with_different_variety(db_session):
    create_crop_template(
        db_session,
        _template("西瓜", "8424春季版", [_stage("育苗期", 30, "控温", 0)]),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety="8424秋季版",
        stages=[_stage("育苗期", 30, "控温", 0)],
    )

    assert duplicate is None


def test_find_exact_duplicate_ignores_same_name_variety_with_different_stages(
    db_session,
):
    create_crop_template(
        db_session,
        _template("西瓜", "8424", [_stage("育苗期", 30, "控温", 0)]),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety="8424",
        stages=[
            _stage("育苗期", 30, "控温", 0),
            _stage("伸蔓期", 20, "整枝", 1),
        ],
    )

    assert duplicate is None


def test_find_exact_duplicate_treats_stage_order_as_irrelevant(db_session):
    existing = create_crop_template(
        db_session,
        _template(
            "西瓜",
            "8424",
            [
                _stage("育苗期", 30, "控温 保湿", 0),
                _stage("定植期", 1, "浇定根水", 1),
            ],
        ),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety="8424",
        stages=[
            _stage("定植期", 1, "浇定根水", 0),
            _stage("育苗期", 30, "控温 保湿", 1),
        ],
    )

    assert duplicate is not None
    assert duplicate.id == existing.id


def test_find_exact_duplicate_preserves_duplicate_stage_counts(db_session):
    create_crop_template(
        db_session,
        _template(
            "西瓜",
            "8424",
            [
                _stage("育苗期", 30, "控温", 0),
                _stage("育苗期", 30, "控温", 1),
            ],
        ),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety="8424",
        stages=[_stage("育苗期", 30, "控温", 0)],
    )

    assert duplicate is None


def test_find_exact_duplicate_normalizes_key_tasks_whitespace(db_session):
    existing = create_crop_template(
        db_session,
        _template("西瓜", None, [_stage("育苗期", 30, "  控温\t保湿\n遮阴  ", 0)]),
        farm_id=1,
    )

    duplicate = find_exact_duplicate(
        db_session,
        farm_id=1,
        name="西瓜",
        variety=None,
        stages=[_stage("育苗期", 30, "控温 保湿 遮阴", 0)],
    )

    assert duplicate is not None
    assert duplicate.id == existing.id


def test_list_system_templates_only_returns_null_farm_and_filters_category(
    db_session,
):
    system_template = _create_system_template(db_session, category="水果")
    _create_system_template(db_session, name="番茄", variety=None, category="蔬菜")
    create_crop_template(
        db_session,
        _template("用户西瓜", "8424", [_stage("育苗期", 30, "控温", 0)]),
        farm_id=1,
    )

    all_system = list_system_templates(db_session)
    fruit_system = list_system_templates(db_session, category="水果")

    assert {template.id for template in all_system} >= {system_template.id}
    assert all(template.farm_id is None for template in all_system)
    assert [template.id for template in fruit_system] == [system_template.id]


def test_get_system_template_only_returns_null_farm_templates(db_session):
    system_template = _create_system_template(db_session)
    user_template = create_crop_template(
        db_session,
        _template("用户西瓜", "8424", [_stage("育苗期", 30, "控温", 0)]),
        farm_id=1,
    )

    assert get_system_template(db_session, system_template.id).id == system_template.id
    assert get_system_template(db_session, user_template.id) is None


def test_import_system_template_deep_copies_stages_to_farm(db_session):
    system_template = _create_system_template(db_session)

    result = import_system_template(db_session, system_template.id, farm_id=1)

    imported = get_crop_template(db_session, result.template_id, farm_id=1)
    assert result.already_exists is False
    assert imported is not None
    assert imported.id != system_template.id
    assert imported.farm_id == 1
    assert imported.name == system_template.name
    assert imported.variety == system_template.variety
    assert len(imported.stages) == len(system_template.stages)
    assert {stage.id for stage in imported.stages}.isdisjoint(
        {stage.id for stage in system_template.stages}
    )


def test_import_system_template_returns_existing_id_for_duplicate(db_session):
    system_template = _create_system_template(db_session)
    first = import_system_template(db_session, system_template.id, farm_id=1)

    second = import_system_template(db_session, system_template.id, farm_id=1)

    assert second.template_id == first.template_id
    assert second.already_exists is True
    assert len(get_crop_templates(db_session, farm_id=1)) == 1


def test_import_system_template_reimports_after_user_copy_changes(db_session):
    system_template = _create_system_template(db_session)
    first = import_system_template(db_session, system_template.id, farm_id=1)
    imported = get_crop_template(db_session, first.template_id, farm_id=1)
    imported.stages[0].duration_days = 35
    db_session.commit()

    second = import_system_template(db_session, system_template.id, farm_id=1)

    assert second.template_id != first.template_id
    assert second.already_exists is False
    assert len(get_crop_templates(db_session, farm_id=1)) == 2


def test_find_system_template_match_uses_exact_name_and_variety(db_session):
    system_template = _create_system_template(db_session, name="西瓜", variety=None)
    _create_system_template(db_session, name="小西瓜", variety=None)

    assert (
        find_system_template_match(db_session, name="西瓜", variety=None).id
        == system_template.id
    )
    assert find_system_template_match(db_session, name="瓜", variety=None) is None
    assert find_system_template_match(db_session, name="西瓜", variety="8424") is None


def test_user_template_queries_do_not_expose_system_templates(db_session):
    system_template = _create_system_template(db_session)

    assert get_crop_templates(db_session, farm_id=1) == []
    assert get_crop_template(db_session, system_template.id, farm_id=1) is None


def test_system_templates_are_write_protected(db_session):
    system_template = _create_system_template(db_session)
    update = _template("改名西瓜", "8424", [_stage("育苗期", 20, "控温", 0)])

    with pytest.raises(ValueError):
        update_crop_template(db_session, system_template.id, update, farm_id=1)
    with pytest.raises(ValueError):
        delete_crop_template(db_session, system_template.id, farm_id=1)

    unchanged = get_system_template(db_session, system_template.id)
    assert unchanged is not None
    assert unchanged.name == "西瓜"
