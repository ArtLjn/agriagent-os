"""Agent HTTP API 客户端。"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AgentClient:
    """Agent HTTP API 客户端。"""

    def __init__(self, base_url: str = "http://localhost:8000", token: str = ""):
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def send_message(
        self, message: str, session_id: str | None = None, cycle_id: int | None = None
    ) -> dict[str, Any]:
        """
        发送单条消息到 Agent，返回完整响应。
        返回：{"reply": str, "pending_action": dict | None}
        """
        url = f"{self._base_url}/agent/chat"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        payload = {
            "message": message,
            "session_id": session_id,
            "cycle_id": cycle_id,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.info("Agent 回复: %s", data.get("reply", "")[:50])
        return data

    async def send_confirm(self, session_id: str, action_id: str) -> dict[str, Any]:
        """
        发送确认消息（用于 pending action 确认流程）。
        用户说"确认"，Agent 会执行 pending 的 write skill。
        """
        return await self.send_message("确认", session_id=session_id)

    async def send_cancel(self, session_id: str, action_id: str) -> dict[str, Any]:
        """
        发送取消消息。
        """
        return await self.send_message("取消", session_id=session_id)
