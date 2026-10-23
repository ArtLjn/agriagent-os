import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PromptManagement from './index';
import { listPrompts, reloadPrompts } from '../../api/admin';

vi.mock('../../api/admin', () => ({ listPrompts: vi.fn(), reloadPrompts: vi.fn() }));
const item = { name: 'system', version: 'abc123', active: true, content: '系统提示词测试原文', content_length: 9, source: 'agent/prompts/system.md' };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listPrompts).mockResolvedValue({ items: [item], total: 1 });
  vi.mocked(reloadPrompts).mockResolvedValue({ status: 'ok', message: '重新加载成功' });
});

describe('Prompt 管理', () => {
  it('查看完整系统提示词、源文件和内容版本', async () => {
    render(<PromptManagement />);
    fireEvent.click(await screen.findByText('查看内容'));
    expect(await screen.findByText(item.content)).toBeInTheDocument();
    expect(screen.getByText(item.source)).toBeInTheDocument();
    expect(screen.getByText('Prompt 管理')).toBeInTheDocument();
  });
  it('支持搜索并在重新加载后刷新内容', async () => {
    render(<PromptManagement />);
    await screen.findByText('system');
    fireEvent.change(screen.getByLabelText('搜索提示词'), { target: { value: '不存在' } });
    expect(screen.queryByText('system')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('重新加载模板'));
    await waitFor(() => expect(listPrompts).toHaveBeenCalledTimes(2));
    expect(reloadPrompts).toHaveBeenCalledTimes(1);
  });
  it('加载失败可以重试', async () => {
    vi.mocked(listPrompts).mockRejectedValueOnce(new Error('失败'));
    render(<PromptManagement />);
    fireEvent.click(await screen.findByRole('button', { name: /重\s*试/ }));
    expect(await screen.findByText('system')).toBeInTheDocument();
  });
});
