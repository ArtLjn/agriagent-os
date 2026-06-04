import { describe, expect, it } from 'vitest';

import { formatTracePayload, hasTracePayload } from './tracePayload';

describe('tracePayload', () => {
  it('格式化对象 payload', () => {
    expect(formatTracePayload({ foo: 'bar', count: 2 })).toBe('{\n  "foo": "bar",\n  "count": 2\n}');
  });

  it('格式化 JSON 字符串 payload', () => {
    expect(formatTracePayload('{"foo":"bar"}')).toBe('{\n  "foo": "bar"\n}');
  });

  it('反转义非 JSON 字符串 payload', () => {
    expect(formatTracePayload('line1\\nline2\\t\\"ok\\"')).toBe('line1\nline2\t"ok"');
  });

  it('识别空 payload', () => {
    expect(hasTracePayload(null)).toBe(false);
    expect(hasTracePayload(undefined)).toBe(false);
    expect(hasTracePayload('')).toBe(false);
    expect(hasTracePayload({})).toBe(true);
  });
});
