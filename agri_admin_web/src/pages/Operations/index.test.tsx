import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AxiosResponse } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { listCycles } from '../../api/cycles';
import { operationsApi } from '../../api/operations';
import { usersApi } from '../../api/users';
import Operations from './index';

vi.mock('../../api/cycles', () => ({
  listCycles: vi.fn(),
  createCycle: vi.fn(),
}));

vi.mock('../../api/crops', () => ({
  createTemplate: vi.fn(),
}));

vi.mock('../../api/costs', () => ({
  createRecord: vi.fn(),
}));

vi.mock('../../api/locations', () => ({
  searchLocations: vi.fn(),
}));

vi.mock('../../api/smartFill', () => ({
  parseSmartFill: vi.fn(),
}));

vi.mock('../../api/operations', () => ({
  operationsApi: {
    listUnits: vi.fn(),
    listWorkers: vi.fn(),
    listWorkOrders: vi.fn(),
    listRecentOperations: vi.fn(),
    listOperationTypes: vi.fn(),
    createUnit: vi.fn(),
    updateUnit: vi.fn(),
    deleteUnit: vi.fn(),
    createWorkOrder: vi.fn(),
    listWorkerSummaries: vi.fn(),
    getUnsettledLaborSummary: vi.fn(),
    listDebts: vi.fn(),
    listCostCategories: vi.fn(),
  },
}));

vi.mock('../../api/users', () => ({
  usersApi: {
    getCurrent: vi.fn(),
    getSettings: vi.fn(),
    updateCurrent: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

const mockedListCycles = vi.mocked(listCycles);

function axiosResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: {} },
  } as AxiosResponse<T>;
}

describe('Operations 页面查询参数', () => {
  beforeAll(() => {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedListCycles.mockResolvedValue({
      items: [
        {
          id: 7,
          name: '夏季西瓜',
          crop_template_name: '西瓜',
          start_date: '2026-07-24',
          status: 'active',
        },
      ],
      total: 1,
    });
    vi.mocked(operationsApi.listUnits).mockResolvedValue(
      axiosResponse([
        {
          id: 11,
          farm_id: 1,
          cycle_id: 7,
          name: '东棚 A 区',
          area_mu: '1.5',
          status: 'active',
        },
      ]),
    );
    vi.mocked(operationsApi.listWorkers).mockResolvedValue(axiosResponse([]));
    vi.mocked(operationsApi.listWorkOrders).mockResolvedValue(axiosResponse({ items: [], total: 0 }));
    vi.mocked(operationsApi.listRecentOperations).mockResolvedValue(axiosResponse([]));
    vi.mocked(operationsApi.listOperationTypes).mockResolvedValue(axiosResponse([]));
    vi.mocked(operationsApi.listWorkerSummaries).mockResolvedValue(axiosResponse({ items: [], total: 0 }));
    vi.mocked(operationsApi.getUnsettledLaborSummary).mockResolvedValue(axiosResponse({}));
    vi.mocked(usersApi.getCurrent).mockResolvedValue(axiosResponse({
      id: 'user-1',
      phone: '13800000000',
      nickname: '管理员',
      role: 'admin',
      status: 'active',
      farm: { id: 1, uid: 'farm-1', name: '管理员农场', location: '苏州' },
    }));
    vi.mocked(usersApi.getSettings).mockResolvedValue(axiosResponse({
      user_id: 'user-1',
      default_city: '苏州市虎丘区',
      default_lat: 31.3,
      default_lon: 120.4,
      assistant_role: 'warm',
    }));
  });

  it('用户设置页只调用当前用户和用户设置 v2 接口', async () => {
    render(
      <MemoryRouter initialEntries={['/operations?tab=settings']}>
        <Operations />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(usersApi.getCurrent).toHaveBeenCalledTimes(1);
      expect(usersApi.getSettings).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByDisplayValue('管理员')).toBeInTheDocument();
  });

  it('从地块入口进入时默认打开种植与作业并按茬口查询种植单元', async () => {
    render(
      <MemoryRouter initialEntries={['/operations?tab=planting&cycle_id=7']}>
        <Operations />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(operationsApi.listUnits).toHaveBeenCalledWith(7);
    });

    expect(screen.getByRole('tab', { name: /种植与作业/ })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText('东棚 A 区')).toBeInTheDocument();
    expect(screen.getByText('1.5 亩')).toBeInTheDocument();
  });

  it('批量生成种植单元草稿后逐条创建', async () => {
    vi.mocked(operationsApi.createUnit).mockResolvedValue(
      axiosResponse({
        id: 21,
        farm_id: 1,
        cycle_id: 7,
        name: '1号棚',
        area_mu: '1.5',
        status: 'active',
      }),
    );

    render(
      <MemoryRouter initialEntries={['/operations?tab=planting&cycle_id=7']}>
        <Operations />
      </MemoryRouter>,
    );

    await screen.findByText('东棚 A 区');
    fireEvent.click(screen.getByRole('button', { name: /新建种植单元/ }));
    fireEvent.click(screen.getByRole('button', { name: '批量创建' }));

    fireEvent.change(screen.getByLabelText('数量'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('默认面积（亩）'), { target: { value: '1.5' } });
    fireEvent.click(screen.getByRole('button', { name: '生成草稿' }));

    expect(await screen.findByDisplayValue('1号棚')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2号棚')).toBeInTheDocument();
    expect(screen.getByDisplayValue('3号棚')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /创建 3 个种植单元/ }));

    await waitFor(() => {
      expect(operationsApi.createUnit).toHaveBeenCalledTimes(3);
    });
    expect(operationsApi.createUnit).toHaveBeenNthCalledWith(1, expect.objectContaining({
      cycle_id: 7,
      name: '1号棚',
      area_mu: 1.5,
      status: 'active',
    }));
    expect(operationsApi.createUnit).toHaveBeenNthCalledWith(3, expect.objectContaining({
      name: '3号棚',
      area_mu: 1.5,
    }));
  });

  it('工人用工表格展示工人默认单价', async () => {
    vi.mocked(operationsApi.listWorkers).mockResolvedValue(
      axiosResponse([
        {
          id: 5,
          farm_id: 1,
          name: '张三',
          phone: '13800000000',
          default_pay_type: 'daily',
          default_unit_price: '100.00',
          status: 'active',
        },
      ]),
    );
    vi.mocked(operationsApi.listWorkerSummaries).mockResolvedValue(
      axiosResponse({
        items: [
          {
            id: 5,
            farm_id: 1,
            name: '张三',
            phone: '13800000000',
            default_pay_type: 'daily',
            default_unit_price: '100.00',
            status: 'active',
            total_payable: '0.00',
            total_paid: '0.00',
            total_unpaid: '0.00',
            entry_count: 0,
            cycle_summaries: [],
          },
        ],
        total: 1,
      }),
    );

    render(
      <MemoryRouter initialEntries={['/operations?tab=labor']}>
        <Operations />
      </MemoryRouter>,
    );

    expect(await screen.findByText('张三')).toBeInTheDocument();
    expect(screen.getAllByText('默认单价').length).toBeGreaterThan(0);
    expect(screen.getByText('¥ 100.00')).toBeInTheDocument();
  });
});
