"""债务管理 API 路由。"""

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.farm.dependencies import get_current_farm
from app.models.farm import Farm
from app.schemas.cost import CostRecordCreate, CostRecordResponse, DebtListResponse
from app.services import debt_service

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("", response_model=CostRecordResponse)
def create_debt(
    record: CostRecordCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> CostRecordResponse:
    """创建一条赊账记录。"""
    return debt_service.create_debt_record(db, record, farm_id=farm.id)


@router.get("", response_model=DebtListResponse)
def list_debts(
    counterparty: str | None = Query(None, description="按债权人筛选"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DebtListResponse:
    """获取未结清赊账列表及统计。"""
    skip = (page - 1) * size
    items = debt_service.get_debt_records(
        db, farm_id=farm.id, counterparty=counterparty, skip=skip, limit=size
    )
    total = debt_service.count_debt_records(
        db, farm_id=farm.id, counterparty=counterparty
    )
    summary = debt_service.get_debt_summary(db, farm_id=farm.id)
    return DebtListResponse(items=items, total=total, summary=summary)


@router.post("/settle", response_model=CostRecordResponse)
def settle_debt(
    payload: dict,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> CostRecordResponse:
    """结清赊账。

    Request body:
        counterparty: 债权人名称（必填）
        amount: 还款金额（可选，不传则全额）
        note: 兼容旧 payload 的备注（可选），当前不创建还款记录且不落库
    """
    counterparty = payload.get("counterparty")
    if not counterparty:
        raise HTTPException(status_code=400, detail="counterparty 必填")

    amount = payload.get("amount")
    if amount is not None:
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=400, detail="amount 必须是有效数字"
            ) from exc
        if not amount.is_finite():
            raise HTTPException(status_code=400, detail="amount 必须是有效数字")
        if amount <= 0:
            raise HTTPException(status_code=400, detail="结算金额必须大于 0")

    try:
        return debt_service.settle_debt(
            db,
            farm_id=farm.id,
            counterparty=counterparty,
            amount=amount,
            note=payload.get("note"),
        )
    except debt_service.InvalidSettlementAmountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


__all__ = ["router"]
