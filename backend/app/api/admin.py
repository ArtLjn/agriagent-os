"""Admin API — 运维接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.guardrails_log import GuardrailsLog

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/guardrails-logs")
def list_guardrails_logs(
    trigger_type: str | None = Query(None, description="按类型过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询 Guardrails 拦截日志（支持分页和类型过滤）。"""
    query = db.query(GuardrailsLog)
    if trigger_type:
        query = query.filter(GuardrailsLog.trigger_type == trigger_type)
    total = query.count()
    items = query.order_by(GuardrailsLog.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": items, "total": total}
