from app.models.crop import CropTemplate
from app.ops.system_crop_templates import (
    SYSTEM_CROP_TEMPLATES,
    seed_system_crop_templates,
)


def test_seed_system_crop_templates_is_idempotent(db_session):
    first_count = seed_system_crop_templates(db_session)
    second_count = seed_system_crop_templates(db_session)

    stored_templates = (
        db_session.query(CropTemplate).filter(CropTemplate.farm_id.is_(None)).all()
    )
    assert first_count == len(SYSTEM_CROP_TEMPLATES)
    assert second_count == 0
    assert len(stored_templates) == len(SYSTEM_CROP_TEMPLATES)


def test_seed_system_crop_templates_reloads_deleted_template(db_session):
    seed_system_crop_templates(db_session)
    deleted_template = (
        db_session.query(CropTemplate)
        .filter(CropTemplate.farm_id.is_(None))
        .filter(CropTemplate.name == SYSTEM_CROP_TEMPLATES[0]["name"])
        .filter(CropTemplate.variety == SYSTEM_CROP_TEMPLATES[0]["variety"])
        .one()
    )
    deleted_name = deleted_template.name
    deleted_variety = deleted_template.variety
    db_session.delete(deleted_template)
    db_session.commit()

    added_count = seed_system_crop_templates(db_session)

    restored_template = (
        db_session.query(CropTemplate)
        .filter(CropTemplate.farm_id.is_(None))
        .filter(CropTemplate.name == deleted_name)
        .filter(CropTemplate.variety == deleted_variety)
        .one()
    )
    assert added_count == 1
    assert len(restored_template.stages) == len(SYSTEM_CROP_TEMPLATES[0]["stages"])
    assert db_session.query(CropTemplate).filter(
        CropTemplate.farm_id.is_(None)
    ).count() == len(SYSTEM_CROP_TEMPLATES)
