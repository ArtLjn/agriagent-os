import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getTimeline, getTraceDiagnostics, getTokenSummary, getDailyTokenStats, getHourlyTokenStats, listPrompts, reloadPrompts } from './admin';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('admin api', () => {
  it('通过正式 agri_backend_v2 timeline 接口读取节点和事件，并补充 summary', async () => {
    mockedApiClient.get
      .mockResolvedValueOnce({
        data: {
          trace_id: 'trace-1',
          request_id: 'req-1',
          conversation_id: 'conv-1',
          turn_id: 'turn-1',
          items: [
            {
              record_kind: 'node',
              id: 'span-1',
              node_type: 'llm',
              node_name: 'planner',
              step_index: 2,
              duration_ms: 12,
              status: 'completed',
              token_usage: null,
              start_time: null,
            },
            {
              record_kind: 'event',
              source: 'traceEvents',
              event_id: 'evt-1',
              trace_id: 'trace-1',
              turn_id: 'turn-1',
              seq: 2,
              event_type: 'done',
              terminal: true,
              occurred_at: null,
            },
          ],
          count: 2,
          has_more: false,
        },
      })
      .mockResolvedValueOnce({
        data: { request_id: 'req-1', trace_id: 'trace-1', node_count: 1, total_duration_ms: 12 },
      });

    const result = await getTimeline('trace/1', { limit: 50, include_payload: false });

    expect(mockedApiClient.get).toHaveBeenNthCalledWith(1, '/agent/traces/trace%2F1/timeline', {
      params: { limit: 50, include_payload: false },
    });
    expect(mockedApiClient.get).toHaveBeenNthCalledWith(2, '/agent/traces/trace%2F1/summary');
    expect(result.trace_id).toBe('trace-1');
    expect(result.rounds).toHaveLength(1);
    expect(result.rounds[0].round_index).toBe(2);
    expect(result.rounds[0].nodes).toHaveLength(1);
    expect(result.events?.[0].event_id).toBe('evt-1');
  });

  it('v2 未提供独立 Reflection 诊断时返回明确失败且不发送请求', async () => {
    mockedApiClient.get.mockClear();

    await expect(getTraceDiagnostics('req:1')).rejects.toThrow(
      'trace diagnostics endpoint is not available',
    );
    expect(mockedApiClient.get).not.toHaveBeenCalled();
  });
});

 it('提示词与统计通过 Agent v2 代理访问', async () => {
  mockedApiClient.get.mockResolvedValue({ data: {} });
  mockedApiClient.post.mockResolvedValue({ data: {} });
  await listPrompts();
  await reloadPrompts();
  await getTokenSummary({ days: 7, user_id: 'u' });
  await getDailyTokenStats('2026-10-23');
  await getHourlyTokenStats({ model: 'a' });
  expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/admin/prompts');
  expect(mockedApiClient.post).toHaveBeenCalledWith('/agent/admin/prompts/reload');
  expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/admin/stats/tokens', { params: { days: 7, user_id: 'u' } });
  expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/admin/stats/tokens/daily', { params: { date: '2026-10-23' } });
  expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/admin/stats/tokens/hourly', { params: { model: 'a' } });
});
