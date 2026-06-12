import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataFlywheel from './index';
import {
  addSampleLabel,
  createCaseDraft,
  getDataFlywheelSyncJob,
  getSampleDetail,
  getSessionReview,
  getSessionAnnotations,
  listDataFlywheelSamples,
  markBadCase,
  deleteSampleLabel,
  resolveSampleLabel,
  syncDataFlywheelSessions,
} from '../../api/dataFlywheel';
import type {
  DataFlywheelDetail,
  DataFlywheelSample,
  DataFlywheelSessionAnnotations,
  DataFlywheelSessionReview,
  DataFlywheelSyncJob,
} from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  addSampleLabel: vi.fn(),
  createCaseDraft: vi.fn(),
  exportSampleJsonl: vi.fn(),
  getDataFlywheelSyncJob: vi.fn(),
  getSampleDetail: vi.fn(),
  getSessionReview: vi.fn(),
  getSessionAnnotations: vi.fn(),
  listDataFlywheelSamples: vi.fn(),
  markBadCase: vi.fn(),
  deleteSampleLabel: vi.fn(),
  resolveSampleLabel: vi.fn(),
  syncDataFlywheelSessions: vi.fn(),
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
  issue_candidates: [
    {
      type: 'sensitive_info_leak',
      severity: 'critical',
      reason: '回复疑似暴露模型参数或系统提示',
      evidence: 'temperature',
      suggested_label: 'sensitive_info_leak',
    },
  ],
  token_total: 680,
  latency_ms: 920,
  source_type: 'debug_event',
  created_at: '2026-06-11T08:00:00Z',
};

const anotherSample: DataFlywheelSample = {
  ...sample,
  sample_id: 'turn:session-b:4',
  session_id: 'session-b',
  turn_id: 4,
  request_id: 'req:def',
  user_input_preview: '给李四补一条今天的浇水记录',
  assistant_reply_preview: '我来记录今天的浇水作业。',
  issue_candidates: [],
  token_total: 420,
};

const sessionSecondSample: DataFlywheelSample = {
  ...sample,
  sample_id: 'turn:session-a:4',
  turn_id: 4,
  request_id: 'req:confirm',
  user_input_preview: '确认',
  assistant_reply_preview: '已创建作业。',
  selected_tools: ['create_operation_work_order'],
  actual_tools: ['create_operation_work_order'],
  issue_candidates: [
    {
      type: 'hallucinated_execution',
      severity: 'high',
      reason: '回复声称已执行写入，但没有对应工具成功事件',
      evidence: '已创建作业',
      suggested_label: 'hallucinated_execution',
    },
  ],
};

const sessionMessages = [
  { role: 'user', content: '帮我查一下张三这个月工资有没有漏记' },
  { role: 'assistant', content: '张三本月工资记录里缺少 6 月 8 日。' },
];
const confirmMessages = [
  { role: 'user', content: '确认' },
  { role: 'assistant', content: '已创建作业。' },
];
const anotherMessages = [
  { role: 'user', content: '给李四补一条今天的浇水记录' },
  { role: 'assistant', content: '已为李四记录今天的浇水作业。' },
];

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
  messages: sessionMessages,
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
      event_type: 'pending.plan.created',
      at: '2026-06-11T08:00:01Z',
      payload: { skill: 'wage.list' },
    },
  ],
  issue_candidates: sample.issue_candidates,
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

const missingEventSample: DataFlywheelSample = {
  ...sample,
  sample_id: 'turn:session-missing:5',
  session_id: 'session-missing',
  turn_id: 5,
  request_id: 'req:missing',
  user_input_preview: '今天的天气怎么样',
  assistant_reply_preview: '今天晴，适合巡田。',
  selected_tools: [],
  actual_tools: [],
  issue_candidates: [],
  source_type: 'missing_event_log',
  event_log_status: 'missing',
  chat_record_source: 'mysql_conversation_messages',
};

const missingEventDetail: DataFlywheelDetail = {
  ...detail,
  sample: missingEventSample,
  messages: [
    { role: 'user', content: '今天的天气怎么样' },
    { role: 'assistant', content: '今天晴，适合巡田。' },
  ],
  router_decision: {},
  tool_events: [],
  pending_lifecycle: [],
  issue_candidates: [],
  source: {
    event_file: 'data/agent-events/dt=2026-06-11/farm_id=2/session_id=session-missing/events.jsonl',
    event_seq_start: 1,
    event_seq_end: 2,
    event_log_status: 'missing',
    chat_record_source: 'mysql_conversation_messages',
  },
};

const anotherDetail: DataFlywheelDetail = {
  ...detail,
  sample: anotherSample,
  labels: [
    {
      id: 4,
      sample_id: anotherSample.sample_id,
      label: 'bad_reply',
      comment: '第二条样本备注',
      annotator_id: 'admin',
      sample_type: 'turn',
      session_id: 'session-b',
      turn_id: 4,
      request_id: 'req:def',
    },
  ],
  messages: anotherMessages,
  issue_candidates: [],
  debug_export: {
    sample_id: anotherSample.sample_id,
    request_id: 'req:def',
  },
};

const sessionReview: DataFlywheelSessionReview = {
  session_id: 'session-a',
  turns: [
    {
      sample,
      messages: sessionMessages,
      router_decision: {
        selected_tools: ['worker.search', 'wage.list'],
        reason: '需要核对工资流水',
      },
      tool_events: [
        {
          event_type: 'tool.call.finished',
          payload: { tool_name: 'worker.search', result: { id: 1 } },
        },
      ],
      pending_lifecycle: [
        {
          event_type: 'pending.plan.created',
          at: '2026-06-11T08:00:01Z',
          payload: { skill: 'wage.list' },
        },
      ],
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 11,
        event_seq_end: 18,
      },
    },
    {
      sample: sessionSecondSample,
      messages: confirmMessages,
      router_decision: {
        selected_tools: ['create_operation_work_order'],
      },
      tool_events: [
        {
          event_type: 'tool.call.finished',
          payload: { tool_name: 'create_operation_work_order', result: { id: 8 } },
        },
      ],
      pending_lifecycle: [],
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 19,
        event_seq_end: 24,
      },
    },
  ],
};

const anotherSessionReview: DataFlywheelSessionReview = {
  session_id: 'session-b',
  turns: [
    {
      sample: anotherSample,
      messages: anotherMessages,
      router_decision: {
        selected_tools: ['create_operation_work_order'],
      },
      tool_events: [],
      pending_lifecycle: [],
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 25,
        event_seq_end: 28,
      },
    },
  ],
};

const missingEventSessionReview: DataFlywheelSessionReview = {
  session_id: 'session-missing',
  turns: [
    {
      sample: missingEventSample,
      messages: missingEventDetail.messages,
      router_decision: {},
      tool_events: [],
      pending_lifecycle: [],
      source: missingEventDetail.source,
    },
  ],
};

const sessionAnnotations: DataFlywheelSessionAnnotations = {
  sample_id: 'session:1:session-a',
  sample_type: 'session',
  session_id: 'session-a',
  quality_labels: [],
  labels: [],
};

const mockedList = vi.mocked(listDataFlywheelSamples);
const mockedDetail = vi.mocked(getSampleDetail);
const mockedSessionReview = vi.mocked(getSessionReview);
const mockedSessionAnnotations = vi.mocked(getSessionAnnotations);
const mockedSyncSessions = vi.mocked(syncDataFlywheelSessions);
const mockedSyncJob = vi.mocked(getDataFlywheelSyncJob);
const mockedAddLabel = vi.mocked(addSampleLabel);
const mockedCreateDraft = vi.mocked(createCaseDraft);
const mockedMarkBadCase = vi.mocked(markBadCase);
const mockedDeleteLabel = vi.mocked(deleteSampleLabel);
const mockedResolveLabel = vi.mocked(resolveSampleLabel);

describe('DataFlywheel 页面', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    mockedList.mockResolvedValue({ items: [sample], total: 1 });
    mockedDetail.mockResolvedValue(detail);
    mockedSessionReview.mockImplementation((sessionId) =>
      Promise.resolve(sessionId === 'session-b' ? anotherSessionReview : sessionReview)
    );
    mockedSessionAnnotations.mockResolvedValue(sessionAnnotations);
    mockedSyncSessions.mockResolvedValue({
      job_id: 'session-sync-1',
      status: 'queued',
      mode: 'background',
      session_id: 'session-a',
      result: null,
      error: null,
    });
    mockedSyncJob.mockResolvedValue({
      job_id: 'session-sync-1',
      status: 'completed',
      mode: 'background',
      session_id: 'session-a',
      result: { synced_turns: 2 },
      error: null,
    } as DataFlywheelSyncJob);
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
    mockedDeleteLabel.mockResolvedValue({ deleted: true, id: 1 });
    mockedResolveLabel.mockResolvedValue({
      id: 1,
      sample_id: sample.sample_id,
      label: 'good_reply',
      comment: '初始备注',
      annotator_id: 'admin',
      status: 'resolved',
    });
  });

  it('初次渲染显示标题、样本输入摘要、request_id 和 token 数', async () => {
    render(<DataFlywheel />);

    expect(await screen.findByText('Agent 数据飞轮')).toBeInTheDocument();
    expect(screen.getByText('帮我查一下张三这个月工资有没有漏记')).toBeInTheDocument();
    expect(screen.getByText('req:abc')).toBeInTheDocument();
    expect(screen.getByText('680 tokens')).toBeInTheDocument();
    expect(screen.getAllByText('规则：参数/提示泄露').length).toBeGreaterThan(0);
    expect(screen.getByText('规则候选')).toBeInTheDocument();
    expect(screen.getByText('已标注问题')).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole('tab', { name: /pending lifecycle/ }));
    expect(screen.getByText('pending.plan.created')).toBeInTheDocument();
  });

  it('输入搜索框不会立刻重新请求，点击查询后才使用通用 q 搜索', async () => {
    const user = userEvent.setup();
    render(<DataFlywheel />);

    await screen.findByText('帮我查一下张三这个月工资有没有漏记');
    expect(mockedList).toHaveBeenCalledTimes(1);

    await user.type(screen.getByPlaceholderText('Session / Request ID'), 'req:new');
    expect(mockedList).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: /查询/ }));

    await waitFor(() => {
      expect(mockedList).toHaveBeenCalledTimes(2);
    });
    expect(mockedList).toHaveBeenLastCalledWith({
      limit: 50,
      offset: 0,
      label: undefined,
      unannotated_only: undefined,
      q: 'req:new',
    });
  });

  it('点击问题候选后只显示有候选问题的样本', async () => {
    const cleanSample: DataFlywheelSample = {
      ...anotherSample,
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sample, cleanSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-issues'));

    expect(screen.getByTestId('sample-row-turn:session-a:3')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-row-turn:session-b:4')).not.toBeInTheDocument();
    expect(screen.getByText('规则候选：回复疑似暴露模型参数或系统提示')).toBeInTheDocument();
  });

  it('点击已标注问题后按会话归档显示人工确认的问题', async () => {
    const confirmedBadSample: DataFlywheelSample = {
      ...anotherSample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    const cleanSample: DataFlywheelSample = {
      ...sample,
      sample_id: 'turn:session-c:5',
      session_id: 'session-c',
      turn_id: 5,
      request_id: 'req:clean',
      user_input_preview: '查询今日天气',
      quality_labels: ['good_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sample, confirmedBadSample, cleanSample], total: 3 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));

    expect(screen.getByText('问题会话归档')).toBeInTheDocument();
    expect(screen.getByTestId('problem-session-session-b')).toBeInTheDocument();
    expect(screen.queryByTestId('problem-session-session-a')).not.toBeInTheDocument();
    expect(screen.queryByTestId('problem-session-session-c')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('problem-session-session-b'));

    await waitFor(() => {
      expect(mockedSessionReview).toHaveBeenCalledWith('session-b');
    });
    expect(screen.getByText('完整对话记录')).toBeInTheDocument();
  });

  it('从问题会话归档进入时优先打开已标注的问题 turn', async () => {
    const confirmedBadSample: DataFlywheelSample = {
      ...anotherSample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sample, confirmedBadSample], total: 2 });
    mockedDetail.mockResolvedValue(anotherDetail);
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));
    fireEvent.click(screen.getByTestId('problem-session-session-b'));

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(confirmedBadSample.sample_id);
    });
    expect(screen.getByText('质量标签 · turn #4')).toBeInTheDocument();
    expect(screen.getAllByText('第二条样本备注').length).toBeGreaterThan(0);
  });

  it('点击已标注问题后会按单个会话归档显示会话级问题标注', async () => {
    const sessionLevelBadSample: DataFlywheelSample = {
      ...sample,
      quality_labels: [],
      annotation_status: 'unlabeled',
      session_quality_labels: ['needs_regression'],
      session_annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sessionLevelBadSample], total: 1 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));

    expect(screen.getByText('问题会话归档')).toBeInTheDocument();
    expect(screen.getByTestId('problem-session-session-a')).toBeInTheDocument();
    expect(screen.getAllByText('1 bad').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('sample-row-turn:session-a:3')).not.toBeInTheDocument();
  });

  it('快速切换样本时旧详情响应不会覆盖新详情', async () => {
    let resolveFirstDetail: (value: DataFlywheelDetail) => void = () => undefined;
    let resolveSecondDetail: (value: DataFlywheelDetail) => void = () => undefined;
    mockedList.mockResolvedValue({ items: [sample, anotherSample], total: 2 });
    mockedDetail
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveFirstDetail = resolve;
      }))
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveSecondDetail = resolve;
      }));

    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    fireEvent.click(await screen.findByTestId('sample-row-turn:session-b:4'));

    await act(async () => {
      resolveSecondDetail(anotherDetail);
    });
    expect(await screen.findByText('已为李四记录今天的浇水作业。')).toBeInTheDocument();

    await act(async () => {
      resolveFirstDetail(detail);
    });
    await waitFor(() => {
      expect(screen.queryByText('张三本月工资记录里缺少 6 月 8 日。')).not.toBeInTheDocument();
    });
    expect(screen.getByText('已为李四记录今天的浇水作业。')).toBeInTheDocument();
  });

  it('点击会话归档会进入完整对话审阅视图', async () => {
    mockedList.mockResolvedValue({ items: [sample, anotherSample], total: 2 });
    render(<DataFlywheel />);

    expect(await screen.findByText('session-a')).toBeInTheDocument();
    expect(screen.getByText('session-b')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('archive-session-session-b'));

    await waitFor(() => {
      expect(mockedSessionReview).toHaveBeenCalledWith('session-b');
    });
    expect(screen.getByText('完整对话记录')).toBeInTheDocument();
  });

  it('点击会话归档后显示完整对话和 skill、pending、tool 证据', async () => {
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample, anotherSample], total: 3 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));

    await waitFor(() => {
      expect(mockedSessionReview).toHaveBeenCalledWith('session-a');
    });
    expect(await screen.findByText('完整对话记录')).toBeInTheDocument();
    expect(screen.getByText('帮我查一下张三这个月工资有没有漏记')).toBeInTheDocument();
    expect(screen.getByText('张三本月工资记录里缺少 6 月 8 日。')).toBeInTheDocument();
    expect(screen.getByText('selected: worker.search, wage.list')).toBeInTheDocument();
    expect(screen.getByText('actual: worker.search')).toBeInTheDocument();
    expect(screen.getByText('pending: 已创建')).toBeInTheDocument();
    expect(screen.getAllByText('tool: 1 success / 0 failed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('规则：幻觉执行').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId('review-select-turn:session-a:4'));

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(sessionSecondSample.sample_id);
    });
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

  it('在完整会话中保存标注后刷新 session 审阅流', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');
    fireEvent.click(screen.getByTestId('review-select-turn:session-a:4'));
    await screen.findByText('样本详情');

    await user.click(screen.getByLabelText('坏回复'));
    await user.click(screen.getByRole('button', { name: /保存标注/ }));

    await waitFor(() => {
      expect(mockedSessionReview).toHaveBeenCalledTimes(2);
    });
    expect(mockedSessionReview).toHaveBeenLastCalledWith('session-a');
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

  it('在会话归档视图点击同步会话后同步当前 session 并刷新列表与会话审阅', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');

    await user.click(screen.getByRole('button', { name: /同步会话/ }));

    await waitFor(() => {
      expect(mockedSyncSessions).toHaveBeenCalledWith({
        session_id: 'session-a',
        only_missing: true,
        limit: 100,
      });
    });
    expect(mockedSyncJob).toHaveBeenCalledWith('session-sync-1');
    expect(mockedList).toHaveBeenCalledTimes(2);
    expect(mockedSessionReview).toHaveBeenCalledTimes(2);
  });

  it('事件 JSONL 缺失时明确提示聊天来自 MySQL 且可同步重建', async () => {
    mockedList.mockResolvedValue({ items: [missingEventSample], total: 1 });
    mockedDetail.mockResolvedValue(missingEventDetail);
    mockedSessionReview.mockResolvedValue(missingEventSessionReview);
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('archive-session-session-missing'));

    expect(await screen.findByText('完整对话记录')).toBeInTheDocument();
    expect(screen.getAllByText('聊天记录：MySQL').length).toBeGreaterThan(0);
    expect(screen.getAllByText('事件文件缺失，可同步重建').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId('review-select-turn:session-missing:5'));

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(missingEventSample.sample_id);
    });
    expect(screen.getByText('聊天记录来源')).toBeInTheDocument();
    expect(screen.getByText('MySQL conversation_messages')).toBeInTheDocument();
    expect(screen.getByText('事件证据状态')).toBeInTheDocument();
    expect(screen.getByText('缺失，可点击“同步会话”重建基础事件')).toBeInTheDocument();
  });

  it('可以对完整会话保存会话级标注', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');
    await user.click(screen.getByRole('button', { name: /标注整个会话/ }));

    await user.click(screen.getByLabelText('需要回归'));
    const commentBox = screen.getByPlaceholderText('记录判断依据、复现条件或后续处理建议');
    await user.clear(commentBox);
    await user.type(commentBox, '整段会话需要回归');
    await user.click(screen.getByRole('button', { name: /保存标注/ }));

    await waitFor(() => {
      expect(mockedAddLabel).toHaveBeenCalledWith('session:1:session-a', {
        label: 'needs_regression',
        comment: '整段会话需要回归',
        sample_type: 'session',
        session_id: 'session-a',
      });
    });
  });

  it('加载完整会话标注后左侧归档会显示会话级问题', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    mockedSessionAnnotations.mockResolvedValue({
      sample_id: 'session:1:session-a',
      sample_type: 'session',
      session_id: 'session-a',
      quality_labels: ['sensitive_info_leak'],
      labels: [
        {
          id: 9,
          sample_id: 'session:1:session-a',
          sample_type: 'session',
          session_id: 'session-a',
          turn_id: null,
          request_id: null,
          label: 'sensitive_info_leak',
          comment: '错误的 json 泄漏判断',
          annotator_id: 'admin',
          status: 'open',
        },
      ],
    });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');
    await user.click(screen.getByRole('button', { name: /标注整个会话/ }));

    expect(await screen.findByText('1 会话标注')).toBeInTheDocument();
    expect(screen.getByText('1 bad')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));

    expect(screen.getByTestId('problem-session-session-a')).toBeInTheDocument();
  });

  it('从问题会话归档进入后可以将完整会话标注标记为已完成', async () => {
    const user = userEvent.setup();
    const sessionLevelBadSample: DataFlywheelSample = {
      ...sample,
      quality_labels: [],
      annotation_status: 'unlabeled',
      session_quality_labels: ['sensitive_info_leak'],
      session_annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sessionLevelBadSample, sessionSecondSample], total: 2 });
    mockedSessionAnnotations.mockResolvedValue({
      sample_id: 'session:1:session-a',
      sample_type: 'session',
      session_id: 'session-a',
      quality_labels: ['sensitive_info_leak'],
      labels: [
        {
          id: 9,
          sample_id: 'session:1:session-a',
          sample_type: 'session',
          session_id: 'session-a',
          turn_id: null,
          request_id: null,
          label: 'sensitive_info_leak',
          comment: '错误的 json 泄漏判断',
          annotator_id: 'admin',
          status: 'open',
        },
      ],
    });
    mockedResolveLabel.mockResolvedValue({
      id: 9,
      sample_id: 'session:1:session-a',
      sample_type: 'session',
      session_id: 'session-a',
      turn_id: null,
      request_id: null,
      label: 'sensitive_info_leak',
      comment: '错误的 json 泄漏判断',
      annotator_id: 'admin',
      status: 'resolved',
    });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));
    fireEvent.click(screen.getByTestId('problem-session-session-a'));
    await screen.findByText('完整对话记录');
    await waitFor(() => {
      expect(mockedSessionAnnotations).toHaveBeenCalledWith('session-a');
    });
    expect(screen.getAllByText('错误的 json 泄漏判断').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: /标记已完成 sensitive_info_leak/ }));

    await waitFor(() => {
      expect(mockedResolveLabel).toHaveBeenCalledWith('session:1:session-a', 9);
    });
  });

  it('可以删除已有标注并刷新当前样本', async () => {
    const user = userEvent.setup();
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await screen.findByText('样本详情');
    await user.click(screen.getByRole('button', { name: /删除标注 good_reply/ }));

    await waitFor(() => {
      expect(mockedDeleteLabel).toHaveBeenCalledWith(sample.sample_id, 1);
    });
    expect(mockedDetail).toHaveBeenCalledTimes(2);
  });

  it('可以将已有标注标记为已完成并刷新当前样本', async () => {
    const user = userEvent.setup();
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await screen.findByText('样本详情');
    await user.click(screen.getByRole('button', { name: /标记已完成 good_reply/ }));

    await waitFor(() => {
      expect(mockedResolveLabel).toHaveBeenCalledWith(sample.sample_id, 1);
    });
    expect(mockedDetail).toHaveBeenCalledTimes(2);
  });
});
