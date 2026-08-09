"""赊账记录与结算路由。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import debt_service

router = APIRouter(prefix="/debts", tags=["debts"])


class CreateDebtRequest(StrictRequest):
    counterparty: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    record_date: date
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=500)
    cycle_id: int | None = Field(default=None, gt=0)
    record_type: str = Field(default="cost", pattern="^(cost|income)$")
    category: str = Field(default="赊账", min_length=1, max_length=50)


class SettleDebtRequest(StrictRequest):
    counterparty: str = Field(min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


@router.get("")
def list_debts(
    counterparty: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = debt_service.get_debt_records(
        db,
        farm_id=user["farm_id"],
        counterparty=counterparty,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = debt_service.count_debt_records(
        db, farm_id=user["farm_id"], counterparty=counterparty
    )
    summary = debt_service.get_debt_summary(db, farm_id=user["farm_id"])
    return {"items": items, "total": total, "summary": summary}


@router.get("/summary")
def debt_summary(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": debt_service.get_debt_summary(db, farm_id=user["farm_id"])}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_debt(
    request: CreateDebtRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return debt_service.create_debt_record(
        db,
        farm_id=user["farm_id"],
        record_subtype="赊账",
        **request.model_dump(),
    )


@router.post("/settle")
def settle_debt(
    request: SettleDebtRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return debt_service.settle_debt(
            db, farm_id=user["farm_id"], **request.model_dump()
        )
    except debt_service.InvalidSettlementAmountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
