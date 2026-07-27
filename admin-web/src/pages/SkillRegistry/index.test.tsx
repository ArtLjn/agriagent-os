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
      message: '这个月花了多少钱',
      top_k: 3,
      candidates: [
        {
          skill: 'manage_cost',
          operation: 'query_summary',
          score: 6.2,
          risk: 'read',
          operation_risk: 'read',
          evidence: {
            tag_hits: ['finance'],
            intent_hits: ['query_summary'],
            example_hits: ['这个月花了多少钱'],
            anti_hits: [],
            identity_hits: [],
            score: 6.2,
          },
        },
      ],
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
        recall_at_1: 0.8,
        recall_at_k: 1,
        operation_recall_at_k: 0.83,
        failures: [
          {
            case_id: 'debt_query_001',
            message: '我有哪些欠款',
            expected: {
              skill: 'manage_cost',
              operation: 'query_debt',
            },
            top_k: [
              {
                skill: 'get_farm_status',
                operation: 'query_status',
              },
              {
                skill: 'manage_cost_categories',
                operation: 'query_categories',
              },
            ],
            scores: {
              get_farm_status: 2.2,
              manage_cost_categories: 2,
            },
          },
        ],
      },
    });

    render(<SkillRegistry />);

    await screen.findByText('manage_cost');
    await user.type(screen.getByLabelText('业务输入'), '这个月花了多少钱');
    await user.click(screen.getByRole('button', { name: '测试召回' }));

    await waitFor(() => {
      expect(mockedPreviewSkillRouteRecall).toHaveBeenCalledWith({
        message: '这个月花了多少钱',
        top_k: 5,
      });
    });
    expect(await screen.findByText('query_summary')).toBeInTheDocument();
    expect(screen.getByText('6.20')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '运行测试集' }));

    await waitFor(() => {
      expect(mockedEvaluateSkillRouteRecallDataset).toHaveBeenCalledWith({ top_k: 5 });
    });
    expect(await screen.findByText('skill_route_cases.json')).toBeInTheDocument();
    expect(screen.getAllByText('100.0%').length).toBeGreaterThan(0);
    expect(screen.getByText('debt_query_001')).toBeInTheDocument();
    expect(screen.getByText('我有哪些欠款')).toBeInTheDocument();
    expect(screen.getByText('manage_cost.query_debt')).toBeInTheDocument();
    expect(screen.getByText('get_farm_status.query_status')).toBeInTheDocument();
  });
});
