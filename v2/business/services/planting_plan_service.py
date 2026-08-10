"""种植计划聚合用例。

该模块是 Agent 种植目标与 Business CRUD Service 之间的边界。Agent 只提交规范化
计划和一次确认，模板、茬口、种植单元的事务顺序、匹配校验和幂等由这里统一保证。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from business.models import Farm, PlantingPlanExecution
from business.services import crop_service, cycle_service, work_order_service


class PlantingPlanError(ValueError):
    """可安全返回给 Agent 的业务错误。"""

    def __init__(self, code: str, message: str, **context: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _new_request_id() -> str:
    return str(uuid.uuid4())


def _normalize_location(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"[\s,，。;；]+", "", text).lower()


def _validate_planting_location(
    db: Session,
    *,
    farm_id: int,
    field_location: str | None,
    field_location_confirmed: bool,
) -> None:
    if not field_location or field_location_confirmed:
        return
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    farm_location = str(farm.location or "").strip() if farm else ""
    normalized_farm = _normalize_location(farm_location)
    normalized_field = _normalize_location(field_location)
    if (
        normalized_farm
        and normalized_field
        and normalized_farm not in normalized_field
        and normalized_field not in normalized_farm
    ):
        raise PlantingPlanError(
            "planting_location_ambiguous",
            "农场默认位置与目标地块位置不一致，请确认本次计划应使用哪个位置",
            farm_location=farm_location,
            field_location=field_location,
        )


def _require_positive_area(value: Any) -> float | None:
    if value is None:
        return None
    try:
        area = float(value)
    except (TypeError, ValueError) as exc:
        raise PlantingPlanError("invalid_area", "种植面积必须是有效数字") from exc
    if area <= 0:
        raise PlantingPlanError("invalid_area", "种植面积必须大于 0")
    return area


def _parse_start_date(value: str | date | None) -> str:
    if value is None:
        raise PlantingPlanError("missing_start_date", "请提供计划开始日期")
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise PlantingPlanError(
            "invalid_start_date", "计划开始日期必须是 YYYY-MM-DD"
        ) from exc


def _validate_stages(stages: Any) -> list[dict[str, Any]]:
    if not isinstance(stages, list) or not stages:
        raise PlantingPlanError(
            "custom_template_required",
            "自定义模板至少需要一个生长阶段",
            missing=["custom_template.stages"],
        )
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(stages):
        if not isinstance(raw, dict) or not raw.get("name"):
            raise PlantingPlanError(
                "invalid_template_stage",
                f"第 {index + 1} 个生长阶段缺少名称",
            )
        try:
            duration = int(raw["duration_days"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlantingPlanError(
                "invalid_template_stage",
                f"第 {index + 1} 个生长阶段的 duration_days 无效",
            ) from exc
        if duration < 1 or duration > 3650:
            raise PlantingPlanError(
                "invalid_template_stage",
                f"第 {index + 1} 个生长阶段的 duration_days 超出范围",
            )
        normalized.append(
            {
                "name": str(raw["name"]).strip(),
                "duration_days": duration,
                "order_index": int(raw.get("order_index", index)),
                "key_tasks": raw.get("key_tasks"),
            }
        )
    return normalized


def _template_summary(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": template.get("id"),
        "name": template.get("name"),
        "variety": template.get("variety"),
        "category": template.get("category"),
        "stages": template.get("stages") or [],
    }


def _build_custom_template_plan(
    *,
    crop_name: str,
    variety: str | None,
    custom_template: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    custom = custom_template or {}
    template_name = str(custom.get("name") or crop_name).strip()
    if crop_service.normalize_crop_name(
        template_name
    ) != crop_service.normalize_crop_name(crop_name):
        raise PlantingPlanError(
            "crop_template_mismatch",
            f"自定义模板名称 {template_name} 与目标作物 {crop_name} 不一致",
            crop_name=crop_name,
            template_name=template_name,
        )
    return "create_custom", {
        "name": template_name,
        "variety": custom.get("variety", variety),
        "category": custom.get("category"),
        "stages": _validate_stages(custom.get("stages")),
    }


def _resolve_template_plan(
    db: Session,
    *,
    farm_id: int,
    crop_name: str,
    variety: str | None,
    strategy: str,
    template_id: int | None,
    system_template_id: int | None,
    custom_template: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    normalized_crop = crop_service.normalize_crop_name(crop_name)
    if strategy not in {"auto", "existing", "import_system", "create_custom"}:
        raise PlantingPlanError("invalid_template_strategy", "模板策略无效")

    if strategy in {"auto", "existing"}:
        local = (
            crop_service.get_crop_template(db, template_id, farm_id)
            if template_id is not None
            else crop_service.find_local_template_match(
                db, farm_id=farm_id, crop_name=crop_name, variety=variety
            )
        )
        if local is not None:
            if crop_service.normalize_crop_name(local["name"]) != normalized_crop:
                raise PlantingPlanError(
                    "crop_template_mismatch",
                    f"目标作物 {crop_name} 与模板 {local['name']} 不一致",
                    crop_name=crop_name,
                    template_name=local["name"],
                )
            return "use_existing", _template_summary(local) | {
                "farm_template_id": local["id"]
            }
        if strategy == "existing":
            raise PlantingPlanError(
                "crop_template_not_found", "指定的农场模板不存在或不属于当前农场"
            )

    if strategy in {"auto", "import_system"}:
        system = (
            crop_service.get_system_template(db, system_template_id)
            if system_template_id is not None
            else crop_service.find_system_template_match(db, crop_name, variety)
        )
        if system is not None:
            if crop_service.normalize_crop_name(system["name"]) != normalized_crop:
                raise PlantingPlanError(
                    "crop_template_mismatch",
                    f"目标作物 {crop_name} 与系统模板 {system['name']} 不一致",
                    crop_name=crop_name,
                    template_name=system["name"],
                )
            return "import_system", _template_summary(system) | {
                "system_template_id": system["id"]
            }
        if strategy == "import_system":
            raise PlantingPlanError("system_template_not_found", "指定的系统模板不存在")

    if strategy == "auto" and custom_template is None:
        raise PlantingPlanError(
            "custom_template_required",
            f"农场和系统均没有 {crop_name} 模板，需要先提供自定义模板阶段",
            missing=["custom_template.stages"],
        )

    return _build_custom_template_plan(
        crop_name=crop_name,
        variety=variety,
        custom_template=custom_template,
    )


def prepare_planting_plan(
    db: Session,
    *,
    farm_id: int,
    crop_name: str,
    total_area_mu: float | None = None,
    field_name: str | None = None,
    field_location: str | None = None,
    field_location_confirmed: bool = False,
    start_date: str | date | None = None,
    cycle_name: str | None = None,
    variety: str | None = None,
    template_strategy: str = "auto",
    template_id: int | None = None,
    system_template_id: int | None = None,
    custom_template: dict[str, Any] | None = None,
    advisory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成不落业务数据的可审批计划。"""
    if not crop_name or not str(crop_name).strip():
        raise PlantingPlanError("missing_crop_name", "请提供目标作物名称")
    if not field_name or not str(field_name).strip():
        raise PlantingPlanError("missing_field_name", "请提供需要创建的地块名称")
    _validate_planting_location(
        db,
        farm_id=farm_id,
        field_location=field_location,
        field_location_confirmed=field_location_confirmed,
    )
    area = _require_positive_area(total_area_mu)
    normalized_date = _parse_start_date(start_date)
    action, template = _resolve_template_plan(
        db,
        farm_id=farm_id,
        crop_name=crop_name,
        variety=variety,
        strategy=template_strategy,
        template_id=template_id,
        system_template_id=system_template_id,
        custom_template=custom_template,
    )
    advisory_data = dict(advisory or {})
    if field_location:
        advisory_data.setdefault("location", field_location)
    plan = {
        "crop_name": str(crop_name).strip(),
        "variety": variety,
        "template_action": action,
        "template": template,
        "cycle": {
            "name": cycle_name or f"{str(crop_name).strip()}种植计划",
            "start_date": normalized_date,
            "total_area_mu": area,
            "field_name": str(field_name).strip(),
        },
        "planting_unit": {
            "name": str(field_name).strip(),
            "area_mu": area,
            "planted_date": normalized_date,
            "note": field_location,
        },
        "advisory": advisory_data,
        "field_location_confirmed": field_location_confirmed,
    }
    request_id = _new_request_id()
    fingerprint = _fingerprint(plan)
    return {
        "status": "ready",
        "client_request_id": request_id,
        "approval_fingerprint": fingerprint,
        "plan": plan,
        "approval_summary": (
            f"将{action_text(action)}模板、创建 1 个 {plan['crop_name']} 茬口和 "
            f"1 个 {plan['cycle']['total_area_mu']} 亩种植单元。"
        ),
    }


def action_text(action: str) -> str:
    return {
        "use_existing": "复用现有",
        "import_system": "导入系统",
        "create_custom": "创建自定义",
    }.get(action, "处理")


def _load_idempotent_result(
    db: Session,
    *,
    farm_id: int,
    client_request_id: str,
    request_fingerprint: str,
) -> dict[str, Any] | None:
    existing = (
        db.query(PlantingPlanExecution)
        .filter(
            PlantingPlanExecution.farm_id == farm_id,
            PlantingPlanExecution.client_request_id == client_request_id,
        )
        .with_for_update()
        .first()
    )
    if existing is None:
        return None
    if existing.request_fingerprint != request_fingerprint:
        raise PlantingPlanError(
            "idempotency_conflict",
            "同一个请求 ID 已经对应另一份种植计划",
        )
    return dict(existing.result_json or {}) | {"idempotent_replay": True}


def load_committed_planting_plan(
    db: Session,
    *,
    farm_id: int,
    client_request_id: str,
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    """并发唯一键冲突回滚后，在新事务中读取已经提交的结果。"""
    return _load_idempotent_result(
        db,
        farm_id=farm_id,
        client_request_id=client_request_id,
        request_fingerprint=_fingerprint(plan),
    )


def _require_matching_template(
    template: dict[str, Any] | None,
    crop_name: str,
) -> dict[str, Any]:
    if template is None or crop_service.normalize_crop_name(
        template["name"]
    ) != crop_service.normalize_crop_name(crop_name):
        raise PlantingPlanError("crop_template_mismatch", "模板与目标作物不一致")
    return template


def _materialize_template(
    db: Session,
    *,
    farm_id: int,
    crop_name: str,
    action: str | None,
    template_data: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    if action == "use_existing":
        template_id = template_data.get("farm_template_id") or template_data.get("id")
        template = crop_service.get_crop_template(db, template_id, farm_id)
        if template is None:
            raise PlantingPlanError("crop_template_not_found", "农场模板不存在")
    elif action == "import_system":
        try:
            imported = crop_service.import_system_template(
                db,
                template_data.get("system_template_id"),
                farm_id,
            )
        except ValueError as exc:
            raise PlantingPlanError("system_template_not_found", str(exc)) from exc
        template_id = imported.template_id
        template = crop_service.get_crop_template(db, template_id, farm_id)
    elif action == "create_custom":
        stages = _validate_stages(template_data.get("stages"))
        template_name = template_data.get("name") or crop_name
        duplicate = crop_service.find_exact_duplicate(
            db,
            farm_id=farm_id,
            name=template_name,
            variety=template_data.get("variety"),
            stages=stages,
        )
        if duplicate is not None:
            template_id = duplicate.id
            template = crop_service.get_crop_template(db, template_id, farm_id)
        else:
            template = crop_service.create_crop_template(
                db,
                farm_id=farm_id,
                name=template_name,
                variety=template_data.get("variety"),
                category=template_data.get("category"),
                stages=stages,
            )
            template_id = template["id"]
    else:
        raise PlantingPlanError("invalid_template_action", "种植计划缺少模板处理方式")
    return int(template_id), _require_matching_template(template, crop_name)


def _create_cycle_and_unit(
    db: Session,
    *,
    farm_id: int,
    crop_name: str,
    template_id: int,
    plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    cycle_data = plan.get("cycle") or {}
    unit_data = plan.get("planting_unit") or {}
    try:
        cycle = cycle_service.create_crop_cycle(
            db,
            farm_id=farm_id,
            name=cycle_data.get("name") or f"{crop_name}种植计划",
            crop_template_id=template_id,
            start_date=date.fromisoformat(str(cycle_data["start_date"])),
            field_name=unit_data.get("name"),
            total_area_mu=(
                Decimal(str(cycle_data["total_area_mu"]))
                if cycle_data.get("total_area_mu") is not None
                else None
            ),
            expected_crop_name=crop_name,
        )
        unit = work_order_service.create_unit(
            db,
            farm_id=farm_id,
            cycle_id=cycle["id"],
            name=unit_data["name"],
            area_mu=unit_data.get("area_mu"),
            planted_date=date.fromisoformat(str(unit_data["planted_date"])),
            note=unit_data.get("note"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlantingPlanError(
            "planting_plan_rollback",
            f"种植计划提交失败，事务已回滚：{exc}",
        ) from exc
    return cycle, unit


def commit_planting_plan(
    db: Session,
    *,
    farm_id: int,
    client_request_id: str,
    approval_fingerprint: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """在当前事务中提交模板、茬口和种植单元，并保存幂等结果。"""
    if not client_request_id:
        raise PlantingPlanError("missing_client_request_id", "缺少客户端请求 ID")
    request_fingerprint = _fingerprint(plan)
    if request_fingerprint != approval_fingerprint:
        raise PlantingPlanError(
            "approval_stale",
            "审批后的种植计划内容已发生变化，请重新准备并确认",
        )
    replay = _load_idempotent_result(
        db,
        farm_id=farm_id,
        client_request_id=client_request_id,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay

    crop_name = str(plan.get("crop_name") or "").strip()
    if not crop_name:
        raise PlantingPlanError("missing_crop_name", "种植计划缺少目标作物")
    template_id, template = _materialize_template(
        db,
        farm_id=farm_id,
        crop_name=crop_name,
        action=plan.get("template_action"),
        template_data=plan.get("template") or {},
    )
    cycle, unit = _create_cycle_and_unit(
        db,
        farm_id=farm_id,
        crop_name=crop_name,
        template_id=template_id,
        plan=plan,
    )

    result = {
        "status": "committed",
        "idempotent_replay": False,
        "template": {"id": template_id, "name": template["name"]},
        "cycle": {"id": cycle["id"], "name": cycle["name"]},
        "planting_unit": {
            "id": unit["id"],
            "name": unit["name"],
            "area_mu": unit.get("area_mu"),
        },
    }
    execution = PlantingPlanExecution(
        farm_id=farm_id,
        client_request_id=client_request_id,
        request_fingerprint=request_fingerprint,
        approval_fingerprint=approval_fingerprint,
        status="committed",
        crop_template_id=template_id,
        crop_cycle_id=cycle["id"],
        planting_unit_id=unit["id"],
        result_json=result,
    )
    db.add(execution)
    db.flush()
    return result


__all__ = [
    "PlantingPlanError",
    "prepare_planting_plan",
    "commit_planting_plan",
    "load_committed_planting_plan",
]
