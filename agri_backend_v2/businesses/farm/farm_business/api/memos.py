"""用户备忘录 REST API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from farm_business.api.deps import require_permission
from farm_business.db import get_db
from farm_business.services import memo_service as service
from shared.api_response import api_http_exception
from shared.roles import Permission

router = APIRouter(
    prefix="/memos",
    tags=["memos"],
    responses={
        503: {
            "description": "备忘录表未初始化或存储暂不可用；detail.code 为 memo_schema_not_ready 或 memo_storage_unavailable"
        }
    },
)


@router.get("")
def list_memos(
    user: Annotated[dict, Depends(require_permission(Permission.FARM_READ))],
    db: Annotated[Session, Depends(get_db)],
    keyword: str = Query(default="", max_length=200),
    archived: bool = False,
    limit: int = Query(default=service.DEFAULT_RESULTS, ge=1, le=service.MAX_RESULTS),
    skip: int = Query(default=0, ge=0),
) -> dict:
    """搜索自己的备忘录，身份不得由请求参数覆盖。"""
    try:
        return service.list_memos(
            db,
            farm_id=user["farm_id"],
            user_id=user["user_id"],
            keyword=keyword,
            archived=archived,
            limit=limit,
            skip=skip,
        )
    except SQLAlchemyError as exc:
        error = service.storage_error(exc, operation="query")
        raise api_http_exception(
            error.code, str(error), status_code=503, meta=error.meta
        ) from None


@router.post("", status_code=201)
def create_memo(
    request: service.MemoCreate,
    user: Annotated[dict, Depends(require_permission(Permission.FARM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """创建备忘录，重复请求返回既有记录。"""
    try:
        return service.create_memo(
            db, farm_id=user["farm_id"], user_id=user["user_id"], request=request
        )
    except SQLAlchemyError as exc:
        error = service.storage_error(exc, operation="create")
        raise api_http_exception(
            error.code, str(error), status_code=503, meta=error.meta
        ) from None
    except service.MemoError as exc:
        raise api_http_exception(
            exc.code, str(exc), status_code=409, meta=exc.meta
        ) from exc


@router.patch("/{memo_id}")
def update_memo(
    memo_id: int,
    request: service.MemoUpdate,
    user: Annotated[dict, Depends(require_permission(Permission.FARM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """编辑、置顶、归档或恢复自己的备忘录。"""
    try:
        return service.update_memo(
            db,
            farm_id=user["farm_id"],
            user_id=user["user_id"],
            memo_id=memo_id,
            request=request,
        )
    except SQLAlchemyError as exc:
        error = service.storage_error(exc, operation="update")
        raise api_http_exception(
            error.code, str(error), status_code=503, meta=error.meta
        ) from None
    except service.MemoError as exc:
        raise api_http_exception(
            exc.code,
            str(exc),
            status_code=404 if exc.code == "not_found" else 422,
            meta=exc.meta,
        ) from exc
