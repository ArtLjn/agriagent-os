import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { StreamChunk } from '../../api/agent';
import Playground from './index';

const api = vi.hoisted(() => ({ streamChat: vi.fn(), approveTurn: vi.fn() }));
vi.mock('../../api/agent', () => ({
  streamChat: api.streamChat,
  approveTurn: api.approveTurn,
  listDevUsers: vi.fn().mockResolvedValue([]),
  listConversations: vi.fn().mockResolvedValue([]),
  getConversationMessages: vi.fn().mockResolvedValue([]),
  getConversationMessagesPage: vi.fn().mockResolvedValue({ items: [], has_more: false }),
  getConversationTurns: vi.fn().mockResolvedValue({ items: [] }),
  getConversationTurnDetail: vi.fn(),
}));
vi.mock('../../api/admin', () => ({ listTraces: vi.fn().mockResolvedValue({ items: [] }), getTimeline: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(Element.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  api.streamChat.mockImplementation(async function* (): AsyncGenerator<StreamChunk> {
    yield { type: 'step.started', data: { turn_id: 't-1', step_index: 1, status: 'running' } };
    yield { type: 'tool_started', data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, arguments: { city: '天津' } } };
    yield { type: 'tool_finished', data: { turn_id: 't-1', tool_call_id: 'c-1', tool_name: 'get_weather', step: 1, duration_ms: 80, result: { weather: '晴' } } };
    yield { type: 'step.completed', data: { turn_id: 't-1', step_index: 1, status: 'completed', tool_count: 1 } };
    yield { type: 'content', data: '天气查询完成' };
    yield { type: 'turn.completed', data: { status: 'completed' } };
  });
});

describe('Playground 执行界面交互', () => {
  it('发送后在对话内联展示执行步骤，新会话不保留旧记录', async () => {
    render(<Playground />);
    fireEvent.change(screen.getByRole('textbox', { name: '对话输入' }), { target: { value: '查询天气' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText('天气查询完成');
    await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    const execution = screen.getByLabelText('执行过程');
    expect(execution).toBeInTheDocument();
    expect(within(execution).getByText('get_weather')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '新建会话' }));
    expect(screen.queryByLabelText('执行过程')).not.toBeInTheDocument();
    expect(screen.queryByText('天气查询完成')).not.toBeInTheDocument();
  });

  it('输入法选词和 Shift+Enter 不发送，Enter 发送完整多行内容', async () => {
    render(<Playground />);
    const input = screen.getByRole('textbox', { name: '对话输入' });
    fireEvent.change(input, { target: { value: '查询天气\n给出建议' } });
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    expect(api.streamChat).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: 'Enter' });
    await screen.findByText('天气查询完成');
    expect(api.streamChat.mock.calls[0][0]).toBe('查询天气\n给出建议');
    await waitFor(() => expect(input).toBeEnabled());
  });
  it.each([['确认', true], ['取消', false]] as const)('保留%s审批操作并同步详情状态', async (action, approved) => {
    api.streamChat.mockImplementation(async function* (): AsyncGenerator<StreamChunk> {
      yield { type: 'pending_action', data: { action_id: 'approval-1', skill_name: 'create_cycle', params: { crop: '西瓜' } } };
      yield { type: 'content', data: '请确认是否创建茬口' };
    });
    api.approveTurn.mockResolvedValue({});
    render(<Playground />);
    fireEvent.change(screen.getByRole('textbox', { name: '对话输入' }), { target: { value: '创建茬口' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    const actionButton = await screen.findByRole('button', { name: action });
    await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    const approval = screen.getByRole('group', { name: '待确认操作' });
    expect(approval).toHaveTextContent('create_cycle');
    expect(approval).toHaveTextContent('西瓜');
    fireEvent.click(actionButton);
    await waitFor(() => expect(api.approveTurn).toHaveBeenCalledWith('approval-1', approved, approved ? '用户确认' : '用户取消'));
    expect(screen.queryByRole('button', { name: action })).not.toBeInTheDocument();
    expect(screen.getByLabelText('任务执行详情')).toHaveTextContent(approved ? '已确认' : '已取消');
  });

});
