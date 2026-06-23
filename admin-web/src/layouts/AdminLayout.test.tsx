import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import AdminLayout from './AdminLayout';
import { menuGroups } from './adminMenu';

function groupByLabel(label: string) {
  const group = menuGroups.find((item) => item.label === label);
  if (!group) {
    throw new Error(`未找到菜单分组：${label}`);
  }
  return group.children.map((item) => item.key);
}

describe('AdminLayout 菜单信息架构', () => {
  it('业务运营只放平台运营资产入口', () => {
    expect(groupByLabel('业务运营')).toEqual([
      '/dashboard',
      '/users',
      '/crops/system',
    ]);
  });

  it('业务调试归纳管理员个人 app 账号的业务数据视图', () => {
    expect(groupByLabel('业务调试')).toEqual([
      '/operations',
      '/crops',
      '/cycles',
      '/logs',
      '/costs',
      '/weather',
      '/agent',
    ]);
  });
});

describe('AdminLayout 侧边栏折叠', () => {
  it('通过品牌栏按钮收起和展开侧边栏', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/data-flywheel']}>
        <AdminLayout>
          <div>数据飞轮内容</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('img', { name: '田掌柜' })).toBeInTheDocument();
    expect(screen.getByText('智能种植运营助手')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }));

    await waitFor(() => {
      expect(screen.queryByText('智能种植运营助手')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }));

    await waitFor(() => {
      expect(screen.getByText('智能种植运营助手')).toBeInTheDocument();
    });
  }, 10000);

  it('折叠后直接显示具体导航入口', async () => {
    render(
      <MemoryRouter initialEntries={['/dev/data-flywheel']}>
        <AdminLayout>
          <div>数据飞轮内容</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }));

    await waitFor(() => {
      expect(screen.getByRole('menuitem', { name: /数据飞轮/ })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /Prompt 检查器/ })).toBeInTheDocument();
      expect(screen.queryByRole('menuitem', { name: /仪表盘/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('menuitem', { name: /Agent 平台/ })).not.toBeInTheDocument();
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
      expect(screen.getByRole('menuitem', { name: /业务调试中心/ })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /AI 助手/ })).toBeInTheDocument();
      expect(screen.queryByRole('menuitem', { name: /数据飞轮/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('menuitem', { name: /仪表盘/ })).not.toBeInTheDocument();
    });
  }, 10000);
});
