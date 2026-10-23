import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getDailyTokenStats,
  getHourlyTokenStats,
  getTokenSummary,
} from '../../api/admin';
import { usersApi } from '../../api/users';
import TokenDashboard from './index';

vi.mock('../../api/admin', () => ({
  getDailyTokenStats: vi.fn(),
  getHourlyTokenStats: vi.fn(),
  getTokenSummary: vi.fn(),
}));

vi.mock('../../api/users', () => ({
  usersApi: {
    getQuota: vi.fn(),
    list: vi.fn(),
  },
}));

const mockedGetDailyTokenStats = vi.mocked(getDailyTokenStats);
const mockedGetHourlyTokenStats = vi.mocked(getHourlyTokenStats);
const mockedGetTokenSummary = vi.mocked(getTokenSummary);
const mockedUsersApi = vi.mocked(usersApi, true);

describe('TokenDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUsersApi.list.mockResolvedValue({
      data: {
        items: [],
        total: 0,
      },
    } as unknown as Awaited<ReturnType<typeof usersApi.list>>);
    mockedUsersApi.getQuota.mockResolvedValue({
      data: {
        monthly_limit: 100_000,
        monthly_remaining: 100_000,
        monthly_start: '2026-07-01',
        monthly_end: '2026-07-31',
        monthly_usage: 0,
        weekly_limit: 25_000,
        weekly_remaining: 25_000,
        weekly_start: '2026-07-06',
        weekly_end: '2026-07-12',
        weekly_usage: 0,
        status: 'ok',
      },
    } as unknown as Awaited<ReturnType<typeof usersApi.getQuota>>);
  });

  it('日统计接口失败时仍展示已返回的小时趋势图', async () => {
    mockedGetTokenSummary.mockResolvedValue({
      days: 7,
      total_requests: 2,
      total_tokens: 320,
      by_model: {
        'qwen3.6-flash:chat': {
          model: 'qwen3.6-flash',
          call_type: 'chat',
          prompt_tokens: 260,
          completion_tokens: 60,
          total_tokens: 320,
          request_count: 2,
        },
      },
    });
    mockedGetDailyTokenStats.mockRejectedValue(new Error('daily stats timeout'));
    mockedGetHourlyTokenStats.mockResolvedValue({
      start_date: '2026-07-04',
      end_date: '2026-07-10',
      hours: ['09'],
      total_tokens: 320,
      total_requests: 2,
      items: [
        {
          date: '2026-07-10',
          hour: '09',
          farm_id: 2,
          model: 'qwen3.6-flash',
          prompt_tokens: 260,
          completion_tokens: 60,
          total_tokens: 320,
          request_count: 2,
        },
      ],
    });

    render(<TokenDashboard />);

    expect(await screen.findByRole('img', { name: 'Token 用量和请求数时间趋势' })).toBeInTheDocument();
    expect(screen.queryByText('今日暂无可用于趋势图的真实 Token trace')).not.toBeInTheDocument();
  });
});

 it('个人周月配额使用 Agent 实际消耗而非旧接口零用量', async () => {
  mockedUsersApi.list.mockResolvedValue({ data: { items: [{ id: 'u', nickname: '测试用户', phone: '123' }], total: 1 } } as unknown as Awaited<ReturnType<typeof usersApi.list>>);
  mockedUsersApi.getQuota.mockResolvedValue({ data: { monthly_limit: 1000, weekly_limit: 1000, monthly_usage: 0, weekly_usage: 0 } } as unknown as Awaited<ReturnType<typeof usersApi.getQuota>>);
  mockedGetTokenSummary.mockResolvedValue({ days: 7, by_model: {}, total_tokens: 600, total_requests: 1 });
  mockedGetDailyTokenStats.mockResolvedValue({ date: '2026-10-23', items: [] });
  mockedGetHourlyTokenStats.mockResolvedValue({ start_date: '2026-10-01', end_date: '2026-10-23', hours: [], items: [], total_tokens: 600, total_requests: 1 });
  render(<TokenDashboard />);
  await waitFor(() => expect(mockedUsersApi.list).toHaveBeenCalled());
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0]);
  fireEvent.click(await screen.findByText('测试用户 / 123'));
  await waitFor(() => expect(screen.getAllByText('600 / 1.0K')).toHaveLength(2));
  expect(mockedGetHourlyTokenStats).toHaveBeenCalledWith(expect.objectContaining({ user_id: 'u', start_date: expect.stringMatching(/-01$/) }));
});
