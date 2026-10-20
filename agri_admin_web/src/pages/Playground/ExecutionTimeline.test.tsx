import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExecutionTimeline } from './ExecutionTimeline';
import type { ExecutionEvent } from './executionEvents';

const completedEvents: ExecutionEvent[] = [
  { type: 'step.started', step_index: 1, status: 'running', seq: 1 },
  { type: 'context_usage', percent: 42, used: 13700, total: 32000, level: 'green', seq: 2 },
  { type: 'thought', content: '模型内部判断', seq: 3 },
  { type: 'tool_call_delta', tool_call_id: 'c-1', name: 'get_weather', index: 0, arguments_delta: '{}', seq: 4 },
  { type: 'action', tool_name: 'get_weather', arguments: { city: '天津' }, seq: 5 },
  { type: 'tool_started', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: { city: '天津' }, seq: 6 },
  { type: 'tool_finished', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, duration_ms: 1741, result: { weather: '晴' }, seq: 7 },
  { type: 'observation', tool_name: 'get_weather', result: { weather: '晴' }, error: null, seq: 8 },
  { type: 'step.completed', step_index: 1, status: 'completed', tool_count: 1, seq: 9 },
  { type: 'turn.completed', status: 'completed', seq: 10 },
];

describe('ExecutionTimeline', () => {
  it('内联展示合并后的工具步骤，调试噪音不占用对话空间', () => {
    const { container } = render(<ExecutionTimeline loading={false} events={completedEvents} />);
    expect(screen.getByLabelText('执行过程')).toBeInTheDocument();
    expect(screen.getByText('get_weather')).toBeInTheDocument();
    expect(screen.getByText('1 个步骤 · 1 次工具调用')).toBeInTheDocument();
    expect(screen.getByText('第 1 步')).toBeInTheDocument();
    expect(screen.getByText('1 次调用')).toBeInTheDocument();
    expect(screen.getByText('查看参数与结果')).toBeInTheDocument();
    expect(screen.getByText('1.7s')).toBeInTheDocument();
    expect(screen.queryByText('上下文')).not.toBeInTheDocument();
    expect(screen.queryByText('查看模型思考')).not.toBeInTheDocument();
    expect(container.querySelector('.anticon-spin')).not.toBeInTheDocument();
  });

  it('无工具调用的步骤也出现在链路中，步骤数与可见行一致', () => {
    render(<ExecutionTimeline loading={false} events={[
      ...completedEvents.slice(0, 9),
      { type: 'step.started', step_index: 2, status: 'running' },
      { type: 'step.completed', step_index: 2, status: 'completed', tool_count: 0 },
      completedEvents[9],
    ]} />);
    expect(screen.getByText('2 个步骤 · 1 次工具调用')).toBeInTheDocument();
    expect(screen.getByText('第 2 步')).toBeInTheDocument();
    expect(screen.getByText('无工具调用')).toBeInTheDocument();
  });

  it('从流式执行更新到完成状态', () => {
    const { rerender, container } = render(<ExecutionTimeline loading events={completedEvents.slice(0, 6)} />);
    expect(screen.getByRole('status')).toHaveTextContent('正在分析问题并执行任务');
    expect(container.querySelector('.anticon-spin')).toBeInTheDocument();
    rerender(<ExecutionTimeline loading={false} events={completedEvents} />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(container.querySelector('.anticon-spin')).not.toBeInTheDocument();
  });

  it('终止时不将未结束工具误显示为成功或持续执行', () => {
    const { container } = render(<ExecutionTimeline loading events={[
      ...completedEvents.slice(0, 6),
      { type: 'turn.terminated', status: 'terminated', reason: 'max_steps', message: '达到最大步数' },
    ]} />);
    expect(screen.getByText('已终止')).toBeInTheDocument();
    expect(screen.getByText('未完成')).toBeInTheDocument();
    expect(screen.getByText(/达到最大步数/)).toBeInTheDocument();
    expect(container.querySelector('.anticon-spin')).not.toBeInTheDocument();
  });

  it('等待审批时保留提示，执行错误保留业务错误码', () => {
    const { rerender, container } = render(<ExecutionTimeline loading events={[
      { type: 'approval_required', tool_name: 'create_cycle', arguments: { crop: '西瓜' } },
    ]} />);
    expect(screen.getByText('等待确认')).toBeInTheDocument();
    expect(screen.getByText('查看待确认参数')).toBeInTheDocument();
    expect(container.querySelector('.anticon-spin')).not.toBeInTheDocument();
    rerender(<ExecutionTimeline loading={false} events={[{ type: 'error', code: 'TOOL_TIMEOUT', message: '查询超时' }]} />);
    expect(screen.getByText('执行失败')).toBeInTheDocument();
    expect(screen.getByText(/TOOL_TIMEOUT · 查询超时/)).toBeInTheDocument();
  });

  it('空事件不占用对话空间', () => {
    const { container } = render(<ExecutionTimeline loading={false} events={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
