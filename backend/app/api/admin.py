"""Admin API — 运维接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.dependencies import require_admin
from app.infra.repository_runtime import (
    get_guardrails_log_repository,
    run_maybe_awaitable,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/guardrails-logs")
def list_guardrails_logs(
    trigger_type: str | None = Query(None, description="按类型过滤"),
    farm_id: int | None = Query(None, ge=1, description="按农场过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询 Guardrails 拦截日志（支持分页和类型过滤）。"""
    page_data = run_maybe_awaitable(
        get_guardrails_log_repository(db).list_admin_page(
            trigger_type=trigger_type,
            farm_id=farm_id,
            page=page,
            size=size,
        )
    )
    return {"items": page_data.items, "total": page_data.total}
