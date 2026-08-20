import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import AdminLayout from '../../layouts/AdminLayout';

describe('DataFlywheel 路由布局', () => {
  it('在 Agent 平台菜单和页头显示数据飞轮', () => {
    render(
      <MemoryRouter initialEntries={['/dev/data-flywheel']}>
        <AdminLayout>
          <div>DataFlywheel content</div>
        </AdminLayout>
      </MemoryRouter>,
    );

    expect(screen.getAllByText('数据飞轮').length).toBeGreaterThanOrEqual(2);
  });
});
