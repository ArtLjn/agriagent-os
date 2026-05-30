import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent.llm import get_llm
from langchain_core.messages import HumanMessage
from app.agent.prompt_composer import get_composer
from app.api.deps import get_db, get_current_farm
from app.core.json_repair import safe_parse_json
from app.models.farm import Farm
from app.models.idempotency_key import IdempotencyKey
from app.schemas.common import PaginatedResponse
from app.schemas.cycle import (
    CropCycleCreate,
    CropCycleListResponse,
    CropCycleResponse,
    CycleParseRequest,
    CycleParseResponse,
)
from app.services import crop_service, cycle_service

router = APIRouter(prefix="/cycles", tags=["cycles"])


async def _parse_cycle_with_llm(
    llm,
    prompt: str,
    logger: logging.Logger,
) -> CycleParseResponse:
    """通过 LLM 解析茬口，优先用 structured output，失败则 fallback 到 JSON 解析。"""
    try:
        structured_llm = llm.with_structured_output(
            CycleParseResponse, method="function_calling"
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
            response = CycleParseResponse.model_validate(data)
        except Exception as e:
            logger.error("AI 返回数据校验失败: %s", e)
            raise HTTPException(
                status_code=422,
                detail="无法识别茬口信息，请描述种植计划，例如：春季种番茄、秋茬种西瓜",
            )
    return response


@router.post("", response_model=CropCycleResponse)
def create_cycle(
    cycle: CropCycleCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建茬口。"""
    try:
        return cycle_service.create_crop_cycle(db, cycle, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[CropCycleListResponse])
def list_cycles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取茬口列表（分页）。"""
    skip = (page - 1) * size
    cycles = cycle_service.get_crop_cycles(db, farm_id=farm.id, skip=skip, limit=size)
    total = cycle_service.count_crop_cycles(db, farm_id=farm.id)
    items = []
    for c in cycles:
        current = next((s for s in c.stages if s.is_current), None)
        items.append(
            CropCycleListResponse(
                id=c.id,
                name=c.name,
                crop_template_name=c.crop_template.name,
                start_date=c.start_date,
                status=c.status,
                current_stage_name=current.name if current else None,
            )
        )
    return {"items": items, "total": total}


@router.get("/{cycle_id}", response_model=CropCycleResponse)
def get_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """根据 ID 获取茬口详情。"""
    cycle = cycle_service.get_crop_cycle(db, cycle_id, farm_id=farm.id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle


@router.put("/{cycle_id}", response_model=CropCycleResponse)
def update_cycle(
    cycle_id: int,
    cycle: CropCycleCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新茬口。"""
    try:
        return cycle_service.update_crop_cycle(db, cycle_id, cycle, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cycle_id}")
def delete_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除茬口。"""
    try:
        cycle_service.delete_crop_cycle(db, cycle_id, farm_id=farm.id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{cycle_id}/advance-stage", response_model=CropCycleResponse)
def advance_stage(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """推进茬口到下一阶段。"""
    try:
        return cycle_service.advance_stage(db, cycle_id, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/parse", response_model=CycleParseResponse)
async def parse_cycle(
    req: CycleParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """AI 解析自然语言茬口描述，返回结构化种植计划（不入库）。"""
    logger = logging.getLogger(__name__)

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
                return CycleParseResponse(**data)
            except Exception:
                logger.warning("幂等缓存解析失败 | key=%s", idempotency_key)

    templates = crop_service.get_crop_templates(db, farm_id=farm.id)
    template_list = [
        {"id": t.id, "name": t.name, "variety": t.variety} for t in templates
    ]
    today = date.today().isoformat()

    prompt = get_composer().compose(
        "cycle_parse",
        {"description": req.description, "templates": template_list, "today": today},
    )
    logger.info("AI 解析茬口 | farm=%s | input: %s", farm.id, req.description)

    llm = get_llm()
    response = await _parse_cycle_with_llm(llm, prompt, logger)

    # cross-validate: crop_template_id 必须来自真实模板
    if response.crop_template_id is not None:
        found = any(t.id == response.crop_template_id for t in templates)
        if not found:
            response.crop_template_id = None

    if not response.name:
        raise HTTPException(
            status_code=422,
            detail="无法识别茬口信息，请描述种植计划，例如：春季种番茄、秋茬种西瓜",
        )

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
