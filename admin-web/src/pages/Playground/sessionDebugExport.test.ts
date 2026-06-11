import { describe, expect, it } from 'vitest';

import { buildSessionDebugExport } from './sessionDebugExport';
import type { TraceTimeline } from '../../api/admin';
import type { PendingAction } from '../../api/agent';

describe('buildSessionDebugExport', () => {
  it('保留消息、技能和待确认动作', () => {
    const pendingAction: PendingAction = {
      action_id: 'action-1',
      skill_name: 'create_cost_record',
      params: { amount: 100 },
    };

    const exported = buildSessionDebugExport({
      sessionId: 'session-1',
      messages: [
        { id: 'm1', role: 'user', content: '记一笔肥料钱' },
        {
          id: 'm2',
          role: 'assistant',
          content: '请确认',
          skills: ['create_cost_record'],
          pendingAction,
        },
      ],
      timeline: null,
    });

    expect(exported.messages).toEqual([
      { role: 'user', content: '记一笔肥料钱' },
      { role: 'assistant', content: '请确认' },
    ]);
    expect(exported.used_skills).toEqual(['create_cost_record']);
    expect(exported.pending_actions).toEqual([pendingAction]);
  });

  it('从 timeline 导出 skill calls、router diagnostics 和 pending plans', () => {
    const timeline: TraceTimeline = {
      request_id: 'request-1',
      rounds: [
        {
          round_index: 1,
          nodes: [
            {
              node_type: 'skill_router',
              node_name: 'skill_router',
              duration_ms: 1,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: { message: '农场状态' },
              output_data: { selected_tools: ['get_farm_status'] },
            },
            {
              node_type: 'skill_call',
              node_name: 'get_farm_status',
              duration_ms: 12,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: { farm_id: 1 },
              output_data: { active_crops: ['水稻'] },
            },
            {
              node_type: 'skill_call',
              node_name: 'pending_plan',
              duration_ms: 1,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: { skill_name: 'create_cost_record' },
              output_data: { action_id: 'action-1' },
            },
          ],
        },
      ],
    };

    const exported = buildSessionDebugExport({
      sessionId: 'session-1',
      messages: [],
      timeline,
    });

    expect(exported.skill_calls).toEqual([
      {
        round_index: 1,
        skill_name: 'get_farm_status',
        status: 'success',
        duration_ms: 12,
        input_data: { farm_id: 1 },
        output_data: { active_crops: ['水稻'] },
        error_message: null,
      },
    ]);
    expect(exported.router_diagnostics).toEqual([
      {
        round_index: 1,
        input_data: { message: '农场状态' },
        output_data: { selected_tools: ['get_farm_status'] },
      },
    ]);
    expect(exported.pending_plans).toEqual([
      {
        round_index: 1,
        input_data: { skill_name: 'create_cost_record' },
        output_data: { action_id: 'action-1' },
      },
    ]);
  });
});
