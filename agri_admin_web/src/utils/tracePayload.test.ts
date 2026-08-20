import { describe, expect, it } from 'vitest';

import { formatTracePayload, hasTracePayload } from './tracePayload';

describe('tracePayload', () => {
  it('格式化对象 payload', () => {
    expect(formatTracePayload({ foo: 'bar', count: 2 })).toBe('{\n  "foo": "bar",\n  "count": 2\n}');
  });

  it('格式化 JSON 字符串 payload', () => {
    expect(formatTracePayload('{"foo":"bar"}')).toBe('{\n  "foo": "bar"\n}');
  });

  it('格式化双层编码 JSON 字符串 payload', () => {
    const payload = JSON.stringify(JSON.stringify({
      token_budget: 900,
      blocks: [{ key: 'farm', preview: '农场：管理员农场' }],
    }));

    expect(formatTracePayload(payload)).toBe(
      '{\n  "token_budget": 900,\n  "blocks": [\n    {\n      "key": "farm",\n      "preview": "农场：管理员农场"\n    }\n  ]\n}'
    );
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
