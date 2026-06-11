import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataFlywheel from './index';
import {
  addSampleLabel,
  createCaseDraft,
  getSampleDetail,
  listDataFlywheelSamples,
  markBadCase,
} from '../../api/dataFlywheel';
import type { DataFlywheelDetail, DataFlywheelSample } from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  addSampleLabel: vi.fn(),
  createCaseDraft: vi.fn(),
  exportSampleJsonl: vi.fn(),
  getSampleDetail: vi.fn(),
  listDataFlywheelSamples: vi.fn(),
  markBadCase: vi.fn(),
}));

const sample: DataFlywheelSample = {
  sample_id: 'turn:session-a:3',
  sample_type: 'turn',
  quality_labels: [],
  annotation_status: 'unlabeled',
  session_id: 'session-a',
  turn_id: 3,
  request_id: 'req:abc',
  user_input_preview: '帮我查一下张三这个月工资有没有漏记',
  assistant_reply_preview: '我来帮你检查工资记录。',
  selected_tools: ['worker.search', 'wage.list'],
  actual_tools: ['worker.search'],
  token_total: 680,
  latency_ms: 920,
  source_type: 'debug_event',
  created_at: '2026-06-11T08:00:00Z',
};

const detail: DataFlywheelDetail = {
  sample,
  quality_labels: [],
  labels: [
    {
      id: 1,
      sample_id: sample.sample_id,
      label: 'good_reply',
      comment: '初始备注',
      annotator_id: 'admin',
      sample_type: 'turn',
      session_id: 'session-a',
      turn_id: 3,
      request_id: 'req:abc',
    },
  ],
  messages: [
    { role: 'user', content: '帮我查一下张三这个月工资有没有漏记' },
    { role: 'assistant', content: '张三本月工资记录里缺少 6 月 8 日。' },
  ],
  turn: null,
  router_decision: {
    selected_tools: ['worker.search', 'wage.list'],
    reason: '需要核对工资流水',
  },
  tool_events: [
    {
      name: 'worker.search',
      payload: { keyword: '张三' },
    },
  ],
  pending_lifecycle: [
    {
      stage: 'pending.plan.created',
      at: '2026-06-11T08:00:01Z',
      payload: { skill: 'wage.list' },
    },
  ],
  debug_export: {
    sample_id: sample.sample_id,
    request_id: 'req:abc',
  },
  source: {
    event_file: 'events/debug.jsonl',
    event_seq_start: 11,
    event_seq_end: 18,
  },
};

const mockedList = vi.mocked(listDataFlywheelSamples);
const mockedDetail = vi.mocked(getSampleDetail);
const mockedAddLabel = vi.mocked(addSampleLabel);
const mockedCreateDraft = vi.mocked(createCaseDraft);
const mockedMarkBadCase = vi.mocked(markBadCase);

describe('DataFlywheel 页面', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    mockedList.mockResolvedValue({ items: [sample], total: 1 });
    mockedDetail.mockResolvedValue(detail);
    mockedAddLabel.mockResolvedValue({
      id: 2,
      sample_id: sample.sample_id,
      label: 'missing_wage',
      comment: '确认工资缺失',
      annotator_id: 'admin',
    });
    mockedCreateDraft.mockResolvedValue({
      id: 10,
      draft_id: 'draft:1',
      source_sample_id: sample.sample_id,
      target_type: 'evaluation_replay',
      status: 'draft',
      case_json: { request_id: 'req:abc', assertion: 'case_json' },
      created_by: 'admin',
    });
    mockedMarkBadCase.mockResolvedValue({
      id: 3,
      sample_id: sample.sample_id,
      label: 'bad_reply',
      comment: '初始备注',
      annotator_id: 'admin',
    });
  });

  it('初次渲染显示标题、样本输入摘要、request_id 和 token 数', async () => {
    render(<DataFlywheel />);

    expect(await screen.findByText('Agent 数据飞轮')).toBeInTheDocument();
    expect(screen.getByText('帮我查一下张三这个月工资有没有漏记')).toBeInTheDocument();
    expect(screen.getByText('req:abc')).toBeInTheDocument();
    expect(screen.getByText('680 tokens')).toBeInTheDocument();
  });

  it('点击样本行后加载详情并显示工具与 pending 生命周期', async () => {
    render(<DataFlywheel />);

    const row = await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(row);

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(sample.sample_id);
    });
    expect(await screen.findByText('样本详情')).toBeInTheDocument();
    expect(screen.getByText('selected_tools')).toBeInTheDocument();
    expect(screen.getByText('pending.plan.created')).toBeInTheDocument();
  });

  it('可以选择工资缺失、填写备注并保存标注', async () => {
    const user = userEvent.setup();
    render(<DataFlywheel />);

    await fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await screen.findByText('样本详情');

    await user.click(screen.getByLabelText('工资缺失'));
    const commentBox = screen.getByPlaceholderText('记录判断依据、复现条件或后续处理建议');
    await user.clear(commentBox);
    await user.type(commentBox, '确认工资缺失');
    await user.click(screen.getByRole('button', { name: /保存标注/ }));

    await waitFor(() => {
      expect(mockedAddLabel).toHaveBeenCalledWith(sample.sample_id, {
        label: 'missing_wage',
        comment: '确认工资缺失',
        sample_type: 'turn',
        session_id: 'session-a',
        turn_id: 3,
        request_id: 'req:abc',
      });
    });
  });

  it('点击生成 regression case 后创建草稿并显示 Case Draft', async () => {
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await screen.findByText('样本详情');
    fireEvent.click(screen.getByRole('button', { name: /生成 regression case/ }));

    await waitFor(() => {
      expect(mockedCreateDraft).toHaveBeenCalledWith(sample.sample_id, 'evaluation_replay');
    });
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Case Draft')).toBeInTheDocument();
    expect(within(dialog).getByText(/case_json/)).toBeInTheDocument();
  });

  it('点击标记 bad case 调用 markBadCase', async () => {
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await screen.findByText('样本详情');
    fireEvent.click(screen.getByRole('button', { name: /标记 bad case/ }));

    await waitFor(() => {
      expect(mockedMarkBadCase).toHaveBeenCalledWith(sample.sample_id, {
        label: 'bad_reply',
        comment: '初始备注',
        sample_type: 'turn',
        session_id: 'session-a',
        turn_id: 3,
        request_id: 'req:abc',
      });
    });
  });
});
