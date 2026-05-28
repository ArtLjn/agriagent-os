import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor
from app.agent.prompt_registry import get_registry
from app.agent.prompt_renderer import render_prompt
from app.api.deps import get_db, get_current_farm
from app.core.json_repair import safe_parse_json
from app.models.farm import Farm
from app.models.idempotency_key import IdempotencyKey
from app.schemas.common import PaginatedResponse
from app.schemas.crop import (
    CropTemplateCreate,
    CropTemplateParseRequest,
    CropTemplateParseResponse,
    CropTemplateResponse,
)
from app.services import crop_service

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/templates", response_model=CropTemplateResponse)
def create_template(
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建作物模板。"""
    return crop_service.create_crop_template(db, template, farm_id=farm.id)


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
    try:
        crop_service.delete_crop_template(db, template_id, farm_id=farm.id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/templates/parse", response_model=CropTemplateParseResponse)
async def parse_crop_template(
    req: CropTemplateParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """AI 解析自然语言作物描述，返回结构化作物模板数据（不入库）。

    支持幂等键去重（24 小时内相同 key 直接返回缓存结果）。
    """
    logger = logging.getLogger(__name__)

    # 幂等键检查
    if idempotency_key:
        cached = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == idempotency_key)
            .first()
        )
        if cached:
            logger.info("幂等键命中 | key=%s", idempotency_key)
            try:
                data = json.loads(cached.response)
                return CropTemplateParseResponse(**data)
            except Exception:
                logger.warning(
                    "幂等缓存解析失败，重新执行 | key=%s", idempotency_key
                )

    prompt = render_prompt(
        "crop_template_parse",
        {"description": req.description},
        registry=get_registry(),
    )
    logger.info("AI 解析作物模板 | farm=%s | input: %s", farm.id, req.description)

    reply = await invoke_advisor(prompt, farm_id=farm.id)

    # JSON 解析（提取代码块 + 修复）
    try:
        data = safe_parse_json(reply)
    except ValueError:
        logger.error("AI 返回无法解析: %s", reply[:200])
        raise HTTPException(
            status_code=422, detail=f"AI 返回格式异常: {reply[:100]}"
        )

    # Pydantic 校验
    try:
        response = CropTemplateParseResponse.model_validate(data)
    except Exception as e:
        logger.error("AI 返回数据校验失败: %s", e)
        raise HTTPException(
            status_code=422, detail=f"AI 返回数据格式不正确: {str(e)[:100]}"
        )

    # 缓存幂等键
    if idempotency_key:
        try:
            cache = IdempotencyKey(
                key=idempotency_key, response=response.model_dump_json()
            )
            db.add(cache)
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("幂等键缓存写入失败 | key=%s", idempotency_key)

    return response


__all__ = ["router"]
