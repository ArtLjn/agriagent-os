import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import GanttTimeline from './index';

describe('GanttTimeline', () => {
  it('展开后的轮次汇总条按节点类型分段展示', () => {
    render(
      <GanttTimeline
        rounds={[
          {
            round_index: 1,
            nodes: [
              {
                node_type: 'prompt_budget',
                node_name: 'final_prompt',
                duration_ms: 100,
                status: 'success',
                start_time: '2026-07-29T09:00:00+08:00',
              },
              {
                node_type: 'llm_call',
                node_name: 'qwen3.6-flash',
                duration_ms: 300,
                status: 'success',
                start_time: '2026-07-29T09:00:01+08:00',
              },
            ],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText('执行阶段 1'));

    expect(screen.getByLabelText('轮次汇总 final_prompt 100ms')).toHaveStyle({
      background: '#1890ff',
    });
    expect(screen.getByLabelText('轮次汇总 qwen3.6-flash 300ms')).toHaveStyle({
      background: '#722ed1',
    });
  });

  it('节点行时间条与轮次汇总使用同一时间轴定位', () => {
    render(
      <GanttTimeline
        rounds={[
          {
            round_index: 1,
            nodes: [
              {
                node_type: 'routing',
                node_name: 'skill_router',
                duration_ms: 100,
                status: 'success',
                start_time: '2026-07-29T09:00:00+08:00',
              },
              {
                node_type: 'llm_call',
                node_name: 'qwen3.6-flash',
                duration_ms: 300,
                status: 'success',
                start_time: '2026-07-29T09:00:01+08:00',
              },
            ],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText('执行阶段 1'));

    expect(screen.getByLabelText('节点时间 skill_router 100ms')).toHaveStyle({
      left: '0%',
      width: '25%',
    });
    expect(screen.getByLabelText('节点时间 qwen3.6-flash 300ms')).toHaveStyle({
      left: '25%',
      width: '75%',
    });
  });

  it('时间段由轨道统一裁切圆角，避免短段衔接处出现独立胶囊感', () => {
    render(
      <GanttTimeline
        rounds={[
          {
            round_index: 1,
            nodes: [
              {
                node_type: 'routing',
                node_name: 'skill_router',
                duration_ms: 100,
                status: 'success',
                start_time: '2026-07-29T09:00:00+08:00',
              },
              {
                node_type: 'prompt_render',
                node_name: 'system_prompt',
                duration_ms: 1,
                status: 'success',
                start_time: '2026-07-29T09:00:01+08:00',
              },
            ],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText('执行阶段 1'));

    expect(screen.getByLabelText('轮次汇总 skill_router 100ms')).toHaveStyle({
      borderRadius: '0px',
    });
    expect(screen.getByLabelText('轮次汇总 system_prompt 1ms')).toHaveStyle({
      borderRadius: '0px',
    });
  });
});
