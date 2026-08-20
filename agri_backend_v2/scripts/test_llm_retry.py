"""LLM 重试机制单元测试：用 mock 模拟网络断开，验证重试逻辑。

跑法：
  cd /Users/ljn/Documents/demo/explore/agri_backend_v2
  uv run --package farm-manager-agent python scripts/test_llm_retry.py

测试场景：
  1. chat_stream 第一次抛 RemoteProtocolError → 重试第二次成功
  2. chat_stream 已经 yield 内容后失败 → 不重试，返回友好错误
  3. chat_stream 不可重试异常（ValueError）→ 不重试
  4. chat_stream 连续 3 次失败 → 重试次数用完，返回 error
  5. chat（同步）第一次失败 → 重试第二次成功
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# 允许从 agri_backend_v2/scripts/ 直接运行
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# 降低重试间隔，让测试跑得快
import agent.infra.llm as llm_mod
llm_mod.RETRY_DELAY_SECONDS = 0.01

from agent.infra import llm  # noqa: E402


# ─── Mock 工具：构造假的 OpenAI stream response ────────────────

class _FakeDelta:
    """模拟 OpenAI ChatCompletionChunk 的 delta。"""
    def __init__(self, content: str | None = None, tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, delta: _FakeDelta):
        self.delta = delta
        self.finish_reason = "stop"


class _FakeChunk:
    def __init__(self, delta: _FakeDelta):
        self.choices = [_FakeChoice(delta)]


class _FakeStream:
    """假的 async iterable，模拟 openai 的 stream。"""
    def __init__(self, chunks: list[_FakeChunk]):
        self._chunks = chunks
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


def _make_text_stream(text: str) -> _FakeStream:
    """构造一个返回纯文本的假 stream（逐字符 yield）。"""
    chunks = [_FakeChunk(_FakeDelta(content=ch)) for ch in text]
    chunks.append(_FakeChunk(_FakeDelta()))  # 结束 chunk
    return _FakeStream(chunks)


def _make_tool_call_stream(name: str, args: dict) -> _FakeStream:
    """构造一个返回 tool_call 的假 stream。"""
    import json
    # 模拟 tool_call 的分片 yield
    tc_delta = MagicMock()
    tc_delta.index = 0
    tc_delta.id = "call_001"
    tc_delta.function = MagicMock()
    tc_delta.function.name = name
    tc_delta.function.arguments = json.dumps(args)
    chunks = [
        _FakeChunk(_FakeDelta(tool_calls=[tc_delta])),
        _FakeChunk(_FakeDelta()),  # 结束
    ]
    return _FakeStream(chunks)


# ─── 测试用例 ─────────────────────────────────────────────────

class ChatStreamRetryTests(unittest.IsolatedAsyncioTestCase):
    """chat_stream 的重试行为测试。"""

    async def test_1_retries_on_remote_protocol_error(self):
        """场景 1：第一次抛 RemoteProtocolError，第二次成功 → 验证重试生效。"""
        import httpcore
        fake_error = httpcore.RemoteProtocolError(
            "peer closed connection without sending complete message body"
        )

        # 第一次抛异常，第二次返回正常 stream
        mock_create = AsyncMock(
            side_effect=[
                fake_error,
                _make_text_stream("你好世界"),
            ]
        )

        with patch.object(llm._async_client.chat.completions, "create", mock_create):
            events = []
            async for ev in llm.chat_stream([{"role": "user", "content": "hi"}]):
                events.append(ev)

        # 验证调用了 2 次（1 次失败 + 1 次成功）
        self.assertEqual(mock_create.call_count, 2,
                         f"应调用 2 次，实际 {mock_create.call_count} 次")

        # 验证最终成功
        done_events = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done_events), 1, "应有 1 个 done 事件")
        self.assertEqual(done_events[0]["content"], "你好世界")

        # 验证没有 error 事件
        error_events = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(error_events), 0, "不应有 error 事件")

        print("  ✓ [1/5] chat_stream 在 RemoteProtocolError 后重试成功")

    async def test_2_no_retry_after_yield(self):
        """场景 2：已经 yield 内容后失败 → 不重试，返回友好错误。"""
        import httpcore

        # 构造一个"中途断开"的 stream：先 yield "你"，再抛异常
        class _StreamThatBreaksMidWay:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration  # 第一次 __anext__ 就停止

        # 但我们想在 yield 一个 chunk 之后再断开
        # 用一个特殊的 stream：先返回一个 chunk，第二次 raise
        class _MidWayBreakStream:
            def __init__(self):
                self._yielded = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._yielded:
                    self._yielded = True
                    return _FakeChunk(_FakeDelta(content="你"))
                raise httpcore.RemoteProtocolError("mid-stream break")

        mock_create = AsyncMock(return_value=_MidWayBreakStream())

        with patch.object(llm._async_client.chat.completions, "create", mock_create):
            events = []
            async for ev in llm.chat_stream([{"role": "user", "content": "hi"}]):
                events.append(ev)

        # 验证只调用了 1 次（不重试）
        self.assertEqual(mock_create.call_count, 1,
                         f"应只调用 1 次（已 yield 不重试），实际 {mock_create.call_count} 次")

        # 验证有 text 事件（已 yield 的内容）
        text_events = [e for e in events if e["type"] == "text"]
        self.assertEqual(len(text_events), 1, "应有 1 个 text 事件（yield 过的内容）")
        self.assertEqual(text_events[0]["delta"], "你")

        # 验证有 error 事件，且消息友好
        error_events = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(error_events), 1, "应有 1 个 error 事件")
        self.assertIn("网络中断", error_events[0]["message"],
                      "错误消息应包含「网络中断」")

        # 验证没有 done 事件
        done_events = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done_events), 0, "不应有 done 事件")

        print("  ✓ [2/5] chat_stream 已 yield 后失败不重试，返回友好错误")

    async def test_3_no_retry_on_non_retryable(self):
        """场景 3：不可重试异常（ValueError）→ 不重试。"""
        # ValueError 不在可重试列表里
        mock_create = AsyncMock(side_effect=ValueError("bad request"))

        with patch.object(llm._async_client.chat.completions, "create", mock_create):
            events = []
            async for ev in llm.chat_stream([{"role": "user", "content": "hi"}]):
                events.append(ev)

        # 验证只调用了 1 次（不重试）
        self.assertEqual(mock_create.call_count, 1,
                         f"应只调用 1 次（不可重试），实际 {mock_create.call_count} 次")

        # 验证有 error 事件
        error_events = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(error_events), 1, "应有 1 个 error 事件")
        self.assertIn("bad request", error_events[0]["message"])

        print("  ✓ [3/5] chat_stream 不可重试异常不重试")

    async def test_4_exhausts_retries(self):
        """场景 4：连续 3 次都失败（MAX_RETRIES+1）→ 重试次数用完，返回 error。"""
        import httpcore
        fake_error = httpcore.RemoteProtocolError("persistent network issue")

        # 连续 3 次都失败（1 次初始 + 2 次重试 = MAX_RETRIES+1）
        mock_create = AsyncMock(side_effect=[fake_error, fake_error, fake_error])

        with patch.object(llm._async_client.chat.completions, "create", mock_create):
            events = []
            async for ev in llm.chat_stream([{"role": "user", "content": "hi"}]):
                events.append(ev)

        # 验证调用了 3 次（1 + MAX_RETRIES=2）
        self.assertEqual(mock_create.call_count, 3,
                         f"应调用 3 次（1+MAX_RETRIES），实际 {mock_create.call_count} 次")

        # 验证有 error 事件
        error_events = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(error_events), 1, "应有 1 个 error 事件")

        print("  ✓ [4/5] chat_stream 连续失败 3 次后返回 error")

    async def test_5_tool_call_stream_succeeds_after_retry(self):
        """场景 5：带 tool_calls 的流式响应也能重试。"""
        import httpcore
        fake_error = httpcore.RemoteProtocolError("first attempt failed")

        mock_create = AsyncMock(
            side_effect=[
                fake_error,
                _make_tool_call_stream("get_weather", {"location": "北京"}),
            ]
        )

        with patch.object(llm._async_client.chat.completions, "create", mock_create):
            events = []
            async for ev in llm.chat_stream([{"role": "user", "content": "天气"}], tools=[]):
                events.append(ev)

        # 验证重试成功
        self.assertEqual(mock_create.call_count, 2, "应调用 2 次")

        done_events = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done_events), 1, "应有 1 个 done 事件")
        tool_calls = done_events[0]["tool_calls"]
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "get_weather")
        self.assertEqual(tool_calls[0]["arguments"], {"location": "北京"})

        print("  ✓ [5/5] chat_stream 带 tool_calls 的响应也能重试")


class ChatSyncRetryTests(unittest.TestCase):
    """chat（同步）的重试行为测试。"""

    def test_sync_chat_retries_on_network_error(self):
        """同步 chat 第一次失败，第二次成功。"""
        import httpcore
        fake_error = httpcore.RemoteProtocolError("network down")

        # 构造假的 response
        fake_msg = MagicMock()
        fake_msg.content = "hello back"
        fake_msg.tool_calls = None
        fake_choice = MagicMock()
        fake_choice.message = fake_msg
        fake_choice.finish_reason = "stop"
        fake_resp = MagicMock()
        fake_resp.choices = [fake_choice]

        mock_create = MagicMock(
            side_effect=[fake_error, fake_resp]
        )

        with patch.object(llm._sync_client.chat.completions, "create", mock_create):
            result = llm.chat([{"role": "user", "content": "hi"}])

        # 验证调用了 2 次
        self.assertEqual(mock_create.call_count, 2,
                         f"应调用 2 次，实际 {mock_create.call_count} 次")

        # 验证返回正确
        self.assertEqual(result["content"], "hello back")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["finish_reason"], "stop")

        print("  ✓ [6/6] chat（同步）在 RemoteProtocolError 后重试成功")


def main():
    print("=" * 60)
    print("LLM 重试机制测试")
    print("=" * 60)
    print()
    print("配置：MAX_RETRIES =", llm.MAX_RETRIES,
          "| RETRY_DELAY =", llm_mod.RETRY_DELAY_SECONDS, "s (测试用快速间隔)")
    print()

    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ChatStreamRetryTests))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ChatSyncRetryTests))

    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print("=" * 60)
        print("✓ 所有测试通过！重试机制生效。")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("✗ 测试失败：")
        for failure in result.failures:
            print(f"  - {failure[0]}")
        for error in result.errors:
            print(f"  - {error[0]}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
