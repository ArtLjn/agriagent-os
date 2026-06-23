import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listSkills, updateSkillEnabled } from '../../api/admin';
import SkillRegistry from './index';

vi.mock('../../api/admin', () => ({
  listSkills: vi.fn(),
  updateSkillEnabled: vi.fn(),
}));

const mockedListSkills = vi.mocked(listSkills);
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
});
