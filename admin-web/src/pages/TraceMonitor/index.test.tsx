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

  it('兼容 context_builder 旧节点形状并默认折叠原始 JSON', async () => {
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

    const raw = screen.getByText('查看完整节点 JSON').closest('details');
    expect(raw).not.toBeNull();
    expect(raw).not.toHaveAttribute('open');
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

    const outputRaw = screen.getByText('查看完整节点 JSON').closest('details');
    expect(outputRaw).not.toBeNull();
    expect(outputRaw).not.toHaveAttribute('open');
    expect(within(outputRaw!).getByRole('button', { name: /复制 JSON/ })).toBeInTheDocument();
  });

  it('路由决策 payload 渲染为可视化摘要并默认折叠原始 JSON', async () => {
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'routing',
              node_name: 'skill_router',
              duration_ms: 8,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: {
                message: '这个月花了多少钱',
              },
              output_data: {
                frames: [
                  {
                    domain: 'finance',
                    intent: 'query_cost_summary',
                    risk: 'read',
                    capability: 'manage_cost',
                    operation: 'query_summary',
                    operation_hint: 'query_summary',
                    entities: ['cost', 'income', 'balance'],
                    candidate_tools: ['manage_cost'],
                    confidence: 0.84,
                    score: 1,
                    evidence: {
                      domain_scores: { finance: 1 },
                      capability_scores: { manage_cost: 1 },
                      operation_scores: { query_summary: 1 },
                      matched_candidates: [
                        {
                          name: 'manage_cost',
                          domain: 'finance',
                          capability: 'manage_cost',
                          operation: 'query_summary',
                          risk: 'read',
                          enabled: true,
                          legacy_alias: 'get_cost_summary',
                        },
                      ],
                    },
                    missing_fields: [],
                    depends_on: [],
                    requires_confirmation: false,
                  },
                ],
                selected_tools: ['manage_cost'],
                selected_operations: {
                  manage_cost: ['query_summary'],
                },
                context_dependencies: ['farm', 'cost_records', 'cost_categories'],
                fallback: null,
                reason: '按意图候选和 stop-loss policy 选择工具',
                rejected_tools: [],
                policy_violations: [],
                tool_choice: 'auto',
                scores: {
                  domain: { finance: 1 },
                  capability: { manage_cost: 1 },
                  operation: { query_summary: 1 },
                },
                evidence: {
                  selected_candidates: [
                    {
                      name: 'manage_cost',
                      domain: 'finance',
                      capability: 'manage_cost',
                      operation: 'query_summary',
                      risk: 'read',
                    },
                  ],
                },
                plan_draft: {
                  session_id: 'playground-1',
                  farm_id: 2,
                  raw_user_input: '这个月花了多少钱',
                  route_type: 'read_plan',
                  steps: [
                    {
                      step_id: 'query_cost_summary',
                      skill_name: 'manage_cost',
                      params: {},
                      risk: 'read',
                      depends_on: [],
                    },
                  ],
                  selected_tools: ['manage_cost'],
                  source: 'rule_gate',
                  validation: {
                    status: 'valid',
                    safe_route_type: 'read_plan',
                    missing_fields: [],
                    issues: [],
                  },
                },
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

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 skill_router' }));

    expect((await screen.findAllByText('路由决策')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('按意图候选和 stop-loss policy 选择工具')).toBeInTheDocument();
    expect(screen.getByText('命中范围')).toBeInTheDocument();
    expect(screen.getByText('全局评分')).toBeInTheDocument();
    expect(screen.getByText('意图帧')).toBeInTheDocument();
    expect(screen.getByText('已选择候选')).toBeInTheDocument();
    expect(screen.getByText('计划草案')).toBeInTheDocument();
    expect(screen.getByText('query_cost_summary')).toBeInTheDocument();
    expect(screen.getAllByText('这个月花了多少钱').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('manage_cost').length).toBeGreaterThan(1);
    expect(screen.getAllByText('query_summary').length).toBeGreaterThan(1);
    expect(screen.getByText('cost_records')).toBeInTheDocument();

    const raw = screen.getByText('查看完整节点 JSON').closest('details');
    expect(raw).not.toBeNull();
    expect(raw).not.toHaveAttribute('open');
    expect(within(raw!).getByRole('button', { name: /复制 JSON/ })).toBeInTheDocument();
  });

  it('新版 skill_router trace 展示召回路径、候选解释和完整节点 JSON', async () => {
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 1,
          nodes: [
            {
              node_type: 'skill_router',
              node_name: 'skill_router',
              duration_ms: 22,
              status: 'success',
              token_usage: null,
              start_time: '2026-07-28T10:00:00+08:00',
              error_message: null,
              input_data: { message: '查一下成本' },
              output_data: {
                schema_version: 2,
                summary: {
                  selection_path: 'hybrid_retrieval',
                  selection_reason: '按混合召回候选选择工具',
                  selected_routes: ['manage_cost.query_summary'],
                  candidate_count: 13,
                },
                selected: {
                  tools: ['manage_cost'],
                  operations: { manage_cost: ['query_summary'] },
                  tool_choice: 'auto',
                },
                recall: {
                  status: 'used',
                  path: 'bm25_vector_hybrid',
                  retrieval_engine: 'hybrid_operation_retriever',
                  strategy: 'bm25 + quillrag_vector',
                  rag_service_used: true,
                  external_embedding_requested: true,
                  embedding_location: 'quillrag_service',
                  vector_status: 'success',
                  vector_scored_count: 5,
                  scoring_formula: '0.35*bm25 + 0.35*vector',
                },
                candidate_explanations: [
                  {
                    route: 'manage_cost.query_summary',
                    skill: 'manage_cost',
                    operation: 'query_summary',
                    risk: 'read',
                    selected: true,
                    why_selected: '混合召回候选排名靠前并被 policy 选中',
                    scores: {
                      final: 0.82,
                      bm25: 0.71,
                      vector: 0.88,
                    },
                  },
                ],
                plan: {
                  route_type: 'read_plan',
                  steps: [
                    {
                      step_id: 'query_cost',
                      skill_name: 'manage_cost',
                      operation: 'query_summary',
                      risk: 'read',
                    },
                  ],
                  validation: { status: 'valid' },
                },
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

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 skill_router' }));

    expect(await screen.findByText('召回路径')).toBeInTheDocument();
    expect(screen.getByText('hybrid_operation_retriever')).toBeInTheDocument();
    expect(screen.getAllByText(/quillrag_service/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/0\.35\*bm25/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('manage_cost.query_summary').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('混合召回候选排名靠前并被 policy 选中')).toBeInTheDocument();
    expect(screen.getByText('候选评分')).toBeInTheDocument();
    expect(screen.getByText('查看完整节点 JSON').closest('details')).not.toHaveAttribute('open');
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

  it('节点详情长 JSON 字段允许在面板内断行', async () => {
    const longPlanDraft = `plan_draft:${'x'.repeat(240)}`;
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-1',
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              node_type: 'post_process',
              node_name: 'post_tool_result',
              duration_ms: 0,
              status: 'success',
              token_usage: null,
              start_time: null,
              error_message: null,
              input_data: {
                selected_tools: [],
                tool_call_ids: ['call_0b309b594e324610a60021a4'],
                plan_draft: longPlanDraft,
              },
              output_data: null,
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

    fireEvent.click(await screen.findByRole('button', { name: '打开节点 post_tool_result' }));

    const matches = await screen.findAllByText(new RegExp(`plan_draft:.*${'x'.repeat(24)}`));
    const preview = matches.find((element) => element.tagName === 'DIV');
    if (!preview) {
      throw new Error('未找到输入数据预览块');
    }
    expect(preview).toHaveStyle({
      maxWidth: '100%',
      overflowWrap: 'anywhere',
      wordBreak: 'break-word',
    });
  });

  it('展开 trace 时展示请求级根因、指标和恢复建议', async () => {
    mockedListTraceRequests.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          request_id: 'req-blocked',
          session_id: 'sess-1',
          farm_id: 2,
          node_count: 4,
          total_duration_ms: 1234,
          created_at: '2026-07-24T15:00:00+08:00',
          status: 'blocked',
          status_reason: 'pending_plan_contract_blocked',
          error_count: 1,
          root_error: {
            node_id: 101,
            node_type: 'approval',
            node_name: 'pending_plan.contract_validation',
            code: 'pending_plan_contract_blocked',
            message: 'manage_worker 缺少必填字段：name',
            recover: 'ask_user_to_supply_missing_fields_or_rebuild_plan_from_tool_calls',
          },
          metrics: {
            llm_calls: 2,
            tool_calls: 0,
            total_tokens: 4487,
          },
          started_at: '2026-07-24T14:59:58+08:00',
          ended_at: '2026-07-24T15:00:00+08:00',
        },
      ],
    });
    mockedGetTimeline.mockResolvedValueOnce({
      request_id: 'req-blocked',
      summary: {
        request_id: 'req-blocked',
        session_id: 'sess-1',
        farm_id: 2,
        node_count: 4,
        total_duration_ms: 1234,
        created_at: '2026-07-24T15:00:00+08:00',
        status: 'blocked',
        status_reason: 'pending_plan_contract_blocked',
        error_count: 1,
        root_error: {
          node_id: 101,
          node_type: 'approval',
          node_name: 'pending_plan.contract_validation',
          code: 'pending_plan_contract_blocked',
          message: 'manage_worker 缺少必填字段：name',
          recover: 'ask_user_to_supply_missing_fields_or_rebuild_plan_from_tool_calls',
        },
        metrics: {
          llm_calls: 2,
          tool_calls: 0,
          total_tokens: 4487,
        },
        started_at: '2026-07-24T14:59:58+08:00',
        ended_at: '2026-07-24T15:00:00+08:00',
      },
      rounds: [
        {
          round_index: 0,
          nodes: [
            {
              id: 101,
              node_type: 'approval',
              node_name: 'pending_plan.contract_validation',
              duration_ms: 349,
              status: 'blocked',
              token_usage: null,
              start_time: '2026-07-24T15:00:00+08:00',
              end_time: '2026-07-24T15:00:01+08:00',
              error_message: 'manage_worker 缺少必填字段：name',
              error_code: 'pending_plan_contract_blocked',
              recover: 'ask_user_to_supply_missing_fields_or_rebuild_plan_from_tool_calls',
              input_data: null,
              output_data: null,
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dev/traces?request_id=req-blocked']}>
        <TraceMonitor />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Trace 摘要')).toBeInTheDocument();
    expect(screen.getAllByText('blocked').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('pending_plan_contract_blocked').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('manage_worker 缺少必填字段：name')).toBeInTheDocument();
    expect(
      screen.getByText('ask_user_to_supply_missing_fields_or_rebuild_plan_from_tool_calls'),
    ).toBeInTheDocument();
    expect(screen.getByText('total_tokens')).toBeInTheDocument();
    expect(screen.getByText('4,487')).toBeInTheDocument();
  });
});
