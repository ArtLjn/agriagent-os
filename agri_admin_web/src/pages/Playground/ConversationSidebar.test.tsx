import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ConversationSidebar } from './ConversationSidebar';
import { archiveConversation, deleteConversation, listConversations } from '../../api/agent';

vi.mock('../../api/agent', () => ({
  listConversations: vi.fn(), archiveConversation: vi.fn(), deleteConversation: vi.fn(),
}));
const item = { conversation_id: 'c1', last_message: '聊聊番茄', last_role: 'user', last_at: '2026-10-24T10:00:00Z', message_count: 2 };
async function openActions(title = '聊聊番茄') {
  fireEvent.click(await screen.findByRole('button', { name: `会话操作：${title}` }));
  return screen.findByRole('menu');
}

const props = () => ({ userToken: 'owner', sessionId: 'new', sessions: {}, refreshVersion: 0, collapsed: false,
  onCollapse: vi.fn(), onSelect: vi.fn(), onRemove: vi.fn(), onCopyId: vi.fn(), onCopyJson: vi.fn(), onTrace: vi.fn() });

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listConversations).mockResolvedValue({ items: [item], has_more: false });
  vi.mocked(archiveConversation).mockResolvedValue();
  vi.mocked(deleteConversation).mockResolvedValue();
});

describe('会话草稿箱', () => {
  it('收起时隐藏会话内容，展开后保留列表和当前选择', async () => {
    const callbacks = props();
    const view = render(<ConversationSidebar {...callbacks} collapsed sessionId="c1" />);
    await waitFor(() => expect(listConversations).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: '查看会话：聊聊番茄' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开会话列表' }));
    expect(callbacks.onCollapse).toHaveBeenCalledOnce();
    view.rerender(<ConversationSidebar {...callbacks} sessionId="c1" />);
    fireEvent.click(await screen.findByRole('button', { name: '查看会话：聊聊番茄' }));
    expect(callbacks.onSelect).toHaveBeenCalledWith('c1', false);
    expect(listConversations).toHaveBeenCalledOnce();
  });

  it('键盘可以打开行尾菜单并复制编号，不会切换会话', async () => {
    const user = userEvent.setup();
    const callbacks = props();
    render(<ConversationSidebar {...callbacks} />);
    const trigger = await screen.findByRole('button', { name: '会话操作：聊聊番茄' });
    trigger.focus();
    await user.keyboard('{Enter}');
    const copy = await screen.findByRole('menuitem', { name: '复制 Session ID' });
    act(() => copy.focus());
    // rc-menu 使用旧版 which 判断回车；jsdom 的 userEvent 不生成该字段。
    fireEvent.keyDown(copy, { key: 'Enter', code: 'Enter', which: 13, keyCode: 13 });
    expect(callbacks.onCopyId).toHaveBeenCalledExactlyOnceWith('c1');
    expect(callbacks.onSelect).not.toHaveBeenCalled();
  });

  it('归档后移出会话列表，使用当前身份操作且不触发打开', async () => {
    const callbacks = props();
    render(<ConversationSidebar {...callbacks} />);
    await openActions();
    const archive = await screen.findByRole('menuitem', { name: '归档到草稿箱' });
    vi.mocked(listConversations).mockResolvedValue({ items: [], has_more: false });
    fireEvent.click(archive);
    await waitFor(() => expect(callbacks.onRemove).toHaveBeenCalledWith('c1'));
    expect(archiveConversation).toHaveBeenCalledWith('c1', true, 'owner');
    expect(callbacks.onSelect).not.toHaveBeenCalled();
    expect(await screen.findByText('暂无历史会话')).toBeInTheDocument();
  });

  it('草稿箱打开历史使用只读标志，支持恢复', async () => {
    const callbacks = props();
    render(<ConversationSidebar {...callbacks} />);
    await screen.findByRole('button', { name: '会话操作：聊聊番茄' });
    fireEvent.click(screen.getByRole('tab', { name: /草稿箱/ }));
    fireEvent.click(await screen.findByRole('button', { name: '查看会话：聊聊番茄' }));
    expect(callbacks.onSelect).toHaveBeenCalledWith('c1', true);
    expect(listConversations).toHaveBeenLastCalledWith(50, 'owner', { archived: true });
    await openActions();
    fireEvent.click(await screen.findByRole('menuitem', { name: '恢复会话' }));
    await waitFor(() => expect(archiveConversation).toHaveBeenCalledWith('c1', false, 'owner'));
  });

  it('删除必须确认，失败保留会话和确认框以便重试', async () => {
    render(<ConversationSidebar {...props()} />);
    fireEvent.click(screen.getByRole('tab', { name: /草稿箱/ }));
    await openActions();
    fireEvent.click(await screen.findByRole('menuitem', { name: '删除会话' }));
    const dialog = await screen.findByRole('dialog');
    expect(deleteConversation).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: '取 消' }));
    expect(deleteConversation).not.toHaveBeenCalled();
    await openActions();
    fireEvent.click(await screen.findByRole('menuitem', { name: '删除会话' }));
    vi.mocked(deleteConversation).mockRejectedValueOnce(new Error('离线'));
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '确认删除' }));
    await screen.findByText('删除失败，请重试');
    expect(screen.getByRole('button', { name: '查看会话：聊聊番茄' })).toBeInTheDocument();
    vi.mocked(listConversations).mockResolvedValue({ items: [], has_more: false });
    fireEvent.click(await within(screen.getByRole('dialog')).findByRole('button', { name: '确认删除' }));
    await waitFor(() => expect(deleteConversation).toHaveBeenCalledTimes(2));
    expect(deleteConversation).toHaveBeenLastCalledWith('c1', 'owner');
    expect(await screen.findByText('草稿箱为空')).toBeInTheDocument();
  });

  it('生成中的会话不可归档，归档失败不会移除会话', async () => {
    const callbacks = props();
    const view = render(<ConversationSidebar {...callbacks} sessions={{ c1: { messages: [], loading: true, traceLoading: false } }} />);
    await openActions();
    expect(await screen.findByRole('menuitem', { name: '归档到草稿箱' })).toHaveAttribute('aria-disabled', 'true');
    view.rerender(<ConversationSidebar {...callbacks} />);
    vi.mocked(archiveConversation).mockRejectedValueOnce(new Error('离线'));
    fireEvent.click(screen.getByRole('menuitem', { name: '归档到草稿箱' }));
    await screen.findByText('会话操作失败，请重试');
    expect(callbacks.onRemove).not.toHaveBeenCalled();
  });

  it('切换分类后丢弃旧响应，加载更多保留已加载会话', async () => {
    let resolve!: (page: Awaited<ReturnType<typeof listConversations>>) => void;
    vi.mocked(listConversations).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    render(<ConversationSidebar {...props()} />);
    vi.mocked(listConversations).mockResolvedValueOnce({ items: [item], next_cursor: 'c1', has_more: true });
    fireEvent.click(screen.getByRole('tab', { name: /草稿箱/ }));
    await screen.findByRole('button', { name: '查看会话：聊聊番茄' });
    resolve({ items: [{ ...item, last_message: '过期响应' }], has_more: false });
    vi.mocked(listConversations).mockResolvedValueOnce({ items: [{ ...item, conversation_id: 'c2', last_message: '更早会话' }], has_more: false });
    fireEvent.click(screen.getByRole('button', { name: '加载更多' }));
    await screen.findByRole('button', { name: '查看会话：更早会话' });
    expect(screen.getByRole('button', { name: '查看会话：聊聊番茄' })).toBeInTheDocument();
    expect(screen.queryByText('过期响应')).not.toBeInTheDocument();
    expect(listConversations).toHaveBeenLastCalledWith(50, 'owner', { archived: true, cursor: 'c1' });
  });

  it('切换用户后旧列表与未结束的删除均不能影响新身份', async () => {
    let resolve!: () => void;
    const old = props();
    const view = render(<ConversationSidebar key="owner" {...old} />);
    fireEvent.click(screen.getByRole('tab', { name: /草稿箱/ }));
    await openActions();
    fireEvent.click(await screen.findByRole('menuitem', { name: '删除会话' }));
    vi.mocked(deleteConversation).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '确认删除' }));
    vi.mocked(listConversations).mockResolvedValue({ items: [], has_more: false });
    view.rerender(<ConversationSidebar key="new" {...props()} userToken="new" />);
    resolve();
    await screen.findByText('暂无历史会话');
    expect(old.onRemove).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('刷新首页失败后的重试不会错误地沿用旧分页游标', async () => {
    vi.mocked(listConversations).mockResolvedValueOnce({ items: [item], has_more: true, next_cursor: 'c1' });
    const callbacks = props();
    const view = render(<ConversationSidebar {...callbacks} />);
    await screen.findByRole('button', { name: '加载更多' });
    vi.mocked(listConversations).mockRejectedValueOnce(new Error('离线'));
    view.rerender(<ConversationSidebar {...callbacks} refreshVersion={1} />);
    fireEvent.click(await screen.findByRole('button', { name: '加载失败，点击重试' }));
    await waitFor(() => expect(listConversations).toHaveBeenCalledTimes(3));
    expect(listConversations).toHaveBeenLastCalledWith(50, 'owner', { archived: false });
  });
});
