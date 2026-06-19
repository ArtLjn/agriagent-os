import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  importSystemCropTemplate,
  listSystemCropTemplates,
  type CropTemplate,
} from '../../api/crops';
import SystemLibrary from './SystemLibrary';

vi.mock('../../api/crops', () => ({
  importSystemCropTemplate: vi.fn(),
  listSystemCropTemplates: vi.fn(),
}));

const mockedListSystemCropTemplates = vi.mocked(listSystemCropTemplates);
const mockedImportSystemCropTemplate = vi.mocked(importSystemCropTemplate);

const templates: CropTemplate[] = [
  {
    id: 101,
    name: '水稻',
    variety: '通用',
    category: '粮食',
    stages: [
      { id: 1, crop_template_id: 101, name: '育秧期', duration_days: 25, order_index: 1 },
      { id: 2, crop_template_id: 101, name: '分蘖期', duration_days: 30, order_index: 2 },
    ],
  },
  {
    id: 102,
    name: '番茄',
    variety: '设施栽培',
    category: '蔬菜',
    stages: [
      { id: 3, crop_template_id: 102, name: '苗期', duration_days: 28, order_index: 1 },
    ],
  },
];

describe('SystemLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListSystemCropTemplates.mockResolvedValue(templates);
    mockedImportSystemCropTemplate.mockResolvedValue({ id: 201, already_exists: false });
  });

  it('展示系统模板列表和阶段摘要', async () => {
    render(
      <MemoryRouter>
        <SystemLibrary />
      </MemoryRouter>,
    );

    expect(await screen.findByText('水稻')).toBeInTheDocument();
    expect(screen.getByText('番茄')).toBeInTheDocument();
    expect(screen.getByText('粮食')).toBeInTheDocument();
    expect(screen.getByText('育秧期')).toBeInTheDocument();
    expect(screen.getByText('分蘖期')).toBeInTheDocument();
  });

  it('按分类筛选系统模板', async () => {
    const user = userEvent.setup();
    mockedListSystemCropTemplates
      .mockResolvedValueOnce(templates)
      .mockResolvedValueOnce([templates[1]])
      .mockResolvedValueOnce([templates[0]]);

    render(
      <MemoryRouter>
        <SystemLibrary />
      </MemoryRouter>,
    );

    await screen.findByText('水稻');
    await user.click(screen.getByRole('combobox', { name: '作物分类' }));
    await user.click(await screen.findByTitle('蔬菜'));

    await waitFor(() => {
      expect(mockedListSystemCropTemplates).toHaveBeenLastCalledWith('蔬菜');
    });

    await user.click(screen.getByRole('combobox', { name: '作物分类' }));
    await user.click(await screen.findByTitle('粮食'));

    await waitFor(() => {
      expect(mockedListSystemCropTemplates).toHaveBeenLastCalledWith('粮食');
    });
  });

  it('支持多选后一键导入', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <SystemLibrary />
      </MemoryRouter>,
    );

    await screen.findByText('水稻');
    await user.click(within(screen.getByRole('row', { name: /水稻/ })).getByRole('checkbox'));
    await user.click(within(screen.getByRole('row', { name: /番茄/ })).getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /导入所选/ }));

    await waitFor(() => {
      expect(mockedImportSystemCropTemplate).toHaveBeenCalledWith(101);
      expect(mockedImportSystemCropTemplate).toHaveBeenCalledWith(102);
    });
  });

  it('重复导入时提示已有模板并保留列表', async () => {
    const user = userEvent.setup();
    mockedImportSystemCropTemplate.mockResolvedValueOnce({ id: 301, already_exists: true });

    render(
      <MemoryRouter>
        <SystemLibrary />
      </MemoryRouter>,
    );

    await screen.findByText('水稻');
    await user.click(within(screen.getByRole('row', { name: /水稻/ })).getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /导入所选/ }));

    expect(await screen.findByText('已存在相同模板，已为你跳过重复导入')).toBeInTheDocument();
    expect(screen.getByText('水稻')).toBeInTheDocument();
  });
});
