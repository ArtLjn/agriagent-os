import { describe, expect, it } from 'vitest';

import { appendExecutionEvent, executionEventFromChunk } from './executionEvents';
import { buildTimelineItems } from './ExecutionTimeline';

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

  it('保留用户投影的执行进度', () => {
    expect(executionEventFromChunk({ type: 'progress', data: { message: '正在处理请求' } })).toEqual({
      type: 'progress',
      message: '正在处理请求',
    });
  });

  it('展示 Step 和 Tool 失败事件', () => {
    expect(executionEventFromChunk({ type: 'step.started', data: { turn_id: 't-1', step_index: 1, status: 'running' } })).toEqual({ type: 'step.started', step_index: 1, status: 'running' });
    expect(executionEventFromChunk({ type: 'tool_started', data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'weather', step: 1, arguments: {} } })).toEqual({ type: 'tool_started', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'weather', step: 1, arguments: {} });
    expect(executionEventFromChunk({ type: 'tool_finished', data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'weather', step: 1, duration_ms: 24, result: { ok: true } } })).toMatchObject({ type: 'tool_finished', tool_call_id: 'c-1', duration_ms: 24 });
    expect(executionEventFromChunk({ type: 'tool.failed', data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'weather', step: 1, duration_ms: 20, error: { code: 'tool_failed' } } })).toMatchObject({ type: 'tool.failed', tool_call_id: 'c-1' });
  });

  it('按 event_id 去重并按 seq 排序', () => {
    const first = { type: 'progress' as const, message: '一', event_id: 'evt-1', seq: 1 };
    const second = { type: 'progress' as const, message: '二', event_id: 'evt-2', seq: 2 };
    expect(appendExecutionEvent([second, first], { ...first, message: '重放' })).toEqual([
      { ...first, message: '重放' },
      second,
    ]);
  });

  it('忽略不会进入执行时间线的内容事件', () => {
    expect(executionEventFromChunk({ type: 'content', data: '最终答案' })).toBeNull();
    expect(executionEventFromChunk({ type: 'done', data: { status: 'completed' } })).toBeNull();
  });

  it('展示语义终态事件，区分完成、受控终止和失败', () => {
    expect(executionEventFromChunk({
      type: 'turn.completed',
      data: { status: 'completed', stop_reason: 'completed', step_count: 2 },
    })).toEqual({ type: 'turn.completed', status: 'completed', stop_reason: 'completed', step_count: 2 });
    expect(executionEventFromChunk({
      type: 'turn.terminated',
      data: { status: 'terminated', reason: 'max_steps', message: '达到最大步数', step_count: 8 },
    })).toEqual({ type: 'turn.terminated', status: 'terminated', reason: 'max_steps', message: '达到最大步数', step_count: 8 });
    expect(executionEventFromChunk({
      type: 'turn.failed',
      data: { status: 'failed', stop_reason: 'tool_error', error: { code: 'tool_failed' } },
    })).toEqual({ type: 'turn.failed', status: 'failed', stop_reason: 'tool_error', error: { code: 'tool_failed' } });
  });

  it('将 Step 开始和完成合并为一个执行节点', () => {
    const items = buildTimelineItems([
      { type: 'step.started', step_index: 1, status: 'running', seq: 1 },
      { type: 'thought', content: '先查询数据', seq: 2 },
      { type: 'step.completed', step_index: 1, status: 'completed', tool_count: 0, seq: 3 },
    ]);

    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'step', stepIndex: 1, started: { status: 'running' }, completed: { status: 'completed' } });
  });

  it('将工具调用、执行和结果合并为一个节点', () => {
    const items = buildTimelineItems([
      { type: 'action', tool_name: 'get_weather', arguments: {}, seq: 1 },
      { type: 'tool_started', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: {}, seq: 2 },
      { type: 'tool_finished', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, duration_ms: 36, result: { ok: true }, seq: 3 },
      { type: 'observation', tool_name: 'get_weather', result: { ok: true }, error: null, seq: 4 },
    ]);

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: 'tool', toolName: 'get_weather', callId: 'c-1', started: { step: 1 }, finished: { duration_ms: 36 }, observation: { tool_name: 'get_weather' } });
  });
});
