from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.cost import CostParseRequest, CostParseResponse, CostRecordCreate, CostRecordResponse, CycleProfit, YearlySummary
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


@router.post("/parse", response_model=CostParseResponse)
async def parse_cost_record(
    req: CostParseRequest,
    farm: Farm = Depends(get_current_farm),
):
    """AI 解析自然语言记账描述，返回结构化记录。"""
    import json
    import logging

    from app.agents.advisor import invoke_advisor

    logger = logging.getLogger(__name__)
    prompt = (
        f'请将以下记账描述解析为 JSON 格式，包含字段：record_type（cost 或 income）、'
        f'category（简短类别名，如"种子"、"化肥"、"销售收入"）、'
        f'amount（数字字符串）、record_date（YYYY-MM-DD 格式，默认今天）、'
        f'note（可选备注）。\n'
        f'只返回 JSON，不要其他文字。\n'
        f'描述：{req.description}'
    )
    logger.info("AI 解析记账 | farm=%s | input: %s", farm.id, req.description)
    reply = await invoke_advisor(prompt, farm_id=farm.id)

    # 提取 JSON
    try:
        text = reply.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error("AI 返回无法解析: %s", reply[:200])
        raise ValueError(f"AI 返回格式异常，无法解析: {reply[:100]}")

    # 字段校验
    record_type = data.get("record_type", "cost")
    if record_type not in ("cost", "income"):
        record_type = "cost"
    category = str(data.get("category", "其他"))[:50]
    amount = str(data.get("amount", "0"))
    record_date = str(data.get("record_date", ""))
    note = data.get("note")

    return CostParseResponse(
        record_type=record_type,
        category=category,
        amount=amount,
        record_date=record_date,
        note=note,
    )
