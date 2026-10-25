import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { listBusinesses, switchBusiness } from './businesses';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('businesses api', () => {
  it('从 Agent 管理端读取业务清单且不弹全局错误', async () => {
    const payload = {
      active: 'farm',
      total: 1,
      items: [
        {
          name: 'farm',
          display_name: '农场助理',
          description: '农场经营管理助手',
          skill_count: 16,
          error_code: null,
        },
      ],
    };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    const result = await listBusinesses();

    expect(result).toEqual(payload);
    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/agent/admin/businesses',
      expect.objectContaining({ silent: true }),
    );
  });

  it('切换业务时调用 Agent 管理端运行时切换接口', async () => {
    mockedApiClient.put.mockResolvedValueOnce({
      data: { active: 'companion', display_name: '陪伴助手', skill_count: 2 },
    });

    const result = await switchBusiness('companion');

    expect(result.active).toBe('companion');
    expect(mockedApiClient.put).toHaveBeenCalledWith(
      '/agent/admin/businesses/active',
      { name: 'companion' },
      expect.objectContaining({ silent: true }),
    );
  });
});
