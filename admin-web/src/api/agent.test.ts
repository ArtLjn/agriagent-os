import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import {
  getSessionDebugExport,
  listAppSkills,
  mapSseToChunk,
  parseSseStream,
  refreshDailyAdvice,
  streamChat,
} from './agent';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('agent api', () => {
  it('解析 SSE id 并透传 v2 trace 元数据', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          'id: evt-7\nevent: assistant_delta\ndata: {"trace_id":"trace-7","turn_id":"turn-7","conversation_id":"conv-7","seq":7,"delta":"hi"}\n\n',
        ));
        controller.close();
      },
    });

    const events = [];
    for await (const event of parseSseStream(body)) events.push(event);

    expect(events).toEqual([
      {
        type: 'assistant_delta',
        data: {
          trace_id: 'trace-7',
          turn_id: 'turn-7',
          conversation_id: 'conv-7',
          seq: 7,
          delta: 'hi',
          event_id: 'evt-7',
        },
      },
    ]);
  });

  it('streamChat 透传 client_request_id 和 after_seq，并先发 trace meta', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(
            'id: evt-8\nevent: assistant_delta\ndata: {"trace_id":"trace-8","request_id":"req-8","turn_id":"turn-8","conversation_id":"conv-8","seq":8,"delta":"hi"}\n\n',
          ));
          controller.enqueue(new TextEncoder().encode(
            'event: done\ndata: {"trace_id":"trace-8","turn_id":"turn-8","conversation_id":"conv-8","seq":9,"status":"completed"}\n\n',
          ));
          controller.close();
        },
      }),
    }));

    const chunks = [];
    for await (const chunk of streamChat('你好', 'conv-8', null, {
      client_request_id: 'client-8',
      after_seq: 7,
    })) chunks.push(chunk);

    expect(fetch).toHaveBeenCalledWith('/api/agent/chat?after_seq=7', expect.objectContaining({
      body: JSON.stringify({
        message: '你好',
        conversation_id: 'conv-8',
        client_request_id: 'client-8',
      }),
    }));
    expect(chunks[0]).toEqual({
      type: 'meta',
      data: {
        event_id: 'evt-8',
        trace_id: 'trace-8',
        request_id: 'req-8',
        turn_id: 'turn-8',
        conversation_id: 'conv-8',
        seq: 8,
        event_type: 'assistant_delta',
        phase: undefined,
        terminal: undefined,
      },
    });
    expect(chunks.some((chunk) => chunk.type === 'done')).toBe(true);
  });

  it('将推理增量映射为对话内容增量', () => {
    expect(
      mapSseToChunk({ type: 'assistant_delta', data: { delta: '正在查询' } }),
    ).toEqual({ type: 'content', data: '正在查询' });
  });

  it('保留 LLM 重试事件供执行时间线展示', () => {
    expect(
      mapSseToChunk({
        type: 'retrying',
        data: { code: 'llm_retrying', category: 'transient', attempt: 1, delay_ms: 1000 },
      }),
    ).toEqual({
      type: 'retrying',
      data: { code: 'llm_retrying', category: 'transient', attempt: 1, delay_ms: 1000 },
    });
  });

  it('保留尚未完成的 Tool Call 参数增量', () => {
    expect(
      mapSseToChunk({
        type: 'tool_call_delta',
        data: { tool_call_id: 'call-1', name: 'get_weather', index: 0, arguments_delta: '{"location":' },
      }),
    ).toEqual({
      type: 'tool_call_delta',
      data: { tool_call_id: 'call-1', name: 'get_weather', index: 0, arguments_delta: '{"location":' },
    });
  });

  it('读取 App 端技能列表接口', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            key: 'create_cost_record',
            title: '智能记账',
            description: '一句话生成账本记录',
            category: '记录',
            icon: 'receipt-yuan',
            icon_color: 'green',
            recommended: true,
            enabled: true,
          },
        ],
        total: 1,
      },
    });

    const result = await listAppSkills();

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/skills');
    expect(result.items[0].title).toBe('智能记账');
  });

  it('强制刷新每日建议接口', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        cycle_id: 7,
        advice: '重新生成的建议',
        created_at: '2026-06-13T10:00:00',
      },
    });

    const result = await refreshDailyAdvice(7);

    expect(mockedApiClient.post).toHaveBeenCalledWith('/agent/daily/refresh', null, {
      params: { cycle_id: 7 },
    });
    expect(result.advice).toBe('重新生成的建议');
  });

  it('读取会话 debug export v2 并透传模拟用户', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        format: 'farm-manager.chat-session-debug.v2',
        session: { session_id: 'sess-1' },
        messages: [],
        turns: [],
        pending_plans: [],
        events: [],
        missing_event_segments: [],
      },
    });

    const result = await getSessionDebugExport('sess-1', 'user-1');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/conversations/sess-1/debug-export', {
      params: { simulate_user_id: 'user-1' },
    });
    expect(result.format).toBe('farm-manager.chat-session-debug.v2');
  });
});
