import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import AdminLayout from './AdminLayout';
import { platformMenuGroups } from './adminMenu';
import { BusinessContext } from '../businesses/businessContext';
import type { BusinessContextValue } from '../businesses/businessContext';
import { businessViews, menuGroupsFor } from '../businesses/registry';
import type { BusinessView } from '../businesses/registry';

const farmView = businessViews[0];
const menuGroups = menuGroupsFor(farmView);

function groupByLabel(label: string) {
  const group = menuGroups.find((item) => item.label === label);
  if (!group) {
    throw new Error(`未找到菜单分组：${label}`);
  }
  return group.children.map((item) => item.key);
}

const labView: BusinessView = {
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
      children: [
        { key: '/dashboard', icon: 'home', label: '实验仪表盘' },
      ],
    },
  ],
};

function contextValue(overrides: Partial<BusinessContextValue> = {}): BusinessContextValue {
  return {
    views: businessViews,
    selectedName: farmView.name,
    selectedView: farmView,
    runtimeItems: [],
    runtimeActive: null,
    loading: false,
    switchingName: null,
    error: null,
    selectBusiness: async () => true,
    refresh: () => {},
    runtimeFor: () => undefined,
    ...overrides,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

describe('AdminLayout 菜单信息架构', () => {
  it('把农事页面收进单一农场业务分组', () => {
    expect(groupByLabel('农场业务')).toEqual([
      '/dashboard',
      '/crops',
      '/crops/system',
      '/cycles',
      '/logs',
      '/costs',
      '/weather',
      '/memos',
      '/operations',
      '/agent',
    ]);
  });

  it('平台管理收纳业务中心、用户管理与助手设置', () => {
    expect(groupByLabel('平台管理')).toEqual([
      '/businesses',
      '/users',
      '/assistant-settings',
    ]);
    expect(platformMenuGroups.flatMap((group) => group.children)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: '/businesses' }),
        expect.objectContaining({ key: '/users' }),
        expect.objectContaining({ key: '/assistant-settings' }),
      ]),
    );
  });

  it('导航按开发、监控、系统分类且关闭仿真和数据飞轮入口', () => {
    expect(groupByLabel('Agent 开发')).toEqual(['/dev/playground', '/dev/skills', '/dev/prompts']);
    expect(groupByLabel('运行监控')).toEqual(['/dev/traces', '/dev/tokens']);
    expect(groupByLabel('系统管理')).toEqual(['/dev/config']);
    expect(menuGroups.flatMap(group => group.children).some(item => ['/dev/simulation', '/dev/data-flywheel'].includes(item.key))).toBe(false);
  });
});

describe('AdminLayout 业务切换', () => {
  it('品牌区下方显示当前业务切换器', () => {
    render(<MemoryRouter initialEntries={['/dashboard']}><AdminLayout><div>仪表盘</div></AdminLayout></MemoryRouter>);

    expect(screen.getByRole('button', { name: /切换业务，当前 农场业务/ })).toBeInTheDocument();
    expect(screen.getByText('当前业务')).toBeInTheDocument();
  });

  it('预览非当前启用业务时回到业务中心并禁用业务入口', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <BusinessContext.Provider
          value={contextValue({
            views: [farmView, labView],
            selectedName: 'lab',
            selectedView: labView,
            runtimeActive: 'farm',
            runtimeItems: [
              {
                name: 'farm',
                display_name: '农场助理',
                description: '农场经营管理助手',
                skill_count: 16,
                error_code: null,
              },
            ],
          })}
        >
          <AdminLayout><div>业务页面</div></AdminLayout>
          <LocationProbe />
        </BusinessContext.Provider>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('location')).toHaveTextContent('/businesses');
    expect(screen.getByRole('status')).toHaveTextContent('正在预览「实验业务」');
    expect(screen.getByRole('menuitem', { name: '实验业务' })).toHaveAttribute('aria-disabled', 'true');
  });
});

describe('AdminLayout 侧边栏折叠', () => {
  it('从其他页面进入 Playground 时收起导航，手动展开后保持选择', async () => {
    render(<MemoryRouter initialEntries={['/dev/traces']}><AdminLayout><div>工作区</div></AdminLayout></MemoryRouter>);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Agent 开发' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Playground/ }));
    expect(await screen.findByRole('button', { name: 'Playground' })).toHaveAttribute('aria-current', 'page');
    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }));
    expect(await screen.findByRole('menuitem', { name: 'Agent 开发' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('Playground 默认收起全局导航，用户仍可展开访问完整菜单', async () => {
    render(<MemoryRouter initialEntries={['/dev/playground']}><AdminLayout><div>工作区</div></AdminLayout></MemoryRouter>);
    expect(screen.getByRole('button', { name: 'Playground' })).toHaveAttribute('aria-current', 'page');
    expect(screen.queryByRole('menuitem', { name: '平台管理' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }));
    expect(await screen.findByRole('menuitem', { name: '平台管理' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Agent 开发' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('当前 Agent 分组可以收起，页面重渲染不会强制展开', async () => {
    const view = render(<MemoryRouter initialEntries={['/dev/playground']}><AdminLayout><div>工作区</div></AdminLayout></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }));
    const group = await screen.findByRole('menuitem', { name: 'Agent 开发' });
    expect(group).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(group);
    await waitFor(() => expect(group).toHaveAttribute('aria-expanded', 'false'));
    view.rerender(<MemoryRouter initialEntries={['/dev/playground']}><AdminLayout><div>更新工作区</div></AdminLayout></MemoryRouter>);
    expect(group).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(group);
    await waitFor(() => expect(group).toHaveAttribute('aria-expanded', 'true'));
    fireEvent.click(screen.getByRole('menuitem', { name: '平台管理' }));
    await waitFor(() => expect(group).toHaveAttribute('aria-expanded', 'false'));
    expect(screen.getByRole('menuitem', { name: '平台管理' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('通过品牌栏按钮收起和展开侧边栏', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/traces']}>
        <AdminLayout>
          <div>链路追踪内容</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('img', { name: '田掌柜' })).toBeInTheDocument();
    expect(screen.getByText('智能种植运营助手')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出登录' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }));

    await waitFor(() => {
      expect(screen.queryByText('智能种植运营助手')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: '退出登录' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /切换业务/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }));

    await waitFor(() => {
      expect(screen.getByText('智能种植运营助手')).toBeInTheDocument();
    });
  }, 10000);

  it('折叠后直接显示具体导航入口', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/traces']}>
        <AdminLayout>
          <div>链路追踪内容</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '链路追踪' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '数据飞轮' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Token 看板' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Prompt 管理' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '仪表盘' })).not.toBeInTheDocument();
      expect(screen.queryByText('Agent 开发')).not.toBeInTheDocument();
      expect(screen.queryByText('Playground')).not.toBeInTheDocument();
    });
  }, 10000);

  it('折叠后只显示当前分组的导航入口', async () => {
    render(
      <MemoryRouter initialEntries={['/operations']}>
        <AdminLayout>
          <div>业务调试内容</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '业务调试中心' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'AI 助手' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '仪表盘' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '用户管理' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '数据飞轮' })).not.toBeInTheDocument();
    });
  }, 10000);
});
