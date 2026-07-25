import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LlmContextInspector } from './LlmContextInspector';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const snapshot: PlaygroundLlmContextSnapshot = {
  systemPrompt: '系统提示\n<runtime_context>农场状态</runtime_context>',
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
    system_prompt: '系统提示\n<runtime_context>农场状态</runtime_context>',
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
  it('默认只显示折叠的完整 context JSON，展开后展示原始快照', () => {
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

    expect(screen.getByRole('dialog', { name: 'LLM Context JSON' })).toBeInTheDocument();
    const jsonToggle = screen.getByRole('button', { name: /final_llm_context\.json/ });
    expect(jsonToggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.body.textContent).not.toContain('System Prompt');
    expect(document.body.textContent).not.toContain('Prompt Token');
    expect(document.body.textContent).not.toContain('农场状态：夏季大豆播种期');

    fireEvent.click(jsonToggle);

    expect(jsonToggle).toHaveAttribute('aria-expanded', 'true');
    expect(document.body.textContent).toContain('"system_prompt"');
    expect(document.body.textContent).toContain('农场状态：夏季大豆播种期');
  });
});
