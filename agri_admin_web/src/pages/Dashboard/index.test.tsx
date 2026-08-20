import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Dashboard from './index';
import * as dashboardApi from '../../api/dashboard';

vi.mock('../../api/dashboard', () => ({
  getSummary: vi.fn(),
}));

const mockedGetSummary = vi.mocked(dashboardApi.getSummary);

describe('Dashboard', () => {
  it('使用 agri_backend_v2 农场仪表板接口渲染概览，而不是请求不存在的管理员统计接口', async () => {
    mockedGetSummary.mockResolvedValueOnce({
      farm_id: 1,
      name: '管理员农场的农场',
      location: '苏州',
      today: '2026-08-16',
      active_cycles: [],
      recent_logs_count: 0,
      recent_logs_preview: [],
      weather_today: null,
      workers_summary: { total: 0, active: 0, unsettled_wages: 0 },
      cost_summary: { month_income: 0, month_cost: 0, year_profit: 0 },
    });

    render(<Dashboard />);

    await waitFor(() => expect(screen.getByText('农场仪表板')).toBeInTheDocument());
    expect(mockedGetSummary).toHaveBeenCalledOnce();
    expect(screen.getByText('管理员农场的农场')).toBeInTheDocument();
    expect(screen.getByText('暂无天气数据')).toBeInTheDocument();
  });
});
