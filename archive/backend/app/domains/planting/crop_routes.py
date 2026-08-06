import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session

from langchain_core.messages import HumanMessage
from app.shared.database import get_db
from app.domains.farm.dependencies import get_current_farm
from app.domains.users.dependencies import require_admin
from app.shared.json_repair import safe_parse_json
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.shared.schemas import PaginatedResponse
from app.domains.planting.crop_schemas import (
    CropTemplateCreate,
    CropTemplateImportResponse,
    CropTemplateParseRequest,
    CropTemplateParseResponse,
    CropTemplateResponse,
)
from app.domains.planting.smart_fill_schemas import SmartFillParseRequest
from app.domains.planting import crop_service
from app.application.smart_fill import parse_smart_fill

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post(
    "/templates",
    response_model=CropTemplateResponse,
    status_code=201,
)
def create_template(
    template: CropTemplateCreate,
    response: Response,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建作物模板。"""
    duplicate = crop_service.find_exact_duplicate(
        db,
        farm_id=farm.id,
        name=template.name,
        variety=template.variety,
        stages=template.stages,
    )
    if duplicate is not None:
        response.status_code = 200
        duplicate.already_exists = True
        return duplicate

    created = crop_service.create_crop_template(db, template, farm_id=farm.id)
    created.already_exists = False
    return created


@router.get("/templates", response_model=PaginatedResponse[CropTemplateResponse])
def list_templates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取作物模板列表（分页）。"""
    skip = (page - 1) * size
    items = crop_service.get_crop_templates(db, farm_id=farm.id, skip=skip, limit=size)
    total = crop_service.count_crop_templates(db, farm_id=farm.id)
    return {"items": items, "total": total}


@router.get("/templates/system", response_model=list[CropTemplateResponse])
def list_system_templates(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取系统作物模板列表。"""
    del farm
    return crop_service.list_system_templates(db, category=category)


@router.post(
    "/templates/system/{template_id}/import",
    response_model=CropTemplateImportResponse,
    status_code=201,
)
def import_system_template(
    template_id: int,
    response: Response,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """导入系统作物模板到当前农场。"""
    try:
        result = crop_service.import_system_template(
            db,
            system_template_id=template_id,
            farm_id=farm.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if result.already_exists:
        response.status_code = 200
    return {"id": result.template_id, "already_exists": result.already_exists}


@router.post(
    "/templates/system",
    response_model=CropTemplateResponse,
    status_code=201,
)
def create_system_template_endpoint(
    template: CropTemplateCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建系统作物模板（farm_id 为空）。"""
    duplicate = crop_service.find_system_template_match(
        db, name=template.name, variety=template.variety
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="同名同品种的系统模板已存在")
    return crop_service.create_system_crop_template(db, template)


@router.put("/templates/system/{template_id}", response_model=CropTemplateResponse)
def update_system_template_endpoint(
    template_id: int,
    template: CropTemplateCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新系统作物模板（含 stages 全量替换）。"""
    try:
        return crop_service.update_system_crop_template(db, template_id, template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/templates/system/{template_id}")
def delete_system_template_endpoint(
    template_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除系统作物模板；已被农场导入时返回 409。"""
    try:
        crop_service.delete_system_crop_template(db, template_id)
    except ValueError as e:
        msg = str(e)
        if "已被" in msg and "导入" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
    return {"message": "删除成功"}


@router.get("/templates/{template_id}", response_model=CropTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """根据 ID 获取作物模板详情。"""
    template = crop_service.get_crop_template(db, template_id, farm_id=farm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=CropTemplateResponse)
def update_template(
    template_id: int,
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新作物模板。"""
    if crop_service.get_system_template(db, template_id) is not None:
        raise HTTPException(status_code=403, detail="系统模板不允许修改")
    try:
        return crop_service.update_crop_template(
            db, template_id, template, farm_id=farm.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除作物模板。"""
    if crop_service.get_system_template(db, template_id) is not None:
        raise HTTPException(status_code=403, detail="系统模板不允许删除")
    try:
        crop_service.delete_crop_template(db, template_id, farm_id=farm.id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


async def _parse_crop_with_llm(
    llm,
    prompt: str,
    logger: logging.Logger,
) -> CropTemplateParseResponse:
    """通过 LLM 解析作物模板，优先用 structured output，失败则 fallback 到 JSON 解析。"""
    try:
        structured_llm = llm.with_structured_output(
            CropTemplateParseResponse, method="function_calling"
        )
        response = await structured_llm.ainvoke([HumanMessage(content=prompt)])
    except Exception as structured_err:
        logger.warning(
            "with_structured_output 失败，回退到 JSON 解析: %s",
            structured_err,
            exc_info=True,
        )
        try:
            result = await llm.ainvoke([HumanMessage(content=prompt)])
            reply = result.content
        except Exception as e:
            logger.error("AI 调用失败: %s", e)
            raise HTTPException(status_code=503, detail="AI 服务暂时不可用，请稍后重试")

        try:
            data = safe_parse_json(reply)
        except ValueError:
            logger.error("AI 返回无法解析: %s", reply[:200])
            raise HTTPException(
                status_code=422, detail=f"AI 返回格式异常: {reply[:100]}"
            )

        try:
            response = CropTemplateParseResponse.model_validate(data)
        except Exception as e:
            logger.error("AI 返回数据校验失败: %s", e)
            raise HTTPException(
                status_code=422,
                detail="无法识别作物信息，请描述作物名称，例如：我要种8424西瓜、种番茄",
            )
    return response


@router.post("/templates/parse", response_model=CropTemplateParseResponse)
async def parse_crop_template(
    req: CropTemplateParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """兼容入口：转调统一智能填写，保持旧响应格式。"""
    response = await parse_smart_fill(
        SmartFillParseRequest(scene="crop.template", text=req.description),
        farm,
        db,
        idempotency_key,
    )
    return CropTemplateParseResponse.model_validate(response.draft)


__all__ = ["router"]
