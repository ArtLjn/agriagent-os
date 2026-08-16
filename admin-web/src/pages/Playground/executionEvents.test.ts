import { describe, expect, it } from 'vitest';

import { executionEventFromChunk } from './executionEvents';

describe('executionEventFromChunk', () => {
  it('保留 SSE 事件的展示顺序和工具参数', () => {
    const thought = executionEventFromChunk({ type: 'thought', data: '先查找相关数据' });
    const action = executionEventFromChunk({
      type: 'action',
      data: { tool_name: 'search_weather', arguments: { city: '安庆' }, rationale: '需要最新气象信息' },
    });

    expect([thought, action].map((event) => event?.type)).toEqual(['thought', 'action']);
    expect(action).toMatchObject({ type: 'action', tool_name: 'search_weather', arguments: { city: '安庆' } });
  });

  it('将审批事件转换成可读的执行步骤', () => {
    expect(executionEventFromChunk({
      type: 'pending_action',
      data: { action_id: 'turn-1', skill_name: 'create_crop_cycle', params: { crop: '西瓜' } },
    })).toEqual({
      type: 'approval_required',
      tool_name: 'create_crop_cycle',
      arguments: { crop: '西瓜' },
    });
  });

  it('将未完成 Tool Call 增量保留在执行时间线', () => {
    expect(executionEventFromChunk({
      type: 'tool_call_delta',
      data: { tool_call_id: 'call-1', name: 'get_weather', index: 0, arguments_delta: '{"location":' },
    })).toEqual({
      type: 'tool_call_delta',
      tool_call_id: 'call-1',
      name: 'get_weather',
      index: 0,
      arguments_delta: '{"location":',
    });
  });

  it('将待确认计划保留为时间线中的计划卡片', () => {
    expect(executionEventFromChunk({
      type: 'pending_plan',
      data: { plan_id: 'plan-1', goal: '完成种植准备', steps: ['创建茬口'] },
    })).toEqual({ type: 'plan', goal: '完成种植准备', steps: ['创建茬口'] });
  });

  it('忽略不会进入执行时间线的内容事件', () => {
    expect(executionEventFromChunk({ type: 'content', data: '最终答案' })).toBeNull();
    expect(executionEventFromChunk({ type: 'done', data: { status: 'completed' } })).toBeNull();
  });
});
