import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { StreamChunk } from '../../api/agent';
import Playground from './index';

const api = vi.hoisted(() => ({ streamChat: vi.fn(), approveTurn: vi.fn(), getMemoryLearningStatus: vi.fn(), listConversations: vi.fn(), archiveConversation: vi.fn(), deleteConversation: vi.fn(), listDevUsers: vi.fn() }));
vi.mock('../../api/agent', () => ({
  streamChat: api.streamChat,
  approveTurn: api.approveTurn,
  getMemoryLearningStatus: api.getMemoryLearningStatus,
  listDevUsers: api.listDevUsers,
  listConversations: api.listConversations,
  archiveConversation: api.archiveConversation,
  deleteConversation: api.deleteConversation,
  getConversationMessages: vi.fn().mockResolvedValue([]),
  getConversationMessagesPage: vi.fn().mockResolvedValue({ items: [], has_more: false }),
  getConversationTurns: vi.fn().mockResolvedValue({ items: [] }),
  getConversationTurnDetail: vi.fn(),
}));
vi.mock('../../api/admin', () => ({ listTraces: vi.fn().mockResolvedValue({ items: [] }), getTimeline: vi.fn() }));
vi.mock('../../api/questionRecommendations', () => ({
  RECOMMENDATION_HISTORY_LIMIT: 18,
  getQuestionRecommendations: vi.fn().mockResolvedValue({
    mode: 'personalized',
    items: [{ id: 'tomato', question: '帮我梳理番茄采收前需要注意的事项', basis: 'memory' }],
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  api.listConversations.mockResolvedValue({ items: [], has_more: false });
  api.listDevUsers.mockResolvedValue([]);
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
  it('流仍在生成时就按真实轮次展示后台学习状态', async () => {
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => { finish = resolve; });
    api.getMemoryLearningStatus.mockResolvedValue({ status: 'running' });
    api.streamChat.mockImplementation(async function* (): AsyncGenerator<StreamChunk> {
      yield { type: 'meta', data: { turn_id: 'learning-turn', trace_id: 'learning-trace', conversation_id: 'session' } };
      yield { type: 'content', data: '正在处理你的问题' };
      await pending;
    });
    render(<Playground />);
    fireEvent.change(screen.getByRole('textbox', { name: '对话输入' }), { target: { value: '继续聊聊' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    try {
      expect(await screen.findByText('听到啦，正在整理你说的话…')).toBeInTheDocument();
      expect(api.getMemoryLearningStatus).toHaveBeenCalledWith('learning-turn', null);
      expect(screen.getByRole('textbox', { name: '对话输入' })).toBeDisabled();
    } finally {
      finish();
      await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    }
  });

  it('归档当前会话开启空白会话，草稿箱历史只读并可恢复', async () => {
    let archived = false;
    const row = { conversation_id: 'archive-flow', last_message: '用于归档的会话', last_role: 'user', last_at: '2026-10-24T00:00:00Z', message_count: 2 };
    api.listConversations.mockImplementation(async (_limit, _token, options) => ({ items: options.archived === archived ? [row] : [], has_more: false }));
    api.archiveConversation.mockImplementation(async (_id, value) => { archived = value; });
    render(<Playground />);
    fireEvent.click(await screen.findByRole('button', { name: '查看会话：用于归档的会话' }));
    await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: '会话操作：用于归档的会话' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '归档到草稿箱' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: '查看会话：用于归档的会话' })).not.toBeInTheDocument());
    expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled();
    fireEvent.click(screen.getByRole('tab', { name: /草稿箱/ }));
    fireEvent.click(await screen.findByRole('button', { name: '查看会话：用于归档的会话' }));
    await screen.findByText('此会话已归档。请在草稿箱恢复后继续聊天。');
    expect(screen.queryByRole('textbox', { name: '对话输入' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '会话操作：用于归档的会话' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '恢复会话' }));
    await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    fireEvent.click(screen.getByRole('tab', { name: '会话' }));
    expect(await screen.findByRole('button', { name: '查看会话：用于归档的会话' })).toBeInTheDocument();
  });

  it('切换身份后旧流完成不能把旧会话重新加到列表', async () => {
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => { finish = resolve; });
    api.listDevUsers.mockResolvedValue([{ user_id: 'new-user', token: 'new-token', nickname: '另一个用户', role: 'user', farm_id: 7 }]);
    api.streamChat.mockImplementation(async function* (): AsyncGenerator<StreamChunk> {
      yield { type: 'content', data: '旧用户的回复' };
      await pending;
      yield { type: 'content', data: '迟到的回复' };
    });
    render(<Playground />);
    fireEvent.change(screen.getByRole('textbox', { name: '对话输入' }), { target: { value: '旧用户的问题' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText('旧用户的回复');
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByText('另一个用户 (farm:7, user)'));
    await waitFor(() => expect(screen.queryByText('旧用户的回复')).not.toBeInTheDocument());
    await act(async () => { finish(); await pending; });
    await waitFor(() => expect(screen.getByRole('textbox', { name: '对话输入' })).toBeEnabled());
    expect(screen.queryByRole('button', { name: '查看会话：新会话' })).not.toBeInTheDocument();
    expect(screen.queryByText('迟到的回复')).not.toBeInTheDocument();
  });

  it('点击推荐填入输入框并聚焦，用户发送前不调用 Agent', async () => {
    render(<Playground />);
    fireEvent.click(await screen.findByRole('button', { name: /番茄采收前/ }));
    const input = screen.getByRole('textbox', { name: '对话输入' });
    expect(input).toHaveValue('帮我梳理番茄采收前需要注意的事项');
    expect(input).toHaveFocus();
    expect(api.streamChat).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await waitFor(() => expect(api.streamChat).toHaveBeenCalled());
    expect(api.streamChat.mock.calls[0][0]).toBe('帮我梳理番茄采收前需要注意的事项');
  });

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
    await screen.findByRole('button', { name: /番茄采收前/ });
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
    expect(screen.getByRole('textbox', { name: '对话输入' })).toBe(input);
    expect(screen.queryByRole('heading', { name: '今天，想一起探索什么？' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '新建会话' }));
    expect(screen.getByRole('textbox', { name: '对话输入' })).toBe(input);
    expect(screen.getByRole('heading', { name: '今天，想一起探索什么？' })).toBeInTheDocument();
    await screen.findByRole('button', { name: /番茄采收前/ });
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
