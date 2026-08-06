"""LLM client wrapper.

Loads providers.json (OpenAI-compatible format) and exposes:
  - chat(messages, tools) -> {content, tool_calls}
  - chat_stream(messages, tools) -> AsyncGenerator yielding tokens

Uses openai SDK. The 'local' provider points to a self-hosted endpoint.
Model is configurable via env; defaults to qwen3.6-flash.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)

_PROVIDERS_FILE = Path(__file__).resolve().parent.parent.parent / "providers.json"


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


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Synchronous chat call. Returns {content, tool_calls}."""
    logger.info("LLM call: model=%s messages=%d tools=%d",
                MODEL, len(messages), len(tools or []))
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

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
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": args,
            })
    return {
        "content": msg.content or "",
        "tool_calls": tool_calls,
        "finish_reason": choice.finish_reason,
    }


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
    """
    logger.info("LLM stream: model=%s messages=%d tools=%d",
                MODEL, len(messages), len(tools or []))
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    full_content = ""
    tool_calls_map: dict[int, dict[str, Any]] = {}

    try:
        stream = await _async_client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                full_content += delta.content
                yield {"type": "text", "delta": delta.content}

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
                        "name": tc["name"],
                        "arguments_delta": tc_delta.function.arguments or "",
                        "index": idx,
                    }

        tool_calls: list[dict[str, Any]] = []
        for idx in sorted(tool_calls_map.keys()):
            tc = tool_calls_map[idx]
            try:
                args = json.loads(tc["arguments_raw"] or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc["arguments_raw"]}
            tool_calls.append({
                "id": tc["id"],
                "name": tc["name"],
                "arguments": args,
            })

        yield {
            "type": "done",
            "content": full_content,
            "tool_calls": tool_calls,
        }

    except Exception as exc:
        logger.exception("LLM stream failed")
        yield {"type": "error", "message": str(exc)}