import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.core.json_repair import safe_parse_json
from app.agent.prompt_registry import get_registry
from app.agent.prompt_renderer import render_prompt
from app.core.date_context import get_request_date
from app.models.farm import Farm
from app.models.idempotency_key import IdempotencyKey
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
from app.services import cost_service

router = APIRouter(prefix="/costs", tags=["costs"])


@router.post("", response_model=CostRecordResponse)
def create_record(
    record: CostRecordCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建一条成本或收入记录。"""
    return cost_service.create_record(db, record, farm_id=farm.id)


@router.get("", response_model=PaginatedResponse[CostRecordResponse])
def list_records(
    cycle_id: int | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询成本记账记录列表（分页）。"""
    skip = (page - 1) * size
    items = cost_service.get_records(
        db, farm_id=farm.id, cycle_id=cycle_id, category=category, skip=skip, limit=size
    )
    total = cost_service.count_records(
        db, farm_id=farm.id, cycle_id=cycle_id, category=category
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


@router.post("/parse", response_model=CostParseResponse)
async def parse_cost_record(
    req: CostParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """AI 解析自然语言记账描述，返回结构化记录。

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
                return CostParseResponse(**data)
            except Exception:
                logger.warning("幂等缓存解析失败，重新执行 | key=%s", idempotency_key)

    current_date = get_request_date()
    prompt = render_prompt(
        "cost_parse",
        {"description": req.description},
        registry=get_registry(),
        current_date=current_date,
    )
    logger.info("AI 解析记账 | farm=%s | input: %s", farm.id, req.description)

    from app.agent.advisor import invoke_advisor

    reply = await invoke_advisor(prompt, farm_id=farm.id)

    # JSON 解析（提取代码块 + 修复）
    try:
        data = safe_parse_json(reply)
    except ValueError:
        logger.error("AI 返回无法解析: %s", reply[:200])
        raise HTTPException(status_code=422, detail=f"AI 返回格式异常: {reply[:100]}")

    # Pydantic 校验（非法值自动替换为默认值）
    result = CostParseResult.model_validate(data)

    # 构建响应
    response = CostParseResponse(
        record_type=result.record_type,
        category=result.category,
        amount=result.amount,
        record_date=result.record_date,
        note=result.note,
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
