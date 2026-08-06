"""HITL 端到端测试：发起 chat → 等待 approval_required → 调用 /approve → 验证最终结果。

跑法：uv run --package farm-manager-agent python scripts/test_hitl.py
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# 允许从 v2/scripts/ 直接运行，复用 agent 的 logging 配置
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import httpx
from agent.infra.logging import setup_logging

AGENT = "http://127.0.0.1:8000"

setup_logging(app_name="scripts")
logger = logging.getLogger("test_hitl")


async def main() -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 发起 chat，异步读 SSE 流
        async with client.stream(
            "POST",
            f"{AGENT}/chat",
            json={"message": "今天给1号茬口的番茄浇水了，记一笔",
                  "conversation_id": "hitl_test_1"},
        ) as response:
            current_turn_id = None
            approval_received = False
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                logger.info("sse << %s", line)
                if line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                # 捕获 turn_id
                if "turn_id" in data:
                    current_turn_id = data["turn_id"]

                # 收到 approval_required 后立刻调 /approve
                # （注意：不能在 stream 内 await 别的 HTTP，会死锁。改为 fire-and-forget）
                if not approval_received and current_turn_id:
                    if (data.get("tool_name") == "manage_farm_logs"
                            and data.get("risk_level") == "write_confirm"):
                        approval_received = True
                        logger.info("approval_required → /approve turn_id=%s", current_turn_id)
                        # 后台 fire approve
                        asyncio.create_task(_approve(client, current_turn_id))

                # 结束条件
                if data.get("status") in ("completed", "failed"):
                    logger.info("=== turn ended: %s ===", data.get("status"))
                    break


async def _approve(client: httpx.AsyncClient, turn_id: str) -> None:
    """异步批准 HITL 请求。"""
    await asyncio.sleep(0.3)  # 让 chat stream 先收到 approval_required
    r = await client.post(
        f"{AGENT}/approve",
        json={"turn_id": turn_id, "decision": True, "reason": "同意记录浇水"},
    )
    logger.info("approve response: %s %s", r.status_code, r.text)


if __name__ == "__main__":
    asyncio.run(main())
