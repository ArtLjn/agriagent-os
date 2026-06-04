"""Agent Runtime 消息与工具调用解析辅助。"""

import json
import logging
import re
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)


def sliding_window_compact(messages: list, keep_rounds: int = 5) -> list:
    """Sliding window 消息压缩：最近 N 轮完整保留，旧 ToolMessage 截断。

    一轮 = 从 HumanMessage 到下一个 HumanMessage 之前的所有消息。
    """
    if not messages:
        return messages

    round_starts = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            round_starts.append(i)

    if len(round_starts) <= keep_rounds:
        return messages

    compress_up_to = round_starts[-keep_rounds]

    result = list(messages)
    for i, msg in enumerate(result):
        if i >= compress_up_to:
            break
        if isinstance(msg, ToolMessage):
            content = msg.content or ""
            if len(content) > 50:
                tool_name = getattr(msg, "name", "unknown")
                result[i] = ToolMessage(
                    content=f"[已执行 {tool_name}]",
                    tool_call_id=msg.tool_call_id,
                )

    return result


def _find_last_human_message(messages: list) -> str:
    """从消息列表中找到最后一条 HumanMessage 的内容。"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def _extract_tool_calls_from_content(content: str) -> list[dict] | None:
    """从 LLM content 中解析 JSON 格式的伪工具调用，转换为 LangChain tool_calls 格式。

    兼容以下格式：
      {"name": "xxx", "parameters": {...}}
      {"action": "xxx", "args": {...}}
      {"tool": "xxx", "arguments": {...}}
      🌱 {"name": "xxx", "parameters": {...}}  （emoji 前缀）
      工具调用：{"name": "xxx", "parameters": {...}}  （文本前缀）
    """
    if not content:
        return None

    # 匹配 content 中的 JSON 对象（支持 emoji/文本前缀，支持多行）
    # 使用更宽松的匹配：先找到完整的 {...} 块，再验证内部结构
    # 前缀允许：行首、空白、emoji、任意非单词字符（覆盖中文文本前缀如"工具调用："）
    json_pattern = re.compile(
        r"(?:^|\s|\W)"  # 行首、空白或任意非单词字符（覆盖中文前缀）
        r'(\{[ \t\n\r]*"'  # 开始大括号
        r"(?:name|action|tool|function)"  # 工具名键
        r'"[ \t\n\r]*:[ \t\n\r]*"([^"]+)"'  # 工具名值
        r"[ \t\n\r]*,[ \t\n\r]*"
        r'"(?:parameters|params|args|arguments)"'  # 参数键
        r"[ \t\n\r]*:[ \t\n\r]*"  # 冒号
        r"(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})"  # 嵌套参数对象
        r"[ \t\n\r]*\})",  # 结束大括号
        re.DOTALL,
    )

    matches = list(json_pattern.finditer(content))
    if not matches:
        return None

    tool_calls: list[dict] = []
    for idx, m in enumerate(matches):
        tool_name = m.group(2)
        params_json = m.group(3)
        try:
            args = json.loads(params_json)
        except json.JSONDecodeError:
            logger.warning(
                "Content JSON 参数解析失败 | tool=%s | raw=%s",
                tool_name,
                params_json[:200],
            )
            continue
        tool_calls.append(
            {
                "id": f"call_content_{idx}_{_time.time_ns()}",
                "name": tool_name,
                "args": args,
            }
        )

    return tool_calls if tool_calls else None


def _detect_missed_tool_call(
    user_msg: str,
    llm_reply: str,
    selected_tools: list,
) -> tuple[bool, list]:
    """检测 LLM 是否应该在调用工具但返回了纯文本。

    启发式规则：
    1. 用户消息包含工具选择器匹配到的关键词
    2. LLM 回复包含"帮你"、"查询"等承诺性词汇但没有实际调用工具
    3. 有 selected_tools 被绑定但 LLM 未调用
    """
    if not selected_tools:
        return False, []

    # 承诺性词汇 = LLM 说要做某事但实际上没做
    promise_words = ["帮你", "为你", "查询", "查看", "获取", "调用", "处理"]
    has_promise = any(w in llm_reply for w in promise_words)

    # 如果 LLM 回复很短（<20字）且没有承诺词，可能是正常闲聊，不重试
    if len(llm_reply) < 20 and not has_promise:
        return False, []

    # 如果用户消息明显匹配某个工具的关键词，且 LLM 没有调用
    from app.agent.tool_selector import WRITE_PATTERNS, QUERY_TRIGGERS

    matched_tools = []
    for tool in selected_tools:
        # 检查 write patterns
        patterns = WRITE_PATTERNS.get(tool.name, [])
        for pat in patterns:
            if pat.search(user_msg):
                matched_tools.append(tool)
                break
        if tool in matched_tools:
            continue
        # 检查 query triggers
        triggers = QUERY_TRIGGERS.get(tool.name, set())
        for trigger in triggers:
            if trigger in user_msg:
                matched_tools.append(tool)
                break

    # 如果用户消息匹配了工具关键词，且 LLM 回复包含承诺词但没有调用工具
    if matched_tools and has_promise:
        return True, matched_tools

    return False, []


def _extract_tokens_used(response: AIMessage) -> int | None:
    """从 LLM 响应中提取 token 用量。"""
    usage = extract_token_usage(response)
    if usage is not None:
        return usage["total_tokens"]
    return None


def _normalize_token_usage(usage: dict, usage_source: str) -> dict | None:
    """把不同 provider 的 token 字段归一化为统一结构。"""
    try:
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        total_tokens = usage.get("total_tokens")

        if prompt_tokens is None:
            prompt_tokens = 0
        if completion_tokens is None:
            completion_tokens = 0
        if total_tokens is None:
            total_tokens = int(prompt_tokens) + int(completion_tokens)

        return {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
            "usage_source": usage_source,
        }
    except (AttributeError, TypeError, ValueError):
        return None


def extract_token_usage(response: AIMessage) -> dict | None:
    """从 LLM 响应中提取真实 token usage，缺失时返回 None。"""
    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata:
        normalized = _normalize_token_usage(usage_metadata, "usage_metadata")
        if normalized is not None:
            return normalized

    response_metadata = getattr(response, "response_metadata", None) or {}
    for key in ("token_usage", "usage"):
        usage = response_metadata.get(key)
        if usage:
            normalized = _normalize_token_usage(usage, "provider")
            if normalized is not None:
                return normalized

    return None


__all__ = [
    "_detect_missed_tool_call",
    "_extract_tokens_used",
    "_extract_tool_calls_from_content",
    "_find_last_human_message",
    "extract_token_usage",
    "sliding_window_compact",
]
