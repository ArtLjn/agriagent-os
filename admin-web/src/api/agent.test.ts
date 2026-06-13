import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { listAppSkills, refreshDailyAdvice } from './agent';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('agent api', () => {
  it('读取 App 端技能列表接口', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            key: 'create_cost_record',
            title: '智能记账',
            description: '一句话生成账本记录',
            category: '记录',
            icon: 'receipt-yuan',
            icon_color: 'green',
            recommended: true,
            enabled: true,
          },
        ],
        total: 1,
      },
    });

    const result = await listAppSkills();

    expect(mockedApiClient.get).toHaveBeenCalledWith('/agent/skills');
    expect(result.items[0].title).toBe('智能记账');
  });

  it('强制刷新每日建议接口', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        cycle_id: 7,
        advice: '重新生成的建议',
        created_at: '2026-06-13T10:00:00',
      },
    });

    const result = await refreshDailyAdvice(7);

    expect(mockedApiClient.post).toHaveBeenCalledWith('/agent/daily/refresh', null, {
      params: { cycle_id: 7 },
    });
    expect(result.advice).toBe('重新生成的建议');
  });
});
