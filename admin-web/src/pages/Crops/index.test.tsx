import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { listTemplates } from '../../api/crops';
import Crops from './index';

vi.mock('../../api/crops', () => ({
  listTemplates: vi.fn(),
  createTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  parseTemplate: vi.fn(),
}));

describe('Crops 页面', () => {
  beforeAll(() => {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listTemplates).mockResolvedValue({ items: [], total: 0 });
  });

  it('点击新建模板时直接打开手填表单', async () => {
    render(
      <MemoryRouter>
        <Crops />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(listTemplates).toHaveBeenCalledWith({ page: 1, size: 20 });
    });

    fireEvent.click(screen.getByRole('button', { name: /新建模板/ }));

    expect(await screen.findByText('新建作物模板')).toBeInTheDocument();
    expect(screen.getByLabelText('名称')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /添加阶段/ })).toBeInTheDocument();
  });
});
