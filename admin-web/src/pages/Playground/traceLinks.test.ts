import { describe, expect, it } from 'vitest';

import { buildTraceMonitorUrl, selectLatestTraceId } from './traceLinks';

describe('buildTraceMonitorUrl', () => {
  it('有 trace_id 时携带正式 trace_id 和 conversation_id', () => {
    expect(
      buildTraceMonitorUrl({ conversationId: 'sess-1', traceId: 'trace-1' }),
    ).toBe('/dev/traces?trace_id=trace-1&conversation_id=sess-1');
  });

  it('没有 request_id 时仍按 conversation_id 跳转链路页', () => {
    expect(buildTraceMonitorUrl({ conversationId: 'sess-1' })).toBe(
      '/dev/traces?conversation_id=sess-1',
    );
  });
});

describe('selectLatestTraceId', () => {
  it('返回 trace 列表中第一条有效 trace_id', () => {
    expect(
      selectLatestTraceId([
        { trace_id: '   ' },
        { trace_id: 'trace-2' },
      ]),
    ).toBe('trace-2');
  });

  it('没有有效 trace_id 时返回 null', () => {
    expect(selectLatestTraceId([{ trace_id: ' ' }])).toBeNull();
  });
});
