import { describe, expect, it } from 'vitest';

import { buildTraceMonitorUrl, selectLatestTraceRequestId } from './traceLinks';

describe('buildTraceMonitorUrl', () => {
  it('有 request_id 时同时携带 request_id 和 session_id', () => {
    expect(
      buildTraceMonitorUrl({ sessionId: 'sess-1', requestId: 'req-1' }),
    ).toBe('/dev/traces?request_id=req-1&session_id=sess-1');
  });

  it('没有 request_id 时仍按 session_id 跳转链路页', () => {
    expect(buildTraceMonitorUrl({ sessionId: 'sess-1' })).toBe(
      '/dev/traces?session_id=sess-1',
    );
  });
});

describe('selectLatestTraceRequestId', () => {
  it('返回 trace 列表中第一条有效 request_id', () => {
    expect(
      selectLatestTraceRequestId([
        { request_id: '   ' },
        { request_id: 'req-2' },
      ]),
    ).toBe('req-2');
  });

  it('没有有效 request_id 时返回 null', () => {
    expect(selectLatestTraceRequestId([{ request_id: ' ' }])).toBeNull();
  });
});
