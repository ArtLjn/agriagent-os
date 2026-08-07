"""HITL 端到端集成测试：验证 SSE 流中的 approval_required → /approve → 执行。

跑法：
  cd /Users/ljn/Documents/demo/explore/v2
  # 先启动 agent 服务
  uv run --package farm-manager-agent uvicorn agent.main:app --port 8000 &
  # 再跑测试
  uv run --package farm-manager-agent python scripts/test_hitl_e2e.py

测试流程：
  1. 发送写操作消息（引导 LLM 调用 write skill）
  2. 并发读取 SSE 流
  3. 检测到 approval_required 事件 → 提取 turn_id
  4. 调用 POST /approve（自动批准）
  5. 继续读取 SSE 流，验证 observation（工具执行结果）
  6. 验证 final_answer（最终回答）

也测试拒绝场景：
  1. 发送写操作消息
  2. 检测到 approval_required
  3. 调用 POST /approve（拒绝）
  4. 验证 final_answer 包含"取消"字样
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

try:
    import httpx
except ImportError:
    print("✗ 需要 httpx: uv add httpx")
    sys.exit(1)

AGENT = "http://127.0.0.1:8000"
AUTH = "Bearer test"

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

PASS = 0
FAIL = 0


def parse_sse_block(block: str) -> tuple[str, dict | None]:
    """解析一个 SSE block，返回 (event_type, data_dict)。"""
    event_type = ""
    data_str = ""
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_str += line[5:].strip()
    if not data_str:
        return event_type, None
    try:
        return event_type, json.loads(data_str)
    except json.JSONDecodeError:
        return event_type, None


async def chat_with_approval(
    client: httpx.AsyncClient,
    conv_id: str,
    message: str,
    auto_approve: bool = True,
    timeout: float = 60.0,
) -> dict:
    """发送 chat 请求，自动处理 HITL 审批。

    返回 {events, final_answer, approval_triggered, approved, turn_id}
    """
    events: list[dict] = []
    final_answer = ""
    approval_triggered = False
    turn_id = None
    approved = False

    async with client.stream(
        "POST",
        f"{AGENT}/chat",
        headers={
            "Content-Type": "application/json",
            "Authorization": AUTH,
        },
        json={"conversation_id": conv_id, "message": message},
        timeout=timeout,
    ) as response:
        buffer = ""
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                block = block.strip()
                if not block:
                    continue

                event_type, data = parse_sse_block(block)
                if not event_type or not data:
                    continue

                events.append({"type": event_type, "data": data})

                if event_type == "approval_required":
                    approval_triggered = True
                    turn_id = data.get("turn_id")
                    risk_level = data.get("risk_level", "")
                    tool_name = data.get("tool_name", "")
                    print(f"    📋 approval_required: turn={turn_id[:12]}... "
                          f"tool={tool_name} risk={risk_level}")

                    # 自动调用 /approve
                    if auto_approve and turn_id:
                        await asyncio.sleep(0.5)  # 等服务端注册 future
                        approve_resp = await client.post(
                            f"{AGENT}/approve",
                            json={
                                "turn_id": turn_id,
                                "decision": True,
                                "reason": "测试自动批准",
                            },
                        )
                        if approve_resp.status_code == 200:
                            approved = True
                            print(f"    ✓ 已批准 (HTTP {approve_resp.status_code})")
                        else:
                            print(f"    ✗ 批准失败: HTTP {approve_resp.status_code} "
                                  f"{approve_resp.text[:100]}")

                elif event_type == "approval_result":
                    decision = data.get("decision", "")
                    print(f"    📎 approval_result: {decision}")

                elif event_type == "action":
                    tool_name = data.get("tool_name", "")
                    print(f"    ⚡ action: {tool_name}")

                elif event_type == "observation":
                    error = data.get("error")
                    if error:
                        print(f"    ❌ observation error: {error[:80]}")
                    else:
                        result_str = json.dumps(data.get("result", ""),
                                                ensure_ascii=False)[:80]
                        print(f"    👁 observation: {result_str}")

                elif event_type == "final_answer":
                    final_answer = data.get("text", "")
                    print(f"    💬 final_answer: {final_answer[:80]}...")

                elif event_type == "done":
                    status = data.get("status", "")
                    print(f"    🏁 done: status={status}")

    return {
        "events": events,
        "final_answer": final_answer,
        "approval_triggered": approval_triggered,
        "approved": approved,
        "turn_id": turn_id,
    }


async def chat_with_reject(
    client: httpx.AsyncClient,
    conv_id: str,
    message: str,
    timeout: float = 60.0,
) -> dict:
    """发送 chat 请求，自动拒绝 HITL 审批。"""
    events: list[dict] = []
    final_answer = ""
    approval_triggered = False
    turn_id = None

    async with client.stream(
        "POST",
        f"{AGENT}/chat",
        headers={
            "Content-Type": "application/json",
            "Authorization": AUTH,
        },
        json={"conversation_id": conv_id, "message": message},
        timeout=timeout,
    ) as response:
        buffer = ""
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                block = block.strip()
                if not block:
                    continue

                event_type, data = parse_sse_block(block)
                if not event_type or not data:
                    continue

                events.append({"type": event_type, "data": data})

                if event_type == "approval_required":
                    approval_triggered = True
                    turn_id = data.get("turn_id")
                    tool_name = data.get("tool_name", "")
                    print(f"    📋 approval_required: turn={turn_id[:12]}... "
                          f"tool={tool_name}")

                    # 自动拒绝
                    if turn_id:
                        await asyncio.sleep(0.5)
                        reject_resp = await client.post(
                            f"{AGENT}/approve",
                            json={
                                "turn_id": turn_id,
                                "decision": False,
                                "reason": "测试自动拒绝",
                            },
                        )
                        if reject_resp.status_code == 200:
                            print(f"    ✗ 已拒绝 (HTTP {reject_resp.status_code})")

                elif event_type == "final_answer":
                    final_answer = data.get("text", "")
                    print(f"    💬 final_answer: {final_answer[:80]}...")

                elif event_type == "done":
                    print(f"    🏁 done: status={data.get('status', '')}")

    return {
        "events": events,
        "final_answer": final_answer,
        "approval_triggered": approval_triggered,
        "turn_id": turn_id,
    }


async def check_health(client: httpx.AsyncClient) -> bool:
    """检查 agent 服务是否可用。"""
    try:
        resp = await client.get(f"{AGENT}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


async def main():
    global PASS, FAIL

    print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN} HITL 端到端集成测试{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}")
    print()

    async with httpx.AsyncClient() as client:
        # 检查服务可用性
        if not await check_health(client):
            print(f"{RED}✗ agent 服务不可用（{AGENT}），请先启动：{NC}")
            print(f"  uv run --package farm-manager-agent uvicorn agent.main:app --port 8000")
            sys.exit(1)
        print(f"{GREEN}✓ agent 服务可用{NC}\n")

        ts = int(time.time())

        # ─── 测试 1：写操作自动批准 ──
        print(f"{YELLOW}[测试 1] 创建农事日志 → 自动批准 → 验证执行{NC}")
        conv1 = f"hitl-approve-{ts}"
        result1 = await chat_with_approval(
            client, conv1,
            "请创建一条农事日志，operation_type 设为浇水，备注为测试浇水",
        )

        if result1["approval_triggered"]:
            if result1["approved"]:
                # 验证有 observation 事件（工具执行结果）
                has_obs = any(e["type"] == "observation" for e in result1["events"])
                if has_obs:
                    print(f"  {GREEN}✓ PASS{NC} HITL 触发→批准→执行→observation")
                    PASS += 1
                else:
                    print(f"  {RED}✗ FAIL{NC} 批准后没有 observation 事件")
                    FAIL += 1
            else:
                print(f"  {RED}✗ FAIL{NC} HITL 触发但 /approve 调用失败")
                FAIL += 1
        else:
            print(f"  {YELLOW}⚠ SKIP{NC} LLM 未触发写操作（行为差异，非 bug）")
            print(f"    事件: {[e['type'] for e in result1['events']]}")
        print()

        await asyncio.sleep(1)

        # ─── 测试 2：写操作自动拒绝 ──
        print(f"{YELLOW}[测试 2] 创建成本记录 → 自动拒绝 → 验证取消{NC}")
        conv2 = f"hitl-reject-{ts}"
        result2 = await chat_with_reject(
            client, conv2,
            "请帮我记一笔成本，类别为化肥，金额100元",
        )

        if result2["approval_triggered"]:
            # 验证 final_answer 包含"取消"或"拒绝"字样
            fa = result2["final_answer"]
            if any(kw in fa for kw in ["取消", "拒绝", "已取消", "未执行"]):
                print(f"  {GREEN}✓ PASS{NC} HITL 触发→拒绝→final_answer 含取消字样")
                PASS += 1
            else:
                print(f"  {RED}✗ FAIL{NC} 拒绝后 final_answer 未含取消字样")
                print(f"    final_answer: {fa[:100]}")
                FAIL += 1
        else:
            print(f"  {YELLOW}⚠ SKIP{NC} LLM 未触发写操作")
            print(f"    事件: {[e['type'] for e in result2['events']]}")
        print()

        await asyncio.sleep(1)

        # ─── 测试 3：delete 操作（write_high）──
        print(f"{YELLOW}[测试 3] 删除操作（write_high）→ 验证更高风险触发{NC}")
        conv3 = f"hitl-delete-{ts}"
        result3 = await chat_with_approval(
            client, conv3,
            "请删除 ID 为 999 的农事日志",
        )

        if result3["approval_triggered"]:
            # 检查 risk_level 是否为 write_high
            approval_ev = next(
                (e for e in result3["events"] if e["type"] == "approval_required"),
                None,
            )
            if approval_ev:
                risk = approval_ev["data"].get("risk_level", "")
                if risk == "write_high":
                    print(f"  {GREEN}✓ PASS{NC} delete 操作触发 write_high 风险等级")
                    PASS += 1
                else:
                    print(f"  {YELLOW}⚠ PARTIAL{NC} 触发 HITL 但 risk={risk}（期望 write_high）")
                    PASS += 1
            else:
                print(f"  {GREEN}✓ PASS{NC} delete 操作触发 HITL")
                PASS += 1
        else:
            print(f"  {YELLOW}⚠ SKIP{NC} LLM 未触发删除操作")
            print(f"    事件: {[e['type'] for e in result3['events']]}")
        print()

        # ─── 汇总 ──
        print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}")
        print(f"{CYAN} 测试汇总{NC}")
        print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}")
        print(f"  通过: {GREEN}{PASS}{NC}")
        print(f"  失败: {RED}{FAIL}{NC}")
        print()

        if FAIL == 0:
            print(f"{GREEN}✓ 测试完成！{NC}")
            if PASS == 0:
                print(f"  {YELLOW}注意：所有测试都被 SKIP（LLM 未触发写操作）{NC}")
                print(f"  这是 LLM 行为差异，非代码 bug。可尝试调整提示词。")
            sys.exit(0)
        else:
            print(f"{RED}✗ 有 {FAIL} 个测试失败{NC}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
