import { describe, expect, it } from 'vitest';

import { buildConversationRows } from './conversationRows';
import {
  applyHistoricalPendingResolution,
  canConfirmAssistantMessage,
  hasPendingConfirmationControls,
  isPendingPlanContent,
  type AssistantMessage,
} from './pendingPlanControls';

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

describe('pending plan confirmation controls', () => {
  it('识别 pending plan 文本并允许显示确认取消按钮', () => {
    const content = '请确认将执行 2 步（共 2 个步骤）：\n1. 创建工人：李1\n确认执行吗？';

    expect(isPendingPlanContent(content)).toBe(true);
    expect(
      canConfirmAssistantMessage({
        role: 'assistant',
        content,
        pendingAction: null,
      }),
    ).toBe(true);
  });

  it('普通助手消息不显示确认取消按钮', () => {
    expect(
      canConfirmAssistantMessage({
        role: 'assistant',
        content: '今天天气不错',
        pendingAction: null,
      }),
    ).toBe(false);
  });

  it('识别结构化 pending_plan 字段并允许确认', () => {
    expect(
      canConfirmAssistantMessage({
        role: 'assistant',
        content: '我将执行这些步骤，请确认。',
        pendingAction: null,
        pending_plan: {
          plan_id: 'plan-1',
          steps: [{ skill_name: 'manage_workers' }],
        },
      }),
    ).toBe(true);
  });

  it('已处理的 pending plan 文本不再允许再次确认', () => {
    const content = '请确认将执行 1 步（共 1 个步骤）：\n1. 创建茬口：西瓜 8424\n确认执行吗？';

    expect(
      canConfirmAssistantMessage({
        role: 'assistant',
        content,
        pendingAction: null,
        pendingResolution: 'confirmed',
      }),
    ).toBe(false);
  });

  it('已确认/取消的 pending 消息不再渲染确认取消按钮', () => {
    const content = '请确认将执行 1 步（共 1 个步骤）：\n1. 创建茬口：西瓜 8424\n确认执行吗？';
    expect(
      hasPendingConfirmationControls({
        role: 'assistant',
        content,
        pendingAction: null,
        pendingResolution: 'confirmed',
      }),
    ).toBe(false);
    expect(
      hasPendingConfirmationControls({
        role: 'assistant',
        content,
        pendingAction: null,
        pendingResolution: 'canceled',
      }),
    ).toBe(false);
  });
});

describe('applyHistoricalPendingResolution', () => {
  const pendingContent = '请确认将执行 1 步（共 1 个步骤）：\n1. 创建茬口：西瓜 8424\n确认执行吗？';

  it('非末尾的 pending 消息被标记为已确认，按钮不再显示', () => {
    const messages: AssistantMessage[] = [
      { role: 'assistant', content: pendingContent },
      { role: 'user', content: '确认' },
      { role: 'assistant', content: '已创建' },
    ];
    const result = applyHistoricalPendingResolution(messages);
    expect(result[0].pendingResolution).toBe('confirmed');
    expect(hasPendingConfirmationControls(result[0])).toBe(false);
  });

  it('末尾的 pending 消息保留可执行（可能仍处于活跃等待）', () => {
    const messages: AssistantMessage[] = [
      { role: 'user', content: '帮我建茬口' },
      { role: 'assistant', content: pendingContent },
    ];
    const result = applyHistoricalPendingResolution(messages);
    expect(result[1].pendingResolution).toBeUndefined();
    expect(hasPendingConfirmationControls(result[1])).toBe(true);
  });

  it('结构化 pending_plan 字段同样按位置推断', () => {
    const messages: AssistantMessage[] = [
      {
        role: 'assistant',
        content: '我将执行这些步骤，请确认。',
        pending_plan: { plan_id: 'plan-1', steps: [{ skill_name: 'manage_workers' }] },
      },
      { role: 'user', content: '确认' },
    ];
    const result = applyHistoricalPendingResolution(messages);
    expect(result[0].pendingResolution).toBe('confirmed');
  });

  it('没有 pending 的消息原样返回', () => {
    const messages: AssistantMessage[] = [
      { role: 'assistant', content: '今天天气不错' },
      { role: 'user', content: '谢谢' },
    ];
    const result = applyHistoricalPendingResolution(messages);
    expect(result[0].pendingResolution).toBeUndefined();
    expect(result[1].pendingResolution).toBeUndefined();
  });

  it('空数组安全返回', () => {
    expect(applyHistoricalPendingResolution<AssistantMessage>([])).toEqual([]);
  });
});
