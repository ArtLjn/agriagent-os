import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import {
  getSessionDebugExport,
  listAppSkills,
  mapSseToChunk,
  parseSseStream,
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
  it('解析 SSE id 并透传 agri_backend_v2 trace 元数据', async () => {
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

  it.each([false, true])('streamChat 透传请求标识和临时模式 %s，并先发 trace meta', async (temporary) => {
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
      temporary,
    })) chunks.push(chunk);

    expect(fetch).toHaveBeenCalledWith('/api/agent/chat?after_seq=7', expect.objectContaining({
      body: JSON.stringify({
        message: '你好',
        conversation_id: 'conv-8',
        client_request_id: 'client-8',
        temporary,
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

  it('保留工具开始和完成事件供 Playground 合并生命周期', () => {
    expect(mapSseToChunk({
      type: 'tool_started',
      data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: {} },
    })).toEqual({
      type: 'tool_started',
      data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: {} },
    });
    expect(mapSseToChunk({
      type: 'tool_finished',
      data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, duration_ms: 18, result: { ok: true } },
    })).toMatchObject({
      type: 'tool_finished',
      data: { tool_call_id: 'c-1', duration_ms: 18 },
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

  it('后端缺少调试导出端点时保留显式失败供页面本地导出', async () => {
    mockedApiClient.get.mockClear();

    await expect(getSessionDebugExport('sess-1', 'user-1')).rejects.toThrow(
      'session debug export endpoint not available',
    );
    expect(mockedApiClient.get).not.toHaveBeenCalled();
  });
});
