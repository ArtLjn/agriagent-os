import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getMemoryLearningStatus } from '../../api/agent';
import { MemoryLearningNotice } from './MemoryLearningNotice';

vi.mock('../../api/agent', () => ({ getMemoryLearningStatus: vi.fn() }));
const api = vi.mocked(getMemoryLearningStatus);
beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe('后台学习反馈', () => {
  it('聊天结束后继续查询，只有提交成功才说已记住', async () => {
    api.mockResolvedValueOnce({ status: 'running' }).mockResolvedValueOnce({ status: 'done', applied_count: 1 });
    render(<MemoryLearningNotice turnId="t1" userToken="user-token" watch />);
    await act(async () => {});
    expect(screen.getByRole('status')).toHaveTextContent('听到啦，正在整理你说的话');
    expect(screen.queryByText(/已记住/)).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.getByRole('status')).toHaveTextContent('已记住，这次整理了 1 条记忆');
    await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
    expect(api).toHaveBeenCalledTimes(2);
    expect(api).toHaveBeenCalledWith('t1', 'user-token');
  });
  it.each(['disabled', 'temporary', 'not_observed', 'sensitive'])('没有触发学习时不显示成功：%s', async (status) => {
    api.mockResolvedValue({ status });
    const { container, unmount } = render(<MemoryLearningNotice turnId="old" watch={false} />);
    await act(async () => {});
    expect(container).toBeEmptyDOMElement();
    unmount();
    expect(api).toHaveBeenCalledTimes(1);
  });
  it.each([
    [{ status: 'done', applied_count: 0 }, '没有需要长期记住的新内容'],
    [{ status: 'failed', code: 'memory_extraction_incomplete' }, '这次记忆整理未成功'],
  ])('无新增或失败都不能假报成功', async (data, label) => {
    api.mockResolvedValue(data);
    render(<MemoryLearningNotice turnId="t" watch />);
    await act(async () => {});
    expect(screen.getByRole('status')).toHaveTextContent(label);
    expect(screen.queryByText(/已记住/)).not.toBeInTheDocument();
  });
  it('离开会话后取消轮询', async () => {
    api.mockResolvedValue({ status: 'pending' });
    const { unmount } = render(<MemoryLearningNotice turnId="t" watch />);
    await act(async () => {});
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(api).toHaveBeenCalledTimes(1);
  });
});
