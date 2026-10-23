"""管理员查看运行中的系统提示词，源文件通过版本控制维护。"""

from fastapi import Depends, Header

from agent import prompts
from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from shared.roles import Permission


def admin_identity(authorization: str | None = Header(default=None)):
    """提示词内容和重新加载仅向管理调试权限开放。"""
    return require_identity_permission(
        parse_identity(authorization), Permission.ADMIN_DEBUG
    )


@api_router.get("/admin/prompts", dependencies=[Depends(admin_identity)])
def list_admin_prompts():
    """返回运行时缓存中的模板，避免将磁盘内容误报为当前生效内容。"""
    items = prompts.inspect_prompts()
    return {"items": items, "total": len(items)}


@api_router.post("/admin/prompts/reload", dependencies=[Depends(admin_identity)])
def reload_admin_prompts():
    """重新读取当前进程的模板；不承诺更新已启动对话或其他工作进程。"""
    prompts.reload()
    prompts.inspect_prompts()
    return {
        "status": "ok",
        "message": "当前 Agent 进程已重新加载模板，新建上下文时生效",
    }
