import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConfigProvider } from 'antd';
import { memosApi, type Memo } from '../../api/memos';
import { MemoPanel } from './index';

vi.mock('../../api/memos', () => ({ MEMO_PAGE_SIZE: 10, memosApi: { list: vi.fn(), create: vi.fn(), update: vi.fn() } }));
const memo: Memo = { id: 7, title: '巡田准备', content: '检查滴灌设备', pinned: false, archived: false, created_at: '2026-10-23T00:00:00Z', updated_at: '2026-10-23T00:00:00Z' };
const list = vi.mocked(memosApi.list);

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});
beforeEach(() => {
  vi.clearAllMocks();
  list.mockResolvedValue({ items: [memo], total: 1 });
  vi.mocked(memosApi.create).mockResolvedValue(memo);
  vi.mocked(memosApi.update).mockResolvedValue(memo);
});

describe('备忘录面板', () => {
  it('显示真实列表并按关键词和归档状态查询', async () => {
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    expect(await screen.findByText('巡田准备')).toBeInTheDocument();
    expect(screen.getByText('检查滴灌设备')).toBeInTheDocument();
    const search = screen.getByRole('searchbox', { name: '搜索备忘录' });
    fireEvent.change(search, { target: { value: '滴灌' } });
    fireEvent.keyDown(search, { key: 'Enter', code: 'Enter', charCode: 13 });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: '滴灌', skip: 0 }), expect.any(AbortSignal)));
    fireEvent.click(screen.getByText('已归档'));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ archived: true }), expect.any(AbortSignal)));
  });

  it('创建失败保留输入，重试复用幂等键', async () => {
    vi.mocked(memosApi.create).mockRejectedValueOnce(new Error('网络中断'));
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    fireEvent.click(screen.getByRole('button', { name: /新建备忘录/ }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('标题'), { target: { value: '采购清单' } });
    fireEvent.change(within(dialog).getByLabelText('内容'), { target: { value: '滴灌接头 20 个' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /保.*存/ }));
    await waitFor(() => expect(memosApi.create).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(within(dialog).getByLabelText('标题')).toBeEnabled());
    expect(within(dialog).getByLabelText('内容')).toHaveValue('滴灌接头 20 个');
    fireEvent.click(within(dialog).getByRole('button', { name: /保.*存/ }));
    await waitFor(() => expect(memosApi.create).toHaveBeenCalledTimes(2));
    const calls = vi.mocked(memosApi.create).mock.calls;
    expect(calls[0][0]).toEqual(calls[1][0]);
    expect(calls[0][0].client_request_id).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('编辑与置顶使用当前记录 ID', async () => {
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    fireEvent.click(await screen.findByRole('button', { name: '巡田准备' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByLabelText('内容')).toHaveValue('检查滴灌设备');
    fireEvent.change(within(dialog).getByLabelText('内容'), { target: { value: '补充巡田记录' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /保.*存/ }));
    await waitFor(() => expect(memosApi.update).toHaveBeenCalledWith(7, { title: '巡田准备', content: '补充巡田记录' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(await screen.findByRole('button', { name: '置顶' }));
    await waitFor(() => expect(memosApi.update).toHaveBeenCalledWith(7, { pinned: true }));
  });

  it('支持归档和恢复', async () => {
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    fireEvent.click(await screen.findByRole('button', { name: '归档' }));
    await waitFor(() => expect(memosApi.update).toHaveBeenCalledWith(7, { archived: true }));
    list.mockResolvedValue({ items: [{ ...memo, archived: true }], total: 1 });
    fireEvent.click(screen.getByText('已归档'));
    fireEvent.click(await screen.findByRole('button', { name: '恢复' }));
    await waitFor(() => expect(memosApi.update).toHaveBeenCalledWith(7, { archived: false }));
  });

  it('加载失败显示具体错误并支持重试', async () => {
    list.mockRejectedValueOnce({ response: { data: { detail: { code: 'memo_schema_not_ready', message: '备忘录数据表尚未初始化' } } } });
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    expect(await screen.findByText('备忘录数据表尚未初始化')).toBeInTheDocument();
    expect(screen.queryByText('巡田准备')).not.toBeInTheDocument();
    list.mockResolvedValue({ items: [], total: 0 });
    fireEvent.click(screen.getByRole('button', { name: /重.*试/ }));
    expect(await screen.findByText('还没有备忘录，记下第一件事吧')).toBeInTheDocument();
  });

  it('切换筛选后忽略迟到的旧响应', async () => {
    let resolveOld!: (result: { items: Memo[]; total: number }) => void;
    list.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    list.mockResolvedValue({ items: [], total: 0 });
    fireEvent.click(screen.getByText('已归档'));
    expect(await screen.findByText('暂无归档备忘录')).toBeInTheDocument();
    resolveOld({ items: [memo], total: 1 });
    await waitFor(() => expect(list.mock.calls[0][1]?.aborted).toBe(true));
    expect(screen.queryByText('巡田准备')).not.toBeInTheDocument();
  });

  it('当前分页最后一条归档后回到有效页', async () => {
    list.mockResolvedValueOnce({ items: [memo], total: 11 });
    render(<ConfigProvider theme={{ token: { motion: false } }}><MemoPanel /></ConfigProvider>);
    await screen.findByText('巡田准备');
    list.mockResolvedValueOnce({ items: [memo], total: 11 });
    fireEvent.click(screen.getByTitle('2'));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ skip: 10 }), expect.any(AbortSignal)));
    list.mockResolvedValue({ items: [], total: 10 });
    fireEvent.click(await screen.findByRole('button', { name: '归档' }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ skip: 0 }), expect.any(AbortSignal)));
  });
});
