import { describe, expect, it } from 'vitest';

import { buildConversationRows } from './conversationRows';

describe('buildConversationRows', () => {
  it('不显示没有消息和请求状态的本地 session', () => {
    const rows = buildConversationRows(
      {
        empty: { messages: [], loading: false, traceLoading: false, timeline: null },
        active: { messages: [{ id: 'm1', role: 'user', content: '你好' }], loading: false, traceLoading: false, timeline: null },
        loading: { messages: [], loading: true, traceLoading: false, timeline: null },
      },
      [],
    );

    expect(rows.map((row) => row.session_id)).toEqual(['active', 'loading']);
  });

  it('后端已存在的会话不重复追加本地行', () => {
    const rows = buildConversationRows(
      {
        persisted: { messages: [{ id: 'm1', role: 'user', content: '你好' }], loading: false, traceLoading: false, timeline: null },
      },
      [
        {
          id: 1,
          session_id: 'persisted',
          status: 'active',
          created_at: '2026-06-05T00:00:00Z',
          last_active_at: '2026-06-05T00:00:00Z',
        },
      ],
    );

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ session_id: 'persisted', local: false });
  });
});
