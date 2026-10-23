"""备忘录 MCP 工具，协议层只做参数适配与权限校验。"""

from pydantic import ValidationError

from business.db import session_scope
from business.mcp_app import mcp
from business.services import memo_service as service
from business.tools._headers import require_farm_operation_permission


@mcp.tool
def manage_memos(
    operation: str,
    memo_id: int | None = None,
    title: str | None = None,
    content: str | None = None,
    pinned: bool | None = None,
    archived: bool | None = None,
    client_request_id: str | None = None,
    keyword: str = "",
    limit: int = service.DEFAULT_RESULTS,
    skip: int = 0,
) -> dict:
    """创建、搜索、编辑、置顶或归档备忘录；不创建日程或定时通知。

    聚合工具在同一处保留操作分派和错误映射，业务规则由 service 统一校验。
    """
    user = require_farm_operation_permission(operation, tool_name="manage_memos")
    identity = {"farm_id": user["farm_id"], "user_id": user["user_id"]}
    try:
        with session_scope() as db:
            if operation == "query":
                return service.list_memos(
                    db,
                    **identity,
                    keyword=keyword,
                    archived=archived or False,
                    limit=limit,
                    skip=skip,
                )
            if operation == "create":
                request = service.MemoCreate(
                    title=title,
                    content=content,
                    pinned=pinned or False,
                    client_request_id=client_request_id,
                )
                return service.create_memo(db, **identity, request=request)
            if operation in {"update", "archive"}:
                if memo_id is None or memo_id <= 0:
                    raise service.MemoError(
                        "validation_error", "请先查询需要操作的备忘录", field="memo_id"
                    )
                changes = {
                    key: value
                    for key, value in {
                        "title": title,
                        "content": content,
                        "pinned": pinned,
                    }.items()
                    if value is not None
                }
                if operation == "archive":
                    if archived is None:
                        raise service.MemoError(
                            "validation_error",
                            "请明确归档或恢复备忘录",
                            field="archived",
                        )
                    changes = {"archived": archived}
                return service.update_memo(
                    db,
                    **identity,
                    memo_id=memo_id,
                    request=service.MemoUpdate(**changes),
                )
            raise service.MemoError(
                "validation_error", "不支持的备忘录操作", operation=operation
            )
    except service.MemoError as exc:
        return {
            "error": exc.code,
            "code": exc.code,
            "message": str(exc),
            "meta": exc.meta,
        }
    except ValidationError:
        return {
            "error": "validation_error",
            "code": "validation_error",
            "message": "备忘录参数无效，请检查标题、内容和请求标识",
            "meta": {"operation": operation},
        }
