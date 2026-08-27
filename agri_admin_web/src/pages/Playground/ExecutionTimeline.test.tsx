import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ExecutionTimeline } from './ExecutionTimeline';

describe('ExecutionTimeline', () => {
  it('完成后的 Step 和 Tool 不再显示为持续加载', () => {
    render(
      <ExecutionTimeline
        loading={false}
        events={[
          { type: 'step.started', step_index: 1, status: 'running', seq: 1 },
          { type: 'thought', content: '模型内部判断', seq: 2 },
          { type: 'action', tool_name: 'get_weather', arguments: {}, seq: 3 },
          { type: 'tool_started', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: {}, seq: 4 },
          { type: 'tool_finished', turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, duration_ms: 28, result: { ok: true }, seq: 5 },
          { type: 'observation', tool_name: 'get_weather', result: { ok: true }, error: null, seq: 6 },
          { type: 'step.completed', step_index: 1, status: 'completed', tool_count: 1, seq: 7 },
          { type: 'turn.completed', status: 'completed', seq: 8 },
        ]}
      />,
    );

    expect(screen.getByText('执行过程')).toBeInTheDocument();
    expect(screen.getByText('get_weather')).toBeInTheDocument();
    expect(screen.getAllByText('已完成').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('查看模型思考').closest('details')).not.toHaveAttribute('open');

    fireEvent.click(screen.getByText('查看模型思考'));
    expect(screen.getByText('查看模型思考').closest('details')).toHaveAttribute('open');
  });
});
