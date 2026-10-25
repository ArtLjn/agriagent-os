import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listPrompts, reloadPrompts } from '../../api/admin';
import type { PromptItem } from '../../api/admin';
import { BusinessContext } from '../../businesses/businessContext';
import type { BusinessContextValue } from '../../businesses/businessContext';
import { businessViews } from '../../businesses/registry';
import type { BusinessView } from '../../businesses/registry';
import PromptManagement from '.';

vi.mock('../../api/admin', () => ({
  listPrompts: vi.fn(),
  reloadPrompts: vi.fn(),
}));

const mockedListPrompts = vi.mocked(listPrompts);
const mockedReloadPrompts = vi.mocked(reloadPrompts);
const farmView = businessViews[0];
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
      children: [{ key: '/dashboard', icon: 'home', label: '实验仪表盘' }],
    },
  ],
};

const platformPrompt: PromptItem = {
  name: 'memory_assess',
  version: 'p1',
  active: false,
  content_length: 8,
  content: '平台提示词',
  scope: 'platform',
  business: null,
};

const systemPrompt: PromptItem = {
  name: 'system',
  version: 's1',
  active: true,
  content_length: 6,
  content: '系统提示词',
  source: 'businesses/farm/prompts/system.md',
  scope: 'business',
  business: 'farm',
};

function contextValue(overrides: Partial<BusinessContextValue> = {}): BusinessContextValue {
  return {
    views: businessViews,
    selectedName: 'farm',
    selectedView: farmView,
    runtimeItems: [],
    runtimeActive: 'farm',
    loading: false,
    switchingName: null,
    error: null,
    selectBusiness: async () => true,
    refresh: () => {},
    runtimeFor: () => undefined,
    ...overrides,
  };
}

function renderPage(value: BusinessContextValue) {
  return render(
    <BusinessContext.Provider value={value}>
      <PromptManagement />
    </BusinessContext.Provider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedListPrompts.mockResolvedValue({
    items: [platformPrompt, systemPrompt],
    total: 2,
    business: 'farm',
    active_business: 'farm',
  });
  mockedReloadPrompts.mockResolvedValue({
    status: 'ok',
    message: '已重新加载',
  });
});

describe('PromptInspector', () => {
  it('按当前业务查看提示词并允许重载', async () => {
    renderPage(contextValue());

    expect(await screen.findByText('system')).toBeInTheDocument();
    expect(mockedListPrompts).toHaveBeenCalledWith('farm');
    expect(screen.getByText('当前进程使用')).toBeInTheDocument();
    expect(screen.getByText('平台内置')).toBeInTheDocument();
    expect(screen.getByText('业务 · farm')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('搜索提示词'), {
      target: { value: '不存在' },
    });
    expect(screen.queryByText('system')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('搜索提示词'), { target: { value: '' } });

    fireEvent.click(screen.getByRole('button', { name: /重新加载模板/ }));

    await waitFor(() => expect(mockedReloadPrompts).toHaveBeenCalledWith('farm'));
    await waitFor(() => expect(mockedListPrompts).toHaveBeenCalledTimes(2));
  });

  it('查看完整系统提示词、源文件和内容版本', async () => {
    mockedListPrompts.mockResolvedValueOnce({
      items: [systemPrompt],
      total: 1,
      business: 'farm',
      active_business: 'farm',
    });

    renderPage(contextValue());

    fireEvent.click(await screen.findByRole('button', { name: '查看内容' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('系统提示词')).toBeInTheDocument();
    expect(within(dialog).getByText(systemPrompt.source!)).toBeInTheDocument();
    expect(within(dialog).getByText('s1')).toBeInTheDocument();
    expect(within(dialog).getByText('当前进程使用')).toBeInTheDocument();
  });

  it('非启用业务只读预览且禁止重载', async () => {
    mockedListPrompts.mockResolvedValueOnce({
      items: [
        platformPrompt,
        {
          ...systemPrompt,
          active: false,
          business: 'lab',
          content: '实验业务提示词',
        },
      ],
      total: 2,
      business: 'lab',
      active_business: 'farm',
    });

    renderPage(contextValue({
      views: [farmView, labView],
      selectedName: 'lab',
      selectedView: labView,
    }));

    expect(await screen.findByText(/未启用，只读预览/)).toBeInTheDocument();
    expect(mockedListPrompts).toHaveBeenCalledWith('lab');
    expect(screen.getByText('只读预览')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重新加载模板/ })).toBeDisabled();
  });

  it('加载失败时提示 Agent 服务并支持重试', async () => {
    mockedListPrompts.mockRejectedValueOnce(new Error('network'));

    renderPage(contextValue());

    expect(await screen.findByText('提示词加载失败')).toBeInTheDocument();
    expect(screen.getByText(/Agent 服务已启动/)).toBeInTheDocument();
    expect(screen.queryByText('暂无 Prompt 数据')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }));

    await waitFor(() => expect(mockedListPrompts).toHaveBeenCalledTimes(2));
  });
});
