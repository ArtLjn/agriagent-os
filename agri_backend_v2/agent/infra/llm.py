"""LLM client wrapper.

Loads providers.json (OpenAI-compatible format) and exposes:
  - chat(messages, tools) -> {content, tool_calls}
  - chat_stream(messages, tools) -> AsyncGenerator yielding tokens

Uses openai SDK. The 'local' provider points to a self-hosted endpoint.
Model is configurable via env; defaults to qwen3.6-flash.

重试策略：
  - chat()（同步）：遇到网络错误重试最多 MAX_RETRIES 次
  - chat_stream()（流式）：只在「还没 yield 任何内容」时重试；
    已经开始流式输出后失败不重试（重试会导致内容重复，前端无法处理）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI, OpenAI

from agent.infra.error_policy import classify_exception, error_payload

logger = logging.getLogger(__name__)

_PROVIDERS_FILE = Path(__file__).resolve().parent.parent.parent / "providers.json"

# 网络重试配置
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1.0


def _retry_delay(attempt: int) -> float:
    """计算带抖动的异步重试延迟，避免多个 Turn 同步重试。"""
    return RETRY_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.25)


def _load_provider() -> tuple[str, str, str]:
    if not _PROVIDERS_FILE.exists():
        raise FileNotFoundError(f"providers.json missing: {_PROVIDERS_FILE}")
    config = json.loads(_PROVIDERS_FILE.read_text(encoding="utf-8"))
    default_name = config.get("default_provider")
    for p in config.get("providers", []):
        if p.get("name") != default_name or not p.get("enabled"):
            continue
        base_url = p["base_url"]
        api_key = p["api_keys"][0]
        models = [m for m in p.get("models", []) if m.get("enabled")]
        if not models:
            continue
        models.sort(key=lambda m: m.get("priority", 99))
        model = models[0]["id"]
        return base_url, api_key, model
    raise RuntimeError(f"no enabled provider named {default_name}")


_BASE_URL, _API_KEY, _MODEL = _load_provider()

BASE_URL = os.environ.get("LLM_BASE_URL", _BASE_URL)
API_KEY = os.environ.get("LLM_API_KEY", _API_KEY)
MODEL = os.environ.get("LLM_MODEL", _MODEL)

_sync_client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=60.0)
_async_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=60.0)


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否值得重试（网络/服务端临时问题）。"""
    return classify_exception(exc).retryable


def _stream_error_message(exc: Exception, *, stream_started: bool = False) -> str:
    """将 Provider 故障转换为可直接展示给用户的短提示。"""
    classified = classify_exception(exc)
    if classified.retryable:
        status_code = getattr(exc, "status_code", None)
        suffix = f"（HTTP {status_code}）" if isinstance(status_code, int) else ""
        if stream_started:
            return f"网络中断{suffix}，模型输出已停止，请重新发送消息。"
        return f"模型服务暂时不可用{suffix}，已自动重试，请稍后重新发送消息。"
    return str(exc)


def _required_tool_args(
    tool_name: str, tools: list[dict[str, Any]] | None
) -> list[str]:
    """返回工具 schema 声明的必填参数，用于识别流式响应丢参。"""
    for tool in tools or []:
        function = tool.get("function") or {}
        if function.get("name") != tool_name:
            continue
        schema = function.get("parameters") or {}
        required = schema.get("required") or []
        return required if isinstance(required, list) else []
    return []


async def _repair_empty_stream_tool_calls(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_calls: list[dict[str, Any]],
    temperature: float,
) -> list[dict[str, Any]]:
    """用非流式响应修复兼容网关丢失的工具参数增量。"""
    if not any(
        not call.get("arguments") and _required_tool_args(call.get("name", ""), tools)
        for call in tool_calls
    ):
        return tool_calls

    logger.warning(
        "stream tool arguments empty; retrying once with non-stream response"
    )
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = await _async_client.chat.completions.create(**kwargs)
    message = response.choices[0].message
    repaired: list[dict[str, Any]] = []
    for call in message.tool_calls or []:
        args_raw = call.function.arguments or "{}"
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            logger.warning("malformed repaired tool args: %s", args_raw)
            args = {"_raw": args_raw}
        repaired.append({"id": call.id, "name": call.function.name, "arguments": args})
    return repaired or tool_calls


def _log_cache_metrics(usage: Any) -> None:
    """解析 LLM usage 对象，记录 prompt cache 命中率到日志。"""
    if usage is None:
        return
    try:
        total = int(getattr(usage, "prompt_tokens", 0) or 0)
    except (TypeError, ValueError):
        return
    if total == 0:
        return
    details = getattr(usage, "prompt_tokens_details", None)
    try:
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
    except (TypeError, ValueError):
        cached = 0
    hit_rate = (cached / total * 100) if total > 0 else 0
    logger.info(
        "LLM cache: hit=%d/%d (%.1f%%)",
        cached,
        total,
        hit_rate,
    )


def _normalize_usage(usage: Any) -> dict[str, int] | None:
    """将 OpenAI 兼容网关的 usage 对象统一为 Trace 字段。"""
    if usage is None:
        return None

    def read(*names: str) -> int | None:
        for name in names:
            value = (
                usage.get(name)
                if isinstance(usage, dict)
                else getattr(usage, name, None)
            )
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None

    normalized: dict[str, int] = {}
    fields = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
        "reasoning_tokens": ("reasoning_tokens",),
        "cached_tokens": ("cached_tokens",),
    }
    for target, names in fields.items():
        value = read(*names)
        if value is not None:
            normalized[target] = value

    prompt_details = (
        usage.get("prompt_tokens_details")
        if isinstance(usage, dict)
        else getattr(usage, "prompt_tokens_details", None)
    )
    if isinstance(prompt_details, dict):
        cached = prompt_details.get("cached_tokens")
    elif prompt_details is not None:
        cached = getattr(prompt_details, "cached_tokens", None)
    else:
        cached = None
    if "cached_tokens" not in normalized and cached is not None:
        try:
            normalized["cached_tokens"] = int(cached)
        except (TypeError, ValueError):
            pass

    return normalized or None


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Synchronous chat call. Returns {content, tool_calls}.

    遇到可重试异常时最多重试 MAX_RETRIES 次。
    """
    logger.info(
        "LLM call: model=%s messages=%d tools=%d",
        MODEL,
        len(messages),
        len(tools or []),
    )
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = _sync_client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            msg = choice.message
            tool_calls: list[dict[str, Any]] = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    args_raw = tc.function.arguments or "{}"
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        logger.warning("malformed tool args: %s", args_raw)
                        args = {"_raw": args_raw}
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": args,
                        }
                    )
            _log_cache_metrics(getattr(resp, "usage", None))
            result = {
                "content": msg.content or "",
                "tool_calls": tool_calls,
                "finish_reason": choice.finish_reason,
            }
            token_usage = _normalize_usage(getattr(resp, "usage", None))
            if token_usage:
                result["token_usage"] = token_usage
            return result
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES and _is_retryable(exc):
                logger.warning(
                    "LLM call attempt %d failed (retryable: %s), retry in %ss",
                    attempt + 1,
                    type(exc).__name__,
                    RETRY_DELAY_SECONDS,
                )
                import time

                time.sleep(RETRY_DELAY_SECONDS)
                continue
            raise

    # 理论上不会走到这里
    raise last_exc  # type: ignore[misc]


async def chat_stream(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async streaming chat. Yields incremental tokens.

    Each yielded dict is one of:
      - {"type": "text", "delta": "..."}  — text token
      - {"type": "tool_call", "name": "...", "arguments_delta": "...", "index": int}
      - {"type": "done", "content": full_text, "tool_calls": [...]}
      - {"type": "error", "message": "..."}

    重试策略：只在「还没 yield 任何内容」时重试。一旦开始 yield，
    说明 LLM 已经在生成，中断后重试会导致内容重复，前端无法处理。
    """
    logger.info(
        "LLM stream: model=%s messages=%d tools=%d",
        MODEL,
        len(messages),
        len(tools or []),
    )
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        full_content = ""
        tool_calls_map: dict[int, dict[str, Any]] = {}
        has_yielded = False  # 本轮是否已经 yield 过内容

        try:
            # 请求 streaming usage 以收集 prompt cache 命中率
            kwargs.setdefault("stream_options", {"include_usage": True})
            stream = await _async_client.chat.completions.create(**kwargs)
            stream_usage: Any = None
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    stream_usage = chunk.usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    full_content += delta.content
                    yield {"type": "text", "delta": delta.content}
                    has_yielded = True

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name or "",
                                "arguments_raw": "",
                            }
                        tc = tool_calls_map[idx]
                        if tc_delta.function.name:
                            tc["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc["arguments_raw"] += tc_delta.function.arguments
                        yield {
                            "type": "tool_call",
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments_delta": tc_delta.function.arguments or "",
                            "index": idx,
                        }
                        has_yielded = True

            tool_calls: list[dict[str, Any]] = []
            for idx in sorted(tool_calls_map.keys()):
                tc = tool_calls_map[idx]
                try:
                    args = json.loads(tc["arguments_raw"] or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": tc["arguments_raw"]}
                tool_calls.append(
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": args,
                    }
                )

            tool_calls = await _repair_empty_stream_tool_calls(
                messages, tools, tool_calls, temperature
            )

            _log_cache_metrics(stream_usage)
            done_event = {
                "type": "done",
                "content": full_content,
                "tool_calls": tool_calls,
            }
            token_usage = _normalize_usage(stream_usage)
            if token_usage:
                done_event["token_usage"] = token_usage
            yield done_event
            return  # 成功完成，退出重试循环

        except Exception as exc:
            last_exc = exc
            # 已经 yield 过内容 → 不能重试（会导致前端内容重复）
            if has_yielded:
                logger.exception(
                    "LLM stream failed mid-stream (no retry, already yielded)"
                )
                classified = classify_exception(exc)
                payload = error_payload(
                    classified,
                    attempt=attempt,
                    stream_started=True,
                )
                yield {
                    "type": "error",
                    "message": _stream_error_message(exc, stream_started=True),
                    "data": payload,
                }
                return

            # 还没 yield 任何内容 → 可以重试
            if attempt < MAX_RETRIES and _is_retryable(exc):
                delay = _retry_delay(attempt)
                logger.warning(
                    "LLM stream attempt %d failed (retryable: %s), retry in %.2fs",
                    attempt + 1,
                    type(exc).__name__,
                    delay,
                )
                yield {
                    "type": "retrying",
                    "data": {
                        "code": "llm_retrying",
                        "category": "transient",
                        "attempt": attempt + 1,
                        "delay_ms": int(delay * 1000),
                    },
                }
                await asyncio.sleep(delay)
                continue

            # 不可重试或重试次数用完
            logger.exception("LLM stream failed (no more retries)")
            classified = classify_exception(exc)
            payload = error_payload(classified, attempt=attempt)
            yield {
                "type": "error",
                "message": payload["message"],
                "data": payload,
            }
            return

    # 理论上不会走到这里
    if last_exc:
        classified = classify_exception(last_exc)
        payload = error_payload(classified, attempt=MAX_RETRIES)
        yield {
            "type": "error",
            "message": payload["message"],
            "data": payload,
        }
