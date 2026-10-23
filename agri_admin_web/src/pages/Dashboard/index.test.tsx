import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Dashboard from './index';
import * as dashboardApi from '../../api/dashboard';

vi.mock('../../api/dashboard', () => ({
  getSummary: vi.fn(),
}));

const mockedGetSummary = vi.mocked(dashboardApi.getSummary);

beforeEach(() => vi.resetAllMocks());

const summary: dashboardApi.DashboardSummary = {
  farm_id: 1, name: '丰收农场', location: '苏州', today: '2026-10-23',
  active_cycles: [{ cycle_id: 3, crop: '番茄', field_name: '一号棚', area_mu: 12, current_stage: null, start_date: null, status: 'active' }],
  recent_logs_count: 1,
  recent_logs_preview: [{ id: 1, operation_type: '浇水', operation_date: '2026-10-22', note: '完成滴灌' }],
  weather_today: { date: '2026-10-23', min_c: 11, max_c: 19, precip_mm: 0, wind_mps: 3, code: null, desc: '多云' },
  workers_summary: { total: 5, active: 4, unsettled_wages: 500 },
  cost_summary: { month_income: 10000, month_cost: 2000, year_profit: 99000 },
};

describe('Dashboard', () => {
  it('展示真实周期、农事动态与经营数据，并提供详情入口', async () => {
    mockedGetSummary.mockResolvedValue(summary);
    render(<Dashboard />);
    expect(await screen.findByText('番茄')).toBeInTheDocument();
    expect(screen.getByText('阶段待确认')).toBeInTheDocument();
    expect(screen.getByText('番茄').closest('a')).toHaveAttribute('href', '/cycles/3');
    expect(screen.getByText('完成滴灌')).toBeInTheDocument();
    expect(screen.getByText('¥8,000.00')).toBeInTheDocument();
    expect(screen.getByText('多云')).toBeInTheDocument();
  });

  it('刷新失败保留经营快照，再次刷新可恢复', async () => {
    mockedGetSummary.mockResolvedValueOnce(summary).mockRejectedValueOnce(new Error('离线')).mockResolvedValueOnce({ ...summary, name: '更新后的农场' });
    render(<Dashboard />);
    await screen.findByText('丰收农场');
    fireEvent.click(screen.getByRole('button', { name: /刷新/ }));
    expect(await screen.findByText(/DASHBOARD_LOAD_FAILED/)).toBeInTheDocument();
    expect(screen.getByText('丰收农场')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /刷新/ }));
    expect(await screen.findByText('更新后的农场')).toBeInTheDocument();
    expect(screen.queryByText(/DASHBOARD_LOAD_FAILED/)).not.toBeInTheDocument();
  });

  it('首次失败可重试，缺失地块与面积不显示伪造数据', async () => {
    mockedGetSummary.mockRejectedValueOnce(new Error('离线')).mockResolvedValueOnce({ ...summary, active_cycles: [{ ...summary.active_cycles[0], area_mu: null, field_name: null }] });
    render(<Dashboard />);
    fireEvent.click(await screen.findByRole('button', { name: /重\s*试/ }));
    expect(await screen.findByText('地块未设置 · 面积未记录')).toBeInTheDocument();
  });

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
