import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from langchain_core.messages import HumanMessage
from app.api.deps import get_db, get_current_farm
from app.core.json_repair import safe_parse_json
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.cycle import (
    CropCycleCreate,
    CropCycleListResponse,
    CropCycleResponse,
    CycleParseRequest,
    CycleParseResponse,
)
from app.schemas.smart_fill import SmartFillParseRequest
from app.services import cycle_service
from app.agent.application.smart_fill import parse_smart_fill

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
    stats = cycle_service.get_cycle_unit_stats(db, [c.id for c in cycles], farm.id)
    items = []
    for c in cycles:
        current = next((s for s in c.stages if s.is_current), None)
        stat = stats.get(c.id, {})
        items.append(
            CropCycleListResponse(
                id=c.id,
                name=c.name,
                crop_template_name=c.crop_template.name,
                start_date=c.start_date,
                status=c.status,
                current_stage_name=current.name if current else None,
                total_area_mu=c.total_area_mu,
                unit_area_mu=stat.get("unit_area_mu"),
                unit_count=stat.get("unit_count", 0),
                field_name=c.field_name,
                season=c.season,
            )
        )
    return {"items": items, "total": total}


def _build_cycle_response(db: Session, cycle, farm_id: int) -> CropCycleResponse:
    """组装带批次聚合字段的详情响应。"""
    current = next((s for s in cycle.stages if s.is_current), None)
    stats = cycle_service.get_cycle_unit_stats(db, [cycle.id], farm_id).get(
        cycle.id, {}
    )
    return CropCycleResponse(
        id=cycle.id,
        name=cycle.name,
        crop_template_id=cycle.crop_template_id,
        start_date=cycle.start_date,
        field_name=cycle.field_name,
        total_area_mu=cycle.total_area_mu,
        season=cycle.season,
        batch_note=cycle.batch_note,
        status=cycle.status,
        stages=cycle.stages,
        unit_count=stats.get("unit_count", 0),
        unit_area_mu=stats.get("unit_area_mu"),
        current_stage_name=current.name if current else None,
    )


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
    return _build_cycle_response(db, cycle, farm.id)


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
    """兼容入口：转调统一智能填写，保持旧响应格式。"""
    response = await parse_smart_fill(
        SmartFillParseRequest(scene="crop.cycle", text=req.description),
        farm,
        db,
        idempotency_key,
    )
    return CycleParseResponse.model_validate(response.draft)


__all__ = ["router"]
