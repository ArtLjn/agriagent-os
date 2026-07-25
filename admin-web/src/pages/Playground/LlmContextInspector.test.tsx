import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LlmContextInspector } from './LlmContextInspector';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const snapshot: PlaygroundLlmContextSnapshot = {
  systemPrompt: [
    '李大豆（播种期）',
    '',
    '### farm',
    '农场：管理员农场；位置：苏州市虎丘区',
    '',
    '### ledger',
    '本月花费：250元；近期账务：化肥100元',
    '</runtime_context>',
  ].join('\n'),
  messages: [
    { index: 0, role: 'user', type: 'human', content: '我的农场情况' },
    {
      index: 1,
      role: 'tool',
      type: 'tool',
      content: '农场状态：夏季大豆播种期',
      name: 'get_farm_status',
      tool_call_id: 'call-1',
    },
  ],
  contextBlocks: ['farm', 'ledger'],
  budget: {
    total_tokens: 420,
    max_tokens: 6000,
    actions: ['summarize_old_messages'],
  },
  promptTokens: 420,
  maxTokens: 6000,
  actions: ['summarize_old_messages'],
  truncated: false,
  raw: {
    system_prompt: [
      '李大豆（播种期）',
      '',
      '### farm',
      '农场：管理员农场；位置：苏州市虎丘区',
      '',
      '### ledger',
      '本月花费：250元；近期账务：化肥100元',
      '</runtime_context>',
    ].join('\n'),
    messages: [
      { index: 0, role: 'user', type: 'human', content: '我的农场情况' },
      {
        index: 1,
        role: 'tool',
        type: 'tool',
        content: '农场状态：夏季大豆播种期',
        name: 'get_farm_status',
        tool_call_id: 'call-1',
      },
    ],
    context_blocks: ['farm', 'ledger'],
    budget: {
      total_tokens: 420,
      max_tokens: 6000,
      actions: ['summarize_old_messages'],
    },
  },
};

describe('LlmContextInspector', () => {
  it('主体展示可视化 context 库，底部 JSON 默认折叠且可展开', () => {
    render(
      <LlmContextInspector
        snapshot={snapshot}
        open
        onOpenChange={vi.fn()}
        loading={false}
        hasTimeline
        requestId="req-1"
        nodeCount={9}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole('dialog', { name: 'LLM Context 可观测' })).toBeInTheDocument();
    expect(screen.getAllByText('Context Blocks').length).toBeGreaterThan(0);
    expect(screen.getByText('Runtime Context')).toBeInTheDocument();
    expect(screen.getAllByText('Messages').length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain('农场：管理员农场；位置：苏州市虎丘区');
    expect(document.body.textContent).toContain('农场状态：夏季大豆播种期');

    const jsonToggle = screen.getByRole('button', { name: /final_llm_context\.json/ });
    expect(jsonToggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.body.textContent).not.toContain('"system_prompt"');

    fireEvent.click(jsonToggle);

    expect(jsonToggle).toHaveAttribute('aria-expanded', 'true');
    expect(document.body.textContent).toContain('"system_prompt"');
  });
});
