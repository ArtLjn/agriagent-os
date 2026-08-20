"""历史压缩器：超过 token 阈值时把最旧对话总结成 [CONVERSATION_SUMMARY]。

策略（参考 _example/core/summarizer.py）：
- 保留最近 K 条原文
- 更早的 N 条交给 LLM 总结成 1 条
- 替换 memory 中的 short_term（不写 long_term）

触发：
- soft（>=70%）：异步跑，不阻塞当前 turn
- hard（>=85%）：同步跑，跑完再继续 react loop
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from agent.core import memory
from agent.infra.llm import chat

logger = logging.getLogger(__name__)

KEEP_RECENT = 6
MIN_HISTORY_TO_SUMMARIZE = 8

SUMMARY_PROMPT = """把以下多轮对话总结成 200 字以内的关键信息，便于后续 Agent 参考。
要点：
1. 用户的意图、偏好、已知信息
2. 已经执行过哪些 skill（工具调用），结果如何
3. 待办、未解决的问题

只输出总结正文，不要任何前缀和解释。

对话：
__DIALOG__
"""


def maybe_summarize(
    conversation_id: str,
    force: bool = False,
) -> str | None:
    """对 conversation_id 的历史进行总结。

    force=True 时强制总结（hard 阈值触发）；
    force=False 时只在历史足够长时才总结（soft 阈值触发）。

    返回 summary 字符串（失败返回 None）。
    """
    history = memory.load_messages(conversation_id)
    if len(history) < MIN_HISTORY_TO_SUMMARIZE:
        return None

    if not force and len(history) < KEEP_RECENT + MIN_HISTORY_TO_SUMMARIZE:
        return None

    old = history[:-KEEP_RECENT]
    recent = history[-KEEP_RECENT:]

    dialog = json.dumps(old, ensure_ascii=False, indent=2)
    prompt = SUMMARY_PROMPT.replace("__DIALOG__", dialog)

    logger.info(
        "[summarizer] 触发总结 conv=%s old=%d recent=%d force=%s",
        conversation_id, len(old), len(recent), force,
    )

    try:
        summary = chat([
            {"role": "system", "content": "你是对话总结助手。"},
            {"role": "user", "content": prompt},
        ])
        # chat() 返回 dict
        summary = (summary.get("content") or "").strip() if isinstance(summary, dict) else str(summary).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[summarizer] 总结失败 conv=%s err=%s", conversation_id, exc)
        return None

    if not summary:
        return None

    # 摘要是 Session state，不再伪装成 assistant 消息；否则消息规范化会
    # 因为缺少对应 user 消息而把摘要丢掉。legacy fallback 也沿用同一语义。
    memory.save_legacy_summary(conversation_id, summary)
    memory.save_messages(conversation_id, recent)
    logger.info(
        "[summarizer] ✓ 已压缩 conv=%s history_len=%d → %d, summary_len=%d",
        conversation_id, len(history), len(memory.load_messages(conversation_id)), len(summary),
    )
    return summary


async def maybe_summarize_async(
    conversation_id: str,
    force: bool = False,
) -> str | None:
    """异步包装：把同步 chat 调用放到线程池，避免阻塞 event loop。"""
    return await asyncio.to_thread(maybe_summarize, conversation_id, force)


def build_summary_message(summary: str) -> dict[str, Any]:
    """构造 summary 消息（供 context.build_initial_messages 使用）。"""
    return {"role": "assistant", "content": f"[CONVERSATION_SUMMARY] {summary}"}
