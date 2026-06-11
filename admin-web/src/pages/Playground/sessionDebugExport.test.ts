import { describe, expect, it } from 'vitest';

import { buildSessionDebugExport } from './sessionDebugExport';

describe('buildSessionDebugExport', () => {
  it('导出聊天消息、pending action 和本轮 Skill 调用', () => {
    const exported = buildSessionDebugExport({
      sessionId: 'session-1',
      simulateUserId: 'user-1',
      copiedAt: '2026-06-10T00:00:00.000Z',
      messages: [
        { role: 'user', content: '今天李树去6号棚收水稻' },
        {
          role: 'assistant',
          content: '确认创建农事作业单',
          skills: ['create_operation_work_order'],
          pendingAction: {
            action_id: 'action-1',
            skill_name: 'create_operation_work_order',
            params: { 操作: '采收' },
          },
        },
      ],
      timeline: {
        request_id: 'req-1',
        rounds: [
          {
            round_index: 1,
            nodes: [
              {
                node_type: 'skill_call',
                node_name: 'create_operation_work_order',
                duration_ms: 0,
                status: 'success',
                token_usage: null,
                start_time: null,
                error_message: null,
                input_data: { operation_type: '采收', workers: '李树' },
                output_data: { status: 'pending' },
              },
            ],
          },
        ],
      },
    });

    expect(exported).toMatchObject({
      format: 'farm-manager.chat-session-debug.v1',
      session_id: 'session-1',
      simulate_user_id: 'user-1',
      copied_at: '2026-06-10T00:00:00.000Z',
      used_skills: ['create_operation_work_order'],
      pending_actions: [
        {
          message_index: 1,
          skill_name: 'create_operation_work_order',
        },
      ],
      skill_calls: [
        {
          round_index: 1,
          skill_name: 'create_operation_work_order',
          input_data: { operation_type: '采收', workers: '李树' },
          output_data: { status: 'pending' },
        },
      ],
    });
  });
});
