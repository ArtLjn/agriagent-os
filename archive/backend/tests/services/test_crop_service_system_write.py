import pytest

from app.domains.planting.crop_models import CropTemplate, GrowthStage
from app.domains.farm.models import Farm
from app.domains.planting.crop_schemas import CropTemplateCreate, GrowthStageCreate
from app.domains.planting import crop_service


def _payload(name: str = "西瓜", variety: str | None = "8424"):
    return CropTemplateCreate(
        name=name,
        variety=variety,
        category="水果",
        stages=[
            GrowthStageCreate(name="育苗期", duration_days=30, order_index=0, key_tasks="控温"),
            GrowthStageCreate(name="定植期", duration_days=1, order_index=1, key_tasks="浇水"),
        ],
    )


def test_create_system_crop_template_persists_with_null_farm_id(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())

    assert template.id is not None
    assert template.farm_id is None
    assert template.name == "西瓜"
    assert template.variety == "8424"
    assert template.category == "水果"
    assert [s.name for s in template.stages] == ["育苗期", "定植期"]


def test_update_system_crop_template_replaces_stages(db_session):
    existing = crop_service.create_system_crop_template(db_session, _payload())

    updated = crop_service.update_system_crop_template(
        db_session,
        existing.id,
        CropTemplateCreate(
            name="改名西瓜",
            variety="8424",
            category="水果",
            stages=[
                GrowthStageCreate(name="新育苗期", duration_days=20, order_index=0, key_tasks=None),
            ],
        ),
    )

    assert updated.id == existing.id
    assert updated.name == "改名西瓜"
    assert [s.name for s in updated.stages] == ["新育苗期"]
    assert db_session.query(GrowthStage).count() == 1


def test_update_system_crop_template_raises_when_not_found(db_session):
    with pytest.raises(ValueError, match="系统模板 99999 不存在"):
        crop_service.update_system_crop_template(db_session, 99999, _payload())


def test_delete_system_crop_template_removes_template_and_stages(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())

    crop_service.delete_system_crop_template(db_session, template.id)

    assert db_session.query(CropTemplate).count() == 0
    assert db_session.query(GrowthStage).count() == 0


def test_delete_system_crop_template_raises_when_imported_by_farm(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())
    db_session.add(Farm(id=2, name="第二农场", user_id="test-user-002"))
    db_session.commit()
    db_session.add(CropTemplate(farm_id=1, name="西瓜", variety="8424", category="水果"))
    db_session.add(CropTemplate(farm_id=2, name="西瓜", variety="8424", category="水果"))
    db_session.commit()

    with pytest.raises(ValueError, match="已被 2 个农场导入"):
        crop_service.delete_system_crop_template(db_session, template.id)


def test_count_farm_template_imports_matches_by_name_and_variety(db_session):
    db_session.add(Farm(id=2, name="第二农场", user_id="test-user-002"))
    db_session.commit()
    db_session.add_all([
        CropTemplate(farm_id=1, name="西瓜", variety="8424", category="水果"),
        CropTemplate(farm_id=2, name="西瓜", variety="8424", category="水果"),
        CropTemplate(farm_id=1, name="西瓜", variety="其他品种", category="水果"),
    ])
    db_session.commit()

    count = crop_service.count_farm_template_imports(db_session, name="西瓜", variety="8424")
    assert count == 2
