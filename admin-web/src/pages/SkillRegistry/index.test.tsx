import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  evaluateSkillRouteRecallDataset,
  listSkills,
  previewSkillRouteRecall,
  updateSkillEnabled,
} from '../../api/admin';
import SkillRegistry from './index';

vi.mock('../../api/admin', () => ({
  evaluateSkillRouteRecallDataset: vi.fn(),
  listSkills: vi.fn(),
  previewSkillRouteRecall: vi.fn(),
  updateSkillEnabled: vi.fn(),
}));

const mockedEvaluateSkillRouteRecallDataset = vi.mocked(evaluateSkillRouteRecallDataset);
const mockedListSkills = vi.mocked(listSkills);
const mockedPreviewSkillRouteRecall = vi.mocked(previewSkillRouteRecall);
const mockedUpdateSkillEnabled = vi.mocked(updateSkillEnabled);

describe('SkillRegistry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('展示 Skill 数量统计并支持禁用 Skill', async () => {
    const user = userEvent.setup();
    mockedListSkills.mockResolvedValueOnce({
      total: 2,
      summary: {
        total: 2,
        enabled: 1,
        disabled: 1,
        admin_only: 0,
      },
      items: [
        {
          name: 'get_cost_summary',
          description: '查询成本汇总',
          parameters_schema: { type: 'object' },
          status: 'active',
          metadata: {
            enabled: true,
            permission_level: 'read',
            risk_level: 'low',
            disabled_reason: null,
          },
        },
        {
          name: 'web_search',
          description: '联网搜索',
          parameters_schema: { type: 'object' },
          status: 'disabled',
          metadata: {
            enabled: false,
            permission_level: 'external_network',
            risk_level: 'low',
            disabled_reason: '搜索服务不稳定',
          },
        },
      ],
    });
    mockedUpdateSkillEnabled.mockResolvedValueOnce({
      name: 'get_cost_summary',
      description: '查询成本汇总',
      parameters_schema: { type: 'object' },
      status: 'disabled',
      metadata: {
        enabled: false,
        permission_level: 'read',
        risk_level: 'low',
        disabled_reason: '管理员手动禁用',
      },
    });

    render(<SkillRegistry />);

    expect(await screen.findByText('全部 Skill')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('已启用')).toBeInTheDocument();
    expect(screen.getByText('已禁用')).toBeInTheDocument();
    expect(screen.getByText('搜索服务不稳定')).toBeInTheDocument();

    await user.click(screen.getByRole('switch', { name: '禁用 get_cost_summary' }));

    await waitFor(() => {
      expect(mockedUpdateSkillEnabled).toHaveBeenCalledWith('get_cost_summary', {
        enabled: false,
        disabled_reason: '管理员手动禁用',
      });
    });
    expect(await screen.findByText('管理员手动禁用')).toBeInTheDocument();
  });

  it('支持单条业务输入召回和 JSON 测试集批量评测', async () => {
    const user = userEvent.setup();
    mockedListSkills.mockResolvedValueOnce({
      total: 1,
      summary: {
        total: 1,
        enabled: 1,
        disabled: 0,
        admin_only: 0,
      },
      items: [
        {
          name: 'manage_cost',
          description: '管理农场账务',
          parameters_schema: { type: 'object' },
          status: 'active',
          metadata: {
            enabled: true,
            permission_level: 'read',
            risk_level: 'low',
            disabled_reason: null,
          },
        },
      ],
    });
    mockedPreviewSkillRouteRecall.mockResolvedValueOnce({
      message: '我有哪些欠款',
      top_k: 5,
      recall_mode: 'hybrid_vector',
      vector_index_enabled: true,
      recall: {
        candidate_scope: 'read',
        quillrag_retrieve_used: true,
        external_embedding_requested: true,
        embedding_location: 'quillrag_service',
      },
      top_candidates: [],
      candidates: [
        {
          skill: 'manage_cost',
          operation: 'query_debt',
          score: 0.63,
          risk: 'read',
          operation_risk: 'read',
          evidence: {
            sources: ['lexical', 'bm25', 'vector'],
            bm25: 1,
            vector: 0.8,
            lexical: 0.9,
            lexical_hits: ['欠款'],
            low_signal_hits: ['有哪些'],
            score: 0.63,
          },
        },
      ],
      skill_router: {
        schema_version: 2,
        summary: {
          selection_path: 'hybrid_retrieval',
          selected_routes: ['manage_cost.query_debt'],
        },
        selected: {
          tools: ['manage_cost'],
          operations: {
            manage_cost: ['query_debt'],
          },
        },
        recall: {
          status: 'used',
          candidate_scope: 'read',
          vector_search_used: true,
        },
      },
    });
    mockedEvaluateSkillRouteRecallDataset.mockResolvedValueOnce({
      dataset: {
        path: 'skill_route_cases.json',
        format: 'json',
        total: 6,
      },
      top_k: 5,
      report: {
        total: 6,
        recall_at_1: 1,
        recall_at_k: 1,
        operation_recall_at_k: 1,
        failures: [],
      },
    });

    render(<SkillRegistry />);

    await screen.findByText('manage_cost');
    await user.type(screen.getByLabelText('业务输入'), '我有哪些欠款');
    await user.click(screen.getByRole('button', { name: '测试召回' }));

    await waitFor(() => {
      expect(mockedPreviewSkillRouteRecall).toHaveBeenCalledWith({
        message: '我有哪些欠款',
        top_k: 5,
      });
    });
    expect(await screen.findByText('query_debt')).toBeInTheDocument();
    expect(screen.getByText('混合向量召回')).toBeInTheDocument();
    expect(screen.getByText('向量索引已启用')).toBeInTheDocument();
    expect(screen.getByText('RAG 已调用')).toBeInTheDocument();
    expect(screen.getByText('Embedding: quillrag_service')).toBeInTheDocument();
    expect(screen.getByText('Scope: read')).toBeInTheDocument();
    expect(screen.getByText('hybrid 0.630')).toBeInTheDocument();
    expect(screen.getByText('lexical')).toBeInTheDocument();
    expect(screen.getByText('bm25')).toBeInTheDocument();
    expect(screen.getByText('vector')).toBeInTheDocument();
    expect(screen.getByText('lexical: 0.90')).toBeInTheDocument();
    expect(screen.getByLabelText('skill_router trace JSON')).toHaveTextContent(
      '"schema_version"'
    );
    expect(screen.getByLabelText('skill_router trace JSON')).toHaveTextContent(
      '"manage_cost"'
    );

    await user.click(screen.getByRole('button', { name: '运行测试集' }));

    await waitFor(() => {
      expect(mockedEvaluateSkillRouteRecallDataset).toHaveBeenCalledWith({ top_k: 5 });
    });
    expect(await screen.findByText('skill_route_cases.json')).toBeInTheDocument();
    expect(screen.getAllByText('100.0%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    expect(screen.queryByText('debt_query_001')).not.toBeInTheDocument();
  });
});
