import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Cycles from './index';
import { listCycles } from '../../api/cycles';

vi.mock('../../api/cycles', () => ({ listCycles: vi.fn(), createCycle: vi.fn(), updateCycle: vi.fn(), deleteCycle: vi.fn(), parseCycle: vi.fn() }));
vi.mock('../../api/crops', () => ({ listTemplates: vi.fn().mockResolvedValue({ items: [] }) }));
vi.mock('../../components/ApiDebugger', () => ({ default: () => null }));

beforeEach(() => {
  vi.mocked(listCycles).mockResolvedValue({ items: [
    { id: 1, name: '芒果种植计划', crop_template_name: '芒果', start_date: '2026-08-18', status: 'active', current_stage_name: '育苗期' },
    { id: 2, name: '水稻种植计划', crop_template_name: '水稻', start_date: '2026-08-27', status: 'active', current_stage_name: '拔节孕穗期' },
  ], total: 42 });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('种植周期工作台', () => {
  it('选择计划更新摘要，本页搜索不改变服务端总数', async () => {
    render(<MemoryRouter><Cycles /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: '水稻种植计划' }));
    expect(within(screen.getByRole('complementary')).getByText('水稻种植计划')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: '搜索本页种植计划' }), { target: { value: '芒果' } });
    expect(screen.queryByRole('button', { name: '水稻种植计划' })).not.toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(within(screen.getByRole('complementary')).getByText('芒果种植计划')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: '搜索本页种植计划' }), { target: { value: '不存在' } });
    expect(screen.getByText('本页没有匹配的种植计划，请调整筛选')).toBeInTheDocument();
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('加载失败显示重试，恢复后可打开新建表单', async () => {
    vi.mocked(listCycles).mockRejectedValueOnce(new Error('网络不可用'));
    render(<MemoryRouter><Cycles /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: /重\s*试/ }));
    expect(await screen.findByRole('button', { name: '芒果种植计划' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '新建茬口' }));
    expect(await screen.findByRole('dialog', { name: '新建茬口' })).toBeInTheDocument();
  });
});
