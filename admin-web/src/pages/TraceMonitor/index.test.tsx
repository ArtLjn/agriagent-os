import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TraceMonitor from './index';
import { getTimeline, listTraceRequests, listTraces } from '../../api/admin';

vi.mock('../../api/admin', () => ({
  deleteTracesBefore: vi.fn(),
  getTimeline: vi.fn(),
  listTraceRequests: vi.fn(),
  listTraces: vi.fn(),
}));

vi.mock('../../components/GanttTimeline', () => ({
  default: ({
    rounds,
    onNodeClick,
  }: {
    rounds: Array<{
      round_index: number;
      nodes: Array<{
        node_type: string;
        node_name: string;
        output_data?: unknown;
        input_data?: unknown;
        duration_ms?: number | null;
        status?: string;
        start_time?: string | null;
        error_message?: string | null;
      }>;
    }>;
    onNodeClick: (roundIndex: number, nodeIndex: number, node: {
      node_type: string;
      node_name: string;
      output_data?: unknown;
      input_data?: unknown;
      duration_ms?: number | null;
      status?: string;
      start_time?: string | null;
      error_message?: string | null;
    }) => void;
  }) => (
    <div>
      timeline loaded
      {rounds.flatMap((round) =>
        round.nodes.map((node, nodeIndex) => (
          <button
            key={`${round.round_index}-${nodeIndex}`}
            type="button"
            onClick={() => onNodeClick(round.round_index, nodeIndex, node)}
          >
            打开节点 {node.node_name}
          </button>
        )),
      )}
    </div>
  ),
}));

const mockedListTraces = vi.mocked(listTraces);
const mockedListTraceRequests = vi.mocked(listTraceRequests);
const mockedGetTimeline = vi.mocked(getTimeline);

describe('TraceMonitor query 初始化', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListTraceRequests.mockResolvedValue({
      total: 1,
      items: [
        {
          request_id: 'req-1',
          session_id: 'sess-1',
          farm_id: 1,
          node_count: 1,
          total_duration_ms: 12,
          created_at: '2026-06-11T10:00:00+08:00',
        },
      ],
    });
    mockedGetTimeline.mockResolvedValue({
      request_id: 'req-1',
      rounds: [],
    });
  });

  it('从 URL query 初始化筛选并自动加载目标 timeline', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1&session_id=sess-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mockedListTraceRequests).toHaveBeenCalledWith({
        limit: 20,
        offset: 0,
        request_id: 'req-1',
        session_id: 'sess-1',
      });
    });
    await waitFor(() => {
      expect(mockedGetTimeline).toHaveBeenCalledWith('req-1');
    });
    expect(screen.getByDisplayValue('req-1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('sess-1')).toBeInTheDocument();
  });

  it('空创建时间显示占位符而不是 1970', async () => {
    mockedListTraceRequests.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          request_id: 'req-empty-time',
          session_id: 'sess-empty-time',
          farm_id: 1,
          node_count: 1,
          total_duration_ms: 12,
          created_at: null,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/req-empty-time/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/1970/)).not.toBeInTheDocument();
    expect(mockedListTraces).not.toHaveBeenCalled();
  });

  it('context_build trace 渲染 Context、block 与 RAG 摘要', async () => {
    const ragBlock = {
      key: 'rag_knowledge',
      source: 'external_rag',
      purpose: 'answer evidence',
      priority: 90,
      token_estimate: 80,
      required: true,
      compressed: false,
      reason: '命中知识库',
      preview: '叶片黄化可能与缺氮或根系受损有关。',
      rag: {
        collection: 'agri_docs',
        mode: 'hybrid',
        actual_mode: 'bm25',
        warning: 'hybrid fallback',
        source_count: 2,
        top_score: 0.87,
        sources: [
          {
            doc_id: 'doc-1',
            chunk_index: 3,
            score: 0.87,
            metadata: {
              title: '水稻病害手册',
              source: 'manual',
            },
          },
        ],
      },
    };

    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'context_build',
              node_name: 'context_bundle',
              duration_ms: 18,
              status: 'success',
              token_usage: null,
              start_time: '2026-06-11T10:00:00+08:00',
              error_message: null,
              input_data: null,
              output_data: {
                token_budget: 512,
                token_estimate: 241,
                policy: {
                  intent: 'diagnose_crop',
                },
                blocks: [ragBlock],
                selected_blocks: [ragBlock],
                sections: [
                  {
                    name: 'Evidence',
                    token_estimate: 120,
                    blocks: [ragBlock],
                  },
                ],
              },
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 context_bundle' }));

    expect(await screen.findByText('Context 摘要')).toBeInTheDocument();
    expect(screen.getByText('token_budget')).toBeInTheDocument();
    expect(screen.getByText('512')).toBeInTheDocument();
    expect(screen.getByText('diagnose_crop')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
    expect(screen.getByText('rag_knowledge')).toBeInTheDocument();
    expect(screen.getByText('external_rag')).toBeInTheDocument();
    expect(screen.getByText('叶片黄化可能与缺氮或根系受损有关。')).toBeInTheDocument();
    expect(screen.getByText('RAG 摘要')).toBeInTheDocument();
    expect(screen.getByText('bm25')).toBeInTheDocument();
    expect(screen.getByText('hybrid fallback')).toBeInTheDocument();
    expect(screen.getByText('source_count')).toBeInTheDocument();
    expect(screen.getByText('top_score')).toBeInTheDocument();
    expect(screen.getByText('水稻病害手册')).toBeInTheDocument();

    const ragSummary = screen.getByText('RAG 摘要').closest('section');
    expect(ragSummary).not.toBeNull();
    expect(within(ragSummary!).getAllByText('doc-1')).toHaveLength(1);
    expect(within(ragSummary!).getAllByText('bm25')).toHaveLength(1);
    expect(within(ragSummary!).getAllByText('水稻病害手册')).toHaveLength(1);
  });

  it('隐藏 Context payload 里的敏感字段值', async () => {
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'context_build',
              node_name: 'context_bundle',
              duration_ms: 18,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: null,
              output_data: {
                token_budget: 128,
                token_estimate: 32,
                policy: {
                  intent: 'debug',
                  api_key: 'fake-sensitive-api-key-value',
                },
                sections: [
                  {
                    name: 'Context',
                    token_estimate: 32,
                    blocks: [
                      {
                        key: 'farm',
                        source: 'runtime',
                        purpose: 'farm state',
                        priority: 10,
                        token_estimate: 32,
                        required: false,
                        compressed: false,
                        reason: 'token=should-hide',
                        preview: 'authorization: should-hide-too',
                        password: 'fake-sensitive-password-value',
                      },
                    ],
                  },
                ],
              },
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 context_bundle' }));

    expect(await screen.findByText('Context 摘要')).toBeInTheDocument();
    expect(screen.getAllByText(/\[REDACTED\]/).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('fake-sensitive-api-key-value')).not.toBeInTheDocument();
    expect(screen.queryByText('should-hide')).not.toBeInTheDocument();
    expect(screen.queryByText('should-hide-too')).not.toBeInTheDocument();
    expect(screen.queryByText('fake-sensitive-password-value')).not.toBeInTheDocument();
  });

  it('兼容 context_builder 旧节点形状并折叠原始 JSON', async () => {
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'prompt_render',
              node_name: 'context_builder',
              duration_ms: 18,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: {
                block_count: 5,
                selected_keys: ['farm', 'cycle', 'user_settings'],
                policy_intent: 'write',
              },
              output_data: {
                token_budget: 900,
                token_estimate: 72,
                selected_blocks: [
                  {
                    key: 'farm',
                    source: 'farm',
                    purpose: '农场状态',
                    priority: 90,
                    token_estimate: 12,
                    required: true,
                    compressed: false,
                    reason: '',
                    preview: '农场：管理员农场；位置：苏州市',
                  },
                ],
                blocks: [
                  {
                    key: 'farm',
                    source: 'farm',
                    purpose: '农场状态',
                    priority: 90,
                    token_estimate: 12,
                    required: true,
                    compressed: false,
                    reason: '',
                    preview: '农场：管理员农场；位置：苏州市',
                  },
                ],
              },
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 context_builder' }));

    expect(await screen.findByText('Context 输入')).toBeInTheDocument();
    expect(screen.getByText('block_count')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('write')).toBeInTheDocument();
    expect(screen.getByText('farm, cycle, user_settings')).toBeInTheDocument();
    expect(screen.getByText('Context 摘要')).toBeInTheDocument();
    expect(screen.getByText('Blocks')).toBeInTheDocument();
    expect(screen.getByText('农场：管理员农场；位置：苏州市')).toBeInTheDocument();

    const inputRaw = screen.getByText('查看原始输入 JSON').closest('details');
    const outputRaw = screen.getByText('查看原始输出 JSON').closest('details');
    expect(inputRaw).not.toBeNull();
    expect(outputRaw).not.toBeNull();
    expect(inputRaw).not.toHaveAttribute('open');
    expect(outputRaw).not.toHaveAttribute('open');
  });

  it('双层编码的 context 输出会自动格式化为摘要', async () => {
    const outputPayload = {
      token_budget: 900,
      token_estimate: 72,
      selected_blocks: [
        {
          key: 'farm',
          source: 'farm',
          purpose: '农场状态',
          priority: 90,
          token_estimate: 12,
          required: true,
          compressed: false,
          reason: '',
          preview: '农场：管理员农场；位置：苏州市',
        },
      ],
      blocks: [
        {
          key: 'farm',
          source: 'farm',
          purpose: '农场状态',
          priority: 90,
          token_estimate: 12,
          required: true,
          compressed: false,
          reason: '',
          preview: '农场：管理员农场；位置：苏州市',
        },
      ],
    };

    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'prompt_render',
              node_name: 'context_builder',
              duration_ms: 18,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: {
                block_count: 5,
                selected_keys: ['farm', 'cycle', 'user_settings'],
                policy_intent: 'agent',
              },
              output_data: JSON.stringify(JSON.stringify(outputPayload)),
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 context_builder' }));

    expect(await screen.findByText('Context 摘要')).toBeInTheDocument();
    expect(screen.getByText('token_budget')).toBeInTheDocument();
    expect(screen.getByText('900')).toBeInTheDocument();
    expect(screen.getByText('Blocks')).toBeInTheDocument();
    expect(screen.getByText('农场：管理员农场；位置：苏州市')).toBeInTheDocument();

    const outputRaw = screen.getByText('查看原始输出 JSON').closest('details');
    expect(outputRaw).not.toBeNull();
    expect(outputRaw).not.toHaveAttribute('open');
  });

  it('普通非 context trace 仍按原始输出展示', async () => {
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'routing',
              node_name: 'router',
              duration_ms: 5,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: null,
              output_data: {
                decision: 'chat',
              },
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-1']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 router' }));

    expect(await screen.findByText(/"decision": "chat"/)).toBeInTheDocument();
    expect(screen.queryByText('Context 摘要')).not.toBeInTheDocument();
  });
});
