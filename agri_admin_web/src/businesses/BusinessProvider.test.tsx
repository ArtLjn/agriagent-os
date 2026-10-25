import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listBusinesses, switchBusiness } from '../api/businesses';
import { authStore } from '../stores/authStore';
import BusinessProvider from './BusinessProvider';
import { useBusinesses } from './businessContext';
import { businessViews } from './registry';
import type { BusinessView } from './registry';

vi.mock('../api/businesses', () => ({
  listBusinesses: vi.fn(),
  switchBusiness: vi.fn(),
}));

const mockedListBusinesses = vi.mocked(listBusinesses);
const mockedSwitchBusiness = vi.mocked(switchBusiness);
const farm = businessViews[0];
const lab: BusinessView = {
  name: 'lab',
  displayName: '实验业务',
  description: '实验业务视角',
  icon: 'experiment',
  homePath: '/dashboard',
  routePrefixes: ['/dashboard'],
  groups: [
    {
      key: 'lab:operations',
      icon: 'experiment',
      label: '实验业务',
      children: [{ key: '/dashboard', icon: 'home', label: '实验仪表盘' }],
    },
  ],
};
const views = [farm, lab];
const runtimeItems = [
  {
    name: 'farm',
    display_name: '农场助理',
    description: '农场经营管理助手',
    skill_count: 16,
    error_code: null,
  },
];

function Probe() {
  const {
    selectedName,
    runtimeActive,
    runtimeItems: items,
    error,
    loading,
    selectBusiness,
  } = useBusinesses();
  return (
    <div>
      <span data-testid="selected">{selectedName ?? 'none'}</span>
      <span data-testid="active">{runtimeActive ?? 'none'}</span>
      <span data-testid="count">{items.length}</span>
      <span data-testid="error">{error ?? ''}</span>
      <span data-testid="loading">{String(loading)}</span>
      <button type="button" onClick={() => selectBusiness('lab')}>switch-lab</button>
    </div>
  );
}

beforeEach(() => {
  authStore.setToken('test-token');
  window.localStorage.removeItem('tianzhanggui-business-view');
  mockedListBusinesses.mockResolvedValue({
    active: 'farm',
    total: 1,
    items: runtimeItems,
  });
  mockedSwitchBusiness.mockResolvedValue({
    active: 'lab',
    display_name: '实验助理',
    skill_count: 1,
  });
});

afterEach(() => {
  authStore.clearToken();
  window.localStorage.removeItem('tianzhanggui-business-view');
  vi.clearAllMocks();
});

describe('BusinessProvider', () => {
  it('默认选择当前启用业务并加载运行时清单', async () => {
    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);

    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('farm'));
    expect(screen.getByTestId('active')).toHaveTextContent('farm');
    expect(screen.getByTestId('count')).toHaveTextContent('1');
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });

  it('恢复本地保存的业务视角', async () => {
    window.localStorage.setItem('tianzhanggui-business-view', 'lab');

    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('farm'));
    expect(screen.getByTestId('selected')).toHaveTextContent('lab');
  });

  it('切换业务时调用运行时切换并持久化选择', async () => {
    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('farm'));
    mockedListBusinesses.mockResolvedValueOnce({
      active: 'lab',
      total: 2,
      items: [
        ...runtimeItems,
        {
          name: 'lab',
          display_name: '实验助理',
          description: '实验业务',
          skill_count: 1,
          error_code: null,
        },
      ],
    });

    fireEvent.click(screen.getByRole('button', { name: 'switch-lab' }));

    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('lab'));
    expect(mockedSwitchBusiness).toHaveBeenCalledWith('lab');
    expect(screen.getByTestId('active')).toHaveTextContent('lab');
    expect(window.localStorage.getItem('tianzhanggui-business-view')).toBe('lab');
  });

  it('本地保存的视角不是当前启用业务时可以再次启用', async () => {
    window.localStorage.setItem('tianzhanggui-business-view', 'lab');

    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('lab'));
    expect(screen.getByTestId('active')).toHaveTextContent('farm');
    mockedListBusinesses.mockResolvedValueOnce({
      active: 'lab',
      total: 2,
      items: [
        ...runtimeItems,
        {
          name: 'lab',
          display_name: '实验助理',
          description: '实验业务',
          skill_count: 1,
          error_code: null,
        },
      ],
    });

    fireEvent.click(screen.getByRole('button', { name: 'switch-lab' }));

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('lab'));
    expect(mockedSwitchBusiness).toHaveBeenCalledWith('lab');
  });

  it('切换失败时保留原业务视角', async () => {
    mockedSwitchBusiness.mockRejectedValueOnce(new Error('network'));

    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('farm'));

    fireEvent.click(screen.getByRole('button', { name: 'switch-lab' }));

    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('业务切换失败'));
    expect(screen.getByTestId('selected')).toHaveTextContent('farm');
    expect(window.localStorage.getItem('tianzhanggui-business-view')).toBeNull();
  });

  it('接口失败时保留注册视图并暴露错误', async () => {
    mockedListBusinesses.mockRejectedValueOnce(new Error('network'));

    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);

    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('业务清单加载失败'));
    expect(screen.getByTestId('selected')).toHaveTextContent('farm');
    expect(screen.getByTestId('active')).toHaveTextContent('none');
    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });

  it('未登录时不请求业务清单', async () => {
    authStore.clearToken();

    render(<BusinessProvider views={views}><Probe /></BusinessProvider>);

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(mockedListBusinesses).not.toHaveBeenCalled();
  });
});
