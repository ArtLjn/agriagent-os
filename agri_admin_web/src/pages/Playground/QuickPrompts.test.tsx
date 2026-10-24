import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getQuestionRecommendations, type QuestionRecommendations } from '../../api/questionRecommendations';
import { QuickPrompts } from './QuickPrompts';

vi.mock('../../api/questionRecommendations', () => ({ getQuestionRecommendations: vi.fn(), RECOMMENDATION_HISTORY_LIMIT: 18 }));
const api = vi.mocked(getQuestionRecommendations);
const data: QuestionRecommendations = {
  mode: 'personalized',
  items: [{ id: 'one', question: '帮我梳理番茄采收前需要注意的事项', basis: 'memory' }],
};

beforeEach(() => { vi.clearAllMocks(); api.mockResolvedValue(data); });

describe('个性化推荐问题', () => {
  it('展示动态问题，点击只交给输入框回调', async () => {
    const select = vi.fn();
    render(<QuickPrompts onSelect={select} userToken="user-a" />);
    expect(screen.getByText('正在为你准备问题…')).toBeInTheDocument();
    const button = await screen.findByRole('button', { name: /番茄采收前/ });
    fireEvent.click(button);
    expect(select).toHaveBeenCalledExactlyOnceWith(data.items[0].question);
    expect(api).toHaveBeenCalledWith([], 'user-a', expect.any(AbortSignal));
    expect(screen.getByText('结合你已保存的兴趣与偏好')).toBeInTheDocument();
    expect(screen.queryByText('记一笔账')).not.toBeInTheDocument();
  });

  it('长问题保留完整可访问名称和填入内容，加载骨架不可点击', async () => {
    const question = '请帮我梳理番茄采收前的田间管理事项，包括如何检查灌溉、通风和采收记录，并按准备工作的先后顺序说明具体步骤。';
    api.mockResolvedValueOnce({ mode: 'personalized', items: [{ id: 'long', question, basis: 'memory' }] });
    const select = vi.fn();
    render(<QuickPrompts onSelect={select} />);
    expect(screen.getByRole('status')).toHaveTextContent('正在为你准备问题');
    expect(screen.getAllByRole('button')).toHaveLength(1);
    const button = await screen.findByRole('button', { name: question });
    expect(button).toHaveAttribute('title', question);
    fireEvent.click(button);
    expect(select).toHaveBeenCalledWith(question);
  });

  it('换一批排除已展示问题，显示新的推荐', async () => {
    render(<QuickPrompts onSelect={vi.fn()} />);
    await screen.findByText(data.items[0].question);
    api.mockResolvedValueOnce({ mode: 'explore', items: [{ id: 'two', question: '帮我回顾最近的农事记录', basis: 'explore' }] });
    fireEvent.click(screen.getByRole('button', { name: '换一批' }));
    expect(await screen.findByText('帮我回顾最近的农事记录')).toBeInTheDocument();
    expect(api).toHaveBeenLastCalledWith([data.items[0].question], null, expect.any(AbortSignal));
    expect(screen.getByTitle('探索话题')).toBeInTheDocument();
    expect(screen.queryByText('结合你已保存的兴趣与偏好')).not.toBeInTheDocument();
  });

  it('切换用户立即清空旧推荐，迟到响应不会覆盖新用户', async () => {
    let resolveOld!: (value: QuestionRecommendations) => void;
    api.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }));
    const view = render(<QuickPrompts onSelect={vi.fn()} userToken="user-a" />);
    view.rerender(<QuickPrompts onSelect={vi.fn()} userToken="user-b" />);
    await screen.findByText(data.items[0].question);
    resolveOld({ mode: 'explore', items: [{ id: 'old', question: '不能显示的旧用户问题', basis: 'explore' }] });
    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('不能显示的旧用户问题')).not.toBeInTheDocument();
    expect(api.mock.calls[0][2].aborted).toBe(true);
    view.rerender(<QuickPrompts onSelect={vi.fn()} userToken="user-c" />);
    expect(screen.queryByText(data.items[0].question)).not.toBeInTheDocument();
    await screen.findByText(data.items[0].question);
  });

  it('失败可以重试，且不冒充个性化推荐', async () => {
    api.mockRejectedValueOnce(new Error('不可用'));
    render(<QuickPrompts onSelect={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '重试' }));
    expect(await screen.findByText(data.items[0].question)).toBeInTheDocument();
  });

  it('发送期间禁用推荐和换一批', async () => {
    const select = vi.fn();
    render(<QuickPrompts onSelect={select} disabled />);
    const button = await screen.findByRole('button', { name: /番茄采收前/ });
    expect(button).toBeDisabled();
    expect(screen.getByRole('button', { name: '换一批' })).toBeDisabled();
    fireEvent.click(button);
    expect(select).not.toHaveBeenCalled();
  });
});
