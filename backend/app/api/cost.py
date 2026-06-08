import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.core.json_repair import safe_parse_json
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.cost import (
    CostParseRequest,
    CostParseResponse,
    CostParseResult,
    CostRecordCreate,
    CostRecordResponse,
    CycleProfit,
    YearlySummary,
)
from app.schemas.smart_fill import SmartFillParseRequest
from app.services import cost_service
from app.agent.application.smart_fill import parse_smart_fill

router = APIRouter(prefix="/costs", tags=["costs"])


@router.post("", response_model=CostRecordResponse)
def create_record(
    record: CostRecordCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建一条成本或收入记录。"""
    try:
        return cost_service.create_record(db, record, farm_id=farm.id)
    except cost_service.DuplicateSourceRecordError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("", response_model=PaginatedResponse[CostRecordResponse])
def list_records(
    cycle_id: int | None = None,
    category: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询成本记账记录列表（分页）。"""
    skip = (page - 1) * size
    items = cost_service.get_records(
        db,
        farm_id=farm.id,
        cycle_id=cycle_id,
        category=category,
        source_type=source_type,
        source_id=source_id,
        skip=skip,
        limit=size,
    )
    total = cost_service.count_records(
        db,
        farm_id=farm.id,
        cycle_id=cycle_id,
        category=category,
        source_type=source_type,
        source_id=source_id,
    )
    return {"items": items, "total": total}


@router.get("/cycles/{cycle_id}/profit", response_model=CycleProfit)
def get_cycle_profit(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取指定种植周期的利润统计。"""
    return cost_service.get_cycle_profit(db, cycle_id, farm_id=farm.id)


@router.get("/summary/{year}", response_model=YearlySummary)
def get_yearly_summary(
    year: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取指定年度的收支汇总。"""
    return cost_service.get_yearly_summary(db, year, farm_id=farm.id)


@router.delete("/{record_id}", response_model=CostRecordResponse)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """软删除一条成本记录。"""
    record = cost_service.delete_record(db, record_id, farm_id=farm.id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return record


async def _parse_cost_with_llm(
    llm,
    prompt: str,
    logger: logging.Logger,
) -> CostParseResult:
    """通过 LLM 解析记账描述，优先用 structured output，失败则 fallback 到 JSON 解析。"""
    try:
        structured_llm = llm.with_structured_output(
            CostParseResult, method="function_calling"
        )
        result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        return result
    except Exception as structured_err:
        logger.warning(
            "with_structured_output 失败，回退到 JSON 解析: %s",
            structured_err,
            exc_info=True,
        )
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            reply = response.content
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
            result = CostParseResult.model_validate(data)
        except Exception as e:
            logger.error("AI 返回数据校验失败: %s", e)
            raise HTTPException(
                status_code=422,
                detail="无法识别记账内容，请描述具体的收支信息，例如：买了化肥200块",
            )
        return result


@router.post("/parse", response_model=CostParseResponse)
async def parse_cost_record(
    req: CostParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """兼容入口：转调统一智能填写，保持旧响应格式。"""
    response = await parse_smart_fill(
        SmartFillParseRequest(scene="ledger.record", text=req.description),
        farm,
        db,
        idempotency_key,
    )
    return CostParseResponse.model_validate(response.draft)


__all__ = ["router"]
