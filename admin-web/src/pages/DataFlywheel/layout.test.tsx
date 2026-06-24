import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataFlywheel from './index';
import {
  getDailyReviewInbox,
  getSampleDetail,
  getReviewIssueChain,
  getSessionReview,
  listDataFlywheelSamples,
} from '../../api/dataFlywheel';
import type {
  DataFlywheelDetail,
  DataFlywheelSample,
  DataFlywheelSessionReview,
  DailyReviewInboxResponse,
  ReviewIssueChainDetail,
} from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  addSampleLabel: vi.fn(),
  createCaseDraft: vi.fn(),
  createRepairPack: vi.fn(),
  exportSampleJsonl: vi.fn(),
  getDailyReviewInbox: vi.fn(),
  getSampleDetail: vi.fn(),
  getReviewIssueChain: vi.fn(),
  getSessionReview: vi.fn(),
  listRepairPackCandidates: vi.fn(),
  listDataFlywheelSamples: vi.fn(),
  markBadCase: vi.fn(),
  markRepairPackResolved: vi.fn(),
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

const dailyReviewInbox: DailyReviewInboxResponse = {
  items: [
    {
      session_id: 'session-a',
      session_card: {
        session_id: 'session-a',
        summary: '我的工人',
        latest_turn_id: 3,
        risk_score: 0.7,
        severity: 'P1',
      },
      highest_risk_chain: {
        chain_id: 'chain:1:session-a:3',
        session_id: 'session-a',
        trigger_turn_id: 3,
        context_turn_ids: [],
        result_turn_ids: [],
        status: 'ready_for_review',
        severity: 'P1',
        dominant_signal: 'rule',
        diagnosis: {
          title: 'risk_turn',
          summary: '风险 turn',
          suggested_labels: ['bad_reply'],
        },
        ai_judge: {},
        human_review: {
          status: 'unreviewed',
          labels: [],
          quality_labels: [],
          expected_behavior: null,
          root_cause: null,
        },
        regression: {},
        repair: {},
      },
      candidate_chain_count: 1,
      evidence_status: 'ready_for_review',
      next_action: 'review_chain',
      status: 'ready_for_review',
      dominant_signal: 'rule',
      updated_at: '2026-06-11T08:00:00Z',
    },
  ],
  total: 1,
};

const reviewChainDetail: ReviewIssueChainDetail = {
  chain: dailyReviewInbox.items[0].highest_risk_chain,
  session_id: 'session-a',
  timeline: [
    {
      turn_id: 3,
      request_id: 'req:abc',
      user_input_preview: '我的工人',
      assistant_reply_preview: '当前可查的工人列表如下。',
      messages: detail.messages,
      selected_tools: ['worker.search'],
      tool_events: [],
      pending_lifecycle: [],
      router_decision: { selected_tools: ['worker.search'] },
      source: detail.source,
      event_log_status: 'available',
      chain_role: 'trigger',
    },
  ],
  trigger_turn: null,
  context_turns: [],
  result_turns: [],
  turn_debug_summaries: {},
  evidence_checklist: [{ key: 'event_log', status: 'present', turn_id: 3 }],
  evidence_status: 'ready_for_review',
  existing_labels: [],
  ai_judge: {},
};

async function openAdvancedSearch() {
  fireEvent.click(screen.getByRole('tab', { name: /高级搜索/ }));
  await screen.findByRole('tab', { name: /样本队列/ });
  await screen.findByTestId('data-flywheel-workspace');
}

describe('DataFlywheel 可折叠布局', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listDataFlywheelSamples).mockResolvedValue({ items: [sample], total: 1 });
    vi.mocked(getDailyReviewInbox).mockResolvedValue(dailyReviewInbox);
    vi.mocked(getReviewIssueChain).mockResolvedValue(reviewChainDetail);
    vi.mocked(getSessionReview).mockResolvedValue(review);
    vi.mocked(getSampleDetail).mockResolvedValue(detail);
  });

  it('默认进入每日质检入口', async () => {
    render(<DataFlywheel />);

    expect(await screen.findByRole('tab', { name: /每日质检/ })).toHaveAttribute(
      'aria-selected',
      'true'
    );
    expect(screen.getByTestId('risk-session-session-a')).toBeInTheDocument();
  });

  it('顶部归档和右侧详情可以收起，让会话 turn 与详情形成两栏主体', async () => {
    render(<DataFlywheel />);

    await openAdvancedSearch();
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

    await openAdvancedSearch();

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

    await openAdvancedSearch();
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
