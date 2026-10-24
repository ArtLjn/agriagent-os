"""最终请求预算：所有动态内容组装后裁剪，不能以初始投影代替发送前检查。"""

from __future__ import annotations

import json
from copy import deepcopy

from agent.domains.harness.context import tokenizer

# 只移除可重新检索的背景；用户当前请求、系统契约和动作状态不能静默丢弃。
OPTIONAL_BLOCKS = (
    "<session-summary>",
    "<completed-history>",
    "<user-personalization>",
    "<system-reminder>",
)
RESULT_FIELDS = ("code", "success", "persisted", "committed", "status", "id", "total")


class ContextBudgetError(ValueError):
    """保留预算上下文，供运行时终止而非无意义地重试同一大请求。"""

    code = "context_budget_exceeded"

    def __init__(self, usage):
        self.usage = usage
        super().__init__("必需上下文超过模型预算，请缩小本次任务或输入范围")


def prepare_request(messages, tools=None, *, max_tokens=None, compact=True):
    """返回独立副本；按完整消息裁剪，超大工具结果保留协议配对和明确的缺失标记。"""
    from agent.config import settings

    reserve = max_tokens or settings.context.response_reserve_tokens
    result = deepcopy(messages)

    def usage():
        return tokenizer.compute_usage(
            result,
            tools=tools,
            response_reserve=reserve,
            safety_margin=settings.context.safety_margin_tokens,
        )

    current = usage()
    if compact and current.decision == "budget_exceeded":
        for prefix in OPTIONAL_BLOCKS:
            last_user = max(
                (i for i, m in enumerate(result) if m.get("role") == "user"), default=-1
            )
            result = [
                m
                for i, m in enumerate(result)
                if not (
                    m.get("role") == "system"
                    or (prefix == "<user-personalization>" and i < last_user)
                )
                or not isinstance(m.get("content"), str)
                or not m["content"].startswith(prefix)
            ]
            current = usage()
            if current.decision != "budget_exceeded":
                break
    if compact and current.decision == "budget_exceeded":
        # 不截半段 JSON 或丢掉否定词。原始结果仍在本轮 Trace 中，可缩小查询范围获取。
        for message in sorted(
            (m for m in result if m.get("role") == "tool"),
            key=lambda m: len(str(m.get("content", ""))),
            reverse=True,
        ):
            original = message.get("content", "")
            omitted = {
                "code": "tool_result_omitted_for_budget",
                "tool_call_id": message.get("tool_call_id"),
                "message": "结果正文过大，已省略。仅可使用保留的状态字段；其余内容请分页或缩小查询，不能猜测。",
            }
            try:
                payload = json.loads(original)
            except (TypeError, ValueError):
                payload = None
            if isinstance(payload, dict):
                omitted["original_status"] = {
                    k: payload[k]
                    for k in RESULT_FIELDS
                    if k in payload
                    and isinstance(payload[k], (str, bool, int, float, type(None)))
                    and len(str(payload[k])) <= 100
                }
            replacement = json.dumps(omitted, ensure_ascii=False)
            if tokenizer.count_tokens(replacement) < tokenizer.count_tokens(
                str(original)
            ):
                message["content"] = replacement
            current = usage()
            if current.decision != "budget_exceeded":
                break
    if current.decision == "budget_exceeded":
        raise ContextBudgetError(current)
    return result, current
