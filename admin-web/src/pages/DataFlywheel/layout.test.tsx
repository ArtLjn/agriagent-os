import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataFlywheel from './index';
import {
  getSampleDetail,
  getSessionReview,
  listDataFlywheelSamples,
} from '../../api/dataFlywheel';
import type {
  DataFlywheelDetail,
  DataFlywheelSample,
  DataFlywheelSessionReview,
} from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  addSampleLabel: vi.fn(),
  createCaseDraft: vi.fn(),
  createRepairPack: vi.fn(),
  exportSampleJsonl: vi.fn(),
  getSampleDetail: vi.fn(),
  getSessionReview: vi.fn(),
  listRepairPackCandidates: vi.fn(),
  listDataFlywheelSamples: vi.fn(),
  markBadCase: vi.fn(),
  markRepairPackResolved: vi.fn(),
  rebuildRepairPack: vi.fn(),
  recordRepairPackVerificationFailure: vi.fn(),
}));

const sample: DataFlywheelSample = {
  sample_id: 'turn:session-a:3',
  sample_type: 'turn',
  quality_labels: [],
  annotation_status: 'unlabeled',
  session_id: 'session-a',
  turn_id: 3,
  request_id: 'req:abc',
  user_input_preview: '我的工人',
  assistant_reply_preview: '当前可查的工人列表如下。',
  selected_tools: ['worker.search'],
  actual_tools: ['worker.search'],
  issue_candidates: [],
  token_total: 680,
  latency_ms: 920,
  source_type: 'debug_event',
  created_at: '2026-06-11T08:00:00Z',
};

const detail: DataFlywheelDetail = {
  sample,
  quality_labels: [],
  prelabels: [],
  labels: [],
  messages: [
    { role: 'user', content: '我的工人' },
    { role: 'assistant', content: '当前可查的工人列表如下。' },
  ],
  turn: null,
  router_decision: { selected_tools: ['worker.search'] },
  tool_events: [],
  pending_lifecycle: [],
  issue_candidates: [],
  debug_export: null,
  source: {
    event_file: 'events/debug.jsonl',
    event_seq_start: 1,
    event_seq_end: 5,
  },
};

const review: DataFlywheelSessionReview = {
  session_id: 'session-a',
  turns: [
    {
      sample,
      messages: detail.messages,
      router_decision: detail.router_decision,
      tool_events: detail.tool_events,
      pending_lifecycle: detail.pending_lifecycle,
      source: detail.source,
    },
  ],
};

describe('DataFlywheel 可折叠布局', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listDataFlywheelSamples).mockResolvedValue({ items: [sample], total: 1 });
    vi.mocked(getSessionReview).mockResolvedValue(review);
    vi.mocked(getSampleDetail).mockResolvedValue(detail);
  });

  it('顶部归档和右侧详情可以收起，让会话 turn 与详情形成两栏主体', async () => {
    render(<DataFlywheel />);

    await screen.findByText('Agent 数据飞轮');
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-left-collapsed',
      'false'
    );
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-right-collapsed',
      'false'
    );

    fireEvent.click(screen.getByRole('button', { name: '收起顶部归档区' }));
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-left-collapsed',
      'true'
    );
    expect(screen.getByRole('button', { name: '展开顶部归档区' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '收起详情区' }));
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-right-collapsed',
      'true'
    );
    fireEvent.click(screen.getByRole('button', { name: '展开详情区' }));
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-right-collapsed',
      'false'
    );
  });

  it('顶部归档将四个固定筛选桶与会话记录滚动行分开', async () => {
    render(<DataFlywheel />);

    await screen.findByText('Agent 数据飞轮');

    const bucketRow = screen.getByTestId('archive-session-all').parentElement;
    expect(bucketRow).toContainElement(screen.getByTestId('archive-issues'));
    expect(bucketRow).toContainElement(screen.getByTestId('archive-ai-prelabels'));
    expect(bucketRow).toContainElement(screen.getByTestId('archive-confirmed-issues'));
    expect(bucketRow).not.toContainElement(screen.getByTestId('archive-session-session-a'));

    const sessionRow = screen.getByTestId('archive-session-session-a').parentElement;
    expect(sessionRow).not.toBe(bucketRow);
  });

  it('在完整会话里选择 turn 后自动展开右侧详情区', async () => {
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');

    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-right-collapsed',
      'false'
    );
    fireEvent.click(screen.getByTestId('review-select-turn:session-a:3'));

    await waitFor(() => {
      expect(getSampleDetail).toHaveBeenCalledWith(sample.sample_id);
    });
    expect(screen.getByTestId('data-flywheel-workspace')).toHaveAttribute(
      'data-right-collapsed',
      'false'
    );
  });
});
