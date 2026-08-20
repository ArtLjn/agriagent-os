import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LlmContextInspector } from './LlmContextInspector';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const snapshot: PlaygroundLlmContextSnapshot = {
  schemaVersion: null,
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
  contextBlockDetails: [],
  runtimeSections: [],
  contextPack: null,
  budget: {
    total_tokens: 420,
    max_tokens: 6000,
    actions: ['summarize_old_messages'],
  },
  compression: null,
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

const v2Snapshot = {
  schemaVersion: 2,
  systemPrompt: '系统提示',
  messages: [
    {
      index: 0,
      role: 'user',
      type: 'human',
      content: '继续任务',
      contentPreview: '继续任务',
      compressed: true,
    },
    {
      index: 1,
      role: 'tool',
      type: 'tool',
      content: '查询完成',
      name: 'get_task_state',
      tool_call_id: 'call-1',
      status: 'success',
    },
  ],
  contextBlocks: ['farm', 'active_task_state'],
  contextBlockDetails: [
    {
      key: 'active_task_state',
      category: 'task',
      source: 'task_state',
      decision: 'selected',
      compressed: false,
      dropped: false,
      priority: 85,
      required: false,
      tokenEstimate: 120,
      contentPreview: '目标：补齐巡田计划',
      content: '目标：补齐巡田计划\n状态：进行中',
      reason: '',
    },
  ],
  runtimeSections: [
    {
      name: 'Task',
      tokenEstimate: 180,
      blocks: [
        {
          key: 'active_task_state',
          category: 'task',
          source: 'task_state',
          decision: 'selected',
          compressed: false,
          dropped: false,
          priority: 85,
          required: false,
          tokenEstimate: 120,
          contentPreview: '目标：补齐巡田计划',
          content: '目标：补齐巡田计划\n状态：进行中',
          reason: '',
        },
      ],
    },
  ],
  contextPack: {
    recentMessageIds: [1235, 1236],
    summaryVersion: 4,
    summaryHash: 'sha256:abc',
    tokenEstimate: 88,
    selectedBlocks: ['conversation_summary', 'recent_messages'],
    compressedBlocks: [],
    droppedBlocks: [],
    compactionReason: '',
  },
  budget: {
    total_tokens: 3315,
    max_tokens: 6000,
    actions: ['compact_tool_results'],
  },
  compression: {
    contextCompressedCount: 1,
    contextDroppedCount: 0,
    messageCompressedCount: 2,
    toolResultCompressedCount: 1,
    events: [],
  },
  promptTokens: 3315,
  maxTokens: 6000,
  actions: ['compact_tool_results'],
  truncated: false,
  raw: {
    schema_version: 2,
  },
} as unknown as PlaygroundLlmContextSnapshot;

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

  it('展示 schema v2 的上下文分类、压缩状态、Runtime Context 和工具消息元数据', () => {
    render(
      <LlmContextInspector
        snapshot={v2Snapshot}
        open
        onOpenChange={vi.fn()}
        loading={false}
        hasTimeline
        requestId="req-v2"
        nodeCount={9}
        onRefresh={vi.fn()}
      />,
    );

    expect(document.body.textContent).toContain('task');
    expect(document.body.textContent).toContain('active_task_state');
    expect(document.body.textContent).toContain('selected');
    expect(document.body.textContent).toContain('目标：补齐巡田计划');
    expect(document.body.textContent).toContain('状态：进行中');
    expect(document.body.textContent).toContain('已压缩');
    expect(document.body.textContent).toContain('call-1');
    expect(document.body.textContent).toContain('get_task_state');
    expect(document.body.textContent).toContain('success');
    expect(document.body.textContent).toContain('ContextPack');
    expect(document.body.textContent).toContain('summary: v4');
    expect(document.body.textContent).toContain('#1235');
    expect(document.body.textContent).toContain('#1236');
  });

  it('当前 request 没有 LLM 快照时展示最近一次 LLM Context 来源', () => {
    render(
      <LlmContextInspector
        snapshot={snapshot}
        open
        onOpenChange={vi.fn()}
        loading={false}
        hasTimeline
        requestId="0830521c"
        snapshotRequestId="badb9573"
        nodeCount={4}
        onRefresh={vi.fn()}
      />,
    );

    expect(document.body.textContent).toContain(
      '当前 request 0830521c 未进入 LLM，展示最近一次 LLM Context：badb9573',
    );
  });
});
