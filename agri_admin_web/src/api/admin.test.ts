import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { getTimeline, getTraceDiagnostics } from './admin';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
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
    expect(result.rounds[0].nodes).toHaveLength(1);
    expect(result.events?.[0].event_id).toBe('evt-1');
  });

  it('通过已有 diagnostics 接口读取 Reflection 诊断', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        request_id: 'req:1',
        reflection_checks: [
          {
            trigger: 'pre_write_plan',
            decision: 'block_write',
            reason: '确认文案不一致',
            checks: ['write_plan_consistency'],
            issues: [
              {
                code: 'confirmation_param_mismatch',
                severity: 'blocker',
                message: '确认文案中的对象与参数不一致',
              },
            ],
            input: { tool_name: 'create_cost_record' },
          },
        ],
        reflection_diagnostic: {
          blocked: true,
          decisions: ['block_write'],
          issue_codes: ['confirmation_param_mismatch'],
        },
      },
    });

    const result = await getTraceDiagnostics('req:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/traces/req:1/diagnostics');
    expect(result.reflection_checks[0].checks).toEqual(['write_plan_consistency']);
  });
});
