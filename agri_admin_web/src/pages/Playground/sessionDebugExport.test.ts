import { describe, expect, it } from 'vitest';

import type { TraceTimeline } from '../../api/admin';
import type { PendingAction } from '../../api/agent';
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
      trace_request_id: 'req-1',
      execution_record_status: 'available',
      execution_record_note: null,
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

  it('保留消息、技能和待确认动作', () => {
    const pendingAction: PendingAction = {
      action_id: 'action-1',
      skill_name: 'create_cost_record',
      params: { amount: 100 },
    };

    const exported = buildSessionDebugExport({
      sessionId: 'session-1',
      copiedAt: '2026-06-10T00:00:00.000Z',
      messages: [
        { role: 'user', content: '记一笔肥料钱' },
        {
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
      {
        role: 'assistant',
        content: '请确认',
        skills: ['create_cost_record'],
        pending_action: pendingAction,
      },
    ]);
    expect(exported.used_skills).toEqual(['create_cost_record']);
    expect(exported.execution_record_status).toBe('unavailable');
    expect(exported.pending_actions).toEqual([
      {
        message_index: 1,
        action_id: 'action-1',
        skill_name: 'create_cost_record',
        params: { amount: 100 },
        context: undefined,
      },
    ]);
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
      copiedAt: '2026-06-10T00:00:00.000Z',
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
    expect(exported.execution_record_status).toBe('available');
  });

  it('导出 Runtime 实际产生的 tool_call 及 Agent 到 MCP 映射', () => {
    const timeline: TraceTimeline = {
      request_id: 'request-2',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'tool_call',
              node_name: 'list_system_crop_templates',
              step_index: 2,
              duration_ms: 18,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              error_code: null,
              input_data: { crop_type: '水稻' },
              output_data: { templates: [] },
              attributes: {
                tool_call_id: 'call-2',
                agent_tool_name: 'list_system_crop_templates',
                business_tool_name: 'manage_crop_cycle',
                operation: 'system_templates',
                progress: 'advanced',
                progress_reason: 'new_observation',
                observation_fingerprint: 'sha256:test',
              },
            },
          ],
        },
      ],
    };

    const exported = buildSessionDebugExport({
      sessionId: 'session-2',
      copiedAt: '2026-06-10T00:00:00.000Z',
      messages: [],
      timeline,
    });

    expect(exported.skill_calls).toEqual([
      expect.objectContaining({
        skill_name: 'list_system_crop_templates',
        step_index: 2,
        tool_call_id: 'call-2',
        agent_tool_name: 'list_system_crop_templates',
        business_tool_name: 'manage_crop_cycle',
        operation: 'system_templates',
        progress: 'advanced',
      }),
    ]);
    expect(exported.execution_record_status).toBe('available');
  });

  it('没有实际 Tool 执行节点时明确标记证据缺失', () => {
    const exported = buildSessionDebugExport({
      sessionId: 'session-empty',
      copiedAt: '2026-08-27T00:00:00.000Z',
      messages: [{ role: 'assistant', content: '已选择查询能力', skills: ['query_workers'] }],
      timeline: {
        request_id: 'request-empty',
        rounds: [{ round_index: 1, nodes: [] }],
      },
    });

    expect(exported.skill_calls).toEqual([]);
    expect(exported.execution_record_status).toBe('none');
    expect(exported.execution_record_note).toBe('无实际 Tool 执行记录');
  });
});
