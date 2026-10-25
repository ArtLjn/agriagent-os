import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { BusinessContext } from '../../businesses/businessContext';
import type { BusinessContextValue } from '../../businesses/businessContext';
import { businessViews } from '../../businesses/registry';
import type { BusinessView } from '../../businesses/registry';
import type { BusinessRuntimeItem } from '../../api/businesses';
import BusinessCenter from '.';

const farmView = businessViews[0];

function makeView(name: string, displayName: string): BusinessView {
  return {
    name,
    displayName,
    description: `${displayName}描述`,
    icon: 'experiment',
    homePath: '/dashboard',
    routePrefixes: ['/dashboard'],
    groups: [
      {
        key: `${name}:operations`,
        icon: 'experiment',
        label: displayName,
        children: [{ key: '/dashboard', icon: 'home', label: `${displayName}入口` }],
      },
    ],
  };
}

const labView = makeView('lab', '实验业务');
const brokenView = makeView('broken', '异常业务');
const opsView = makeView('ops', '运维业务');

function runtime(
  name: string,
  displayName: string,
  errorCode: string | null = null,
): BusinessRuntimeItem {
  return {
    name,
    display_name: displayName,
    description: `${displayName}描述`,
    skill_count: 3,
    error_code: errorCode,
  };
}

const runtimeItems = [
  runtime('farm', '农场助理'),
  runtime('lab', '实验助理'),
  runtime('broken', '异常助理', 'plugin_manifest_unknown_fields'),
  runtime('external', '外部助理'),
];

const views = [farmView, labView, brokenView, opsView];

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

function renderCenter(overrides: Partial<BusinessContextValue> = {}) {
  const selectBusiness = vi.fn().mockResolvedValue(true);
  const refresh = vi.fn();
  const value: BusinessContextValue = {
    views,
    selectedName: 'farm',
    selectedView: farmView,
    runtimeItems,
    runtimeActive: 'farm',
    loading: false,
    switchingName: null,
    error: null,
    selectBusiness,
    refresh,
    runtimeFor: (name) => runtimeItems.find((item) => item.name === name),
    ...overrides,
  };
  render(
    <MemoryRouter>
      <BusinessContext.Provider value={value}>
        <BusinessCenter />
        <LocationProbe />
      </BusinessContext.Provider>
    </MemoryRouter>,
  );
  return { selectBusiness, refresh };
}

describe('BusinessCenter', () => {
  it('展示当前启用、未启用、清单异常、视图未接入和状态未知', () => {
    renderCenter();

    expect(within(screen.getByTestId('business-card-farm')).getByText('当前启用')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-lab')).getByText('已安装未启用')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-broken')).getByText('清单异常')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-external')).getByText('已安装未启用')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-external')).getByText('视图未接入')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-external')).getByText('管理端视图未接入')).toBeInTheDocument();
    expect(within(screen.getByTestId('business-card-ops')).getByText('状态未知')).toBeInTheDocument();
  });

  it('允许切换已安装但未启用的业务视角', () => {
    const { selectBusiness } = renderCenter();

    fireEvent.click(
      within(screen.getByTestId('business-card-lab')).getByRole('button', { name: '切换业务' }),
    );

    expect(selectBusiness).toHaveBeenCalledWith('lab');
  });

  it('当前启用业务可进入，非启用与异常业务禁用进入', () => {
    renderCenter();

    expect(
      within(screen.getByTestId('business-card-farm')).getByRole('button', { name: '进入业务' }),
    ).toBeEnabled();
    expect(
      within(screen.getByTestId('business-card-lab')).getByRole('button', { name: '进入业务' }),
    ).toBeDisabled();
    expect(
      within(screen.getByTestId('business-card-broken')).getByRole('button', { name: '进入业务' }),
    ).toBeDisabled();
  });

  it('从当前视角概览进入业务首页', () => {
    renderCenter();

    const hero = screen.getByLabelText('当前业务视角');
    fireEvent.click(within(hero).getByRole('button', { name: /进入业务/ }));

    expect(screen.getByTestId('location')).toHaveTextContent('/dashboard');
  });

  it('清单失败时可重试', () => {
    const { refresh } = renderCenter({
      runtimeItems: [],
      runtimeActive: null,
      error: '业务清单加载失败，请稍后重试',
    });

    expect(screen.getAllByText('业务清单加载失败，请稍后重试').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }));

    expect(refresh).toHaveBeenCalled();
  });
});
