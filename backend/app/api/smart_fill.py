from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.models.farm import Farm
from app.schemas.smart_fill import (
    SmartFillParseRequest,
    SmartFillParseResponse,
    SmartFillScenarioListResponse,
)
from app.agent.application.smart_fill import list_scenarios, parse_smart_fill

router = APIRouter(prefix="/smart-fill", tags=["smart-fill"])


@router.get("/scenarios", response_model=SmartFillScenarioListResponse)
def list_smart_fill_scenarios(_farm: Farm = Depends(get_current_farm)):
    """列出统一智能填写支持的业务场景。"""
    return SmartFillScenarioListResponse(items=list_scenarios())


@router.post("/parse", response_model=SmartFillParseResponse)
async def parse_smart_fill_scene(
    req: SmartFillParseRequest,
    farm: Farm = Depends(get_current_farm),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """统一智能填写解析入口，仅返回表单草稿，不直接落库。"""
    return await parse_smart_fill(req, farm, db, idempotency_key)


__all__ = ["router"]
