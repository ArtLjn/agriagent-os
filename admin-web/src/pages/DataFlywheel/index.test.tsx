import { act, fireEvent, render as rtlRender, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataFlywheel from './index';
import { getTraceDiagnostics } from '../../api/admin';
import type { TraceDiagnostics } from '../../api/admin';
import {
  acceptSamplePrelabel,
  addSampleLabel,
  createCaseDraft,
  createRepairPack,
  createSamplePrelabel,
  createSamplePrelabelBatch,
  getDailyReviewInbox,
  getDataFlywheelSyncJob,
  getSamplePrelabelBatchJob,
  getSampleDetail,
  getReviewIssueChain,
  getSessionReview,
  getSessionAnnotations,
  listRepairPackCandidates,
  listDataFlywheelSamples,
  markBadCase,
  deleteSampleLabel,
  rejectSamplePrelabel,
  resolveSampleLabel,
  saveReviewIssueChainReview,
  syncDataFlywheelSessions,
} from '../../api/dataFlywheel';
import type {
  DataFlywheelDetail,
  DailyReviewInboxResponse,
  DataFlywheelPrelabel,
  DataFlywheelRepairPack,
  DataFlywheelSample,
  DataFlywheelSessionAnnotations,
  DataFlywheelSessionReview,
  DataFlywheelSyncJob,
  ReviewIssueChainDetail,
} from '../../api/dataFlywheel';

vi.mock('../../api/dataFlywheel', () => ({
  acceptSamplePrelabel: vi.fn(),
  addSampleLabel: vi.fn(),
  createCaseDraft: vi.fn(),
  createRepairPack: vi.fn(),
  createSamplePrelabel: vi.fn(),
  createSamplePrelabelBatch: vi.fn(),
  discardRepairPack: vi.fn(),
  exportSampleJsonl: vi.fn(),
  getDailyReviewInbox: vi.fn(),
  getDataFlywheelSyncJob: vi.fn(),
  getSamplePrelabelBatchJob: vi.fn(),
  getSampleDetail: vi.fn(),
  getReviewIssueChain: vi.fn(),
  getSessionReview: vi.fn(),
  getSessionAnnotations: vi.fn(),
  listRepairPacks: vi.fn(),
  listRepairPackCandidates: vi.fn(),
  listDataFlywheelSamples: vi.fn(),
  markBadCase: vi.fn(),
  markRepairPackResolved: vi.fn(),
  rebuildRepairPack: vi.fn(),
  recordRepairPackVerificationFailure: vi.fn(),
  reopenRepairPack: vi.fn(),
  deleteSampleLabel: vi.fn(),
  rejectSamplePrelabel: vi.fn(),
  resolveSampleLabel: vi.fn(),
  saveReviewIssueChainReview: vi.fn(),
  syncDataFlywheelSessions: vi.fn(),
}));

vi.mock('../../api/admin', () => ({
  getTraceDiagnostics: vi.fn(),
}));

const render = (ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) => {
  const result = rtlRender(ui, options);
  const currentTestName = expect.getState().currentTestName ?? '';
  if (
    !currentTestName.includes('默认进入每日质检') &&
    !currentTestName.includes('高级搜索中保留旧样本检索入口')
  ) {
    fireEvent.click(screen.getByRole('tab', { name: /高级搜索/ }));
  }
  return result;
};

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
  risk_score: 0.88,
  rule_score: 0.88,
  risk_dominant_signal: 'rule',
  risk_severity: 'P0',
  rule_hits: ['sensitive_info_leak'],
  judge_bad_prob: 0.62,
  judge_issue_type: 'sensitive_info_leak',
  judge_suggested_label: 'sensitive_info_leak',
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
  prelabels: [],
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
const mockedInbox = vi.mocked(getDailyReviewInbox);
const mockedReviewChain = vi.mocked(getReviewIssueChain);
const mockedSaveReviewChain = vi.mocked(saveReviewIssueChainReview);
const mockedDetail = vi.mocked(getSampleDetail);
const mockedRepairCandidates = vi.mocked(listRepairPackCandidates);
const mockedSessionReview = vi.mocked(getSessionReview);
const mockedSessionAnnotations = vi.mocked(getSessionAnnotations);
const mockedSyncSessions = vi.mocked(syncDataFlywheelSessions);
const mockedSyncJob = vi.mocked(getDataFlywheelSyncJob);
const mockedPrelabelBatch = vi.mocked(createSamplePrelabelBatch);
const mockedPrelabelBatchJob = vi.mocked(getSamplePrelabelBatchJob);
const mockedAcceptPrelabel = vi.mocked(acceptSamplePrelabel);
const mockedAddLabel = vi.mocked(addSampleLabel);
const mockedCreateDraft = vi.mocked(createCaseDraft);
const mockedCreateRepairPack = vi.mocked(createRepairPack);
const mockedCreatePrelabel = vi.mocked(createSamplePrelabel);
const mockedMarkBadCase = vi.mocked(markBadCase);
const mockedDeleteLabel = vi.mocked(deleteSampleLabel);
const mockedRejectPrelabel = vi.mocked(rejectSamplePrelabel);
const mockedResolveLabel = vi.mocked(resolveSampleLabel);
const mockedTraceDiagnostics = vi.mocked(getTraceDiagnostics);

const reflectionDiagnostics: TraceDiagnostics = {
  request_id: 'req:abc',
  reflection_checks: [
    {
      trigger: 'pre_write_plan',
      decision: 'block_write',
      reason: '确认文案与待执行参数不一致。',
      checks: ['write_plan_consistency'],
      issues: [
        {
          code: 'confirmation_param_mismatch',
          severity: 'blocker',
          message: '确认文案中的对象与工具参数不一致。',
          evidence: { expected: '张三', actual: '李四' },
        },
      ],
      input: {
        tool_name: 'create_operation_work_order',
        tool_call_ids: ['call-1'],
        plan_id: 'plan-1',
        action_id: 'action-1',
      },
    },
  ],
  reflection_diagnostic: {
    blocked: true,
    decisions: ['block_write'],
    issue_codes: ['confirmation_param_mismatch'],
  },
};

const emptyReflectionDiagnostics = (requestId: string): TraceDiagnostics => ({
  request_id: requestId,
  reflection_checks: [],
  reflection_diagnostic: {
    blocked: false,
    decisions: [],
    issue_codes: [],
  },
});

const repairPack: DataFlywheelRepairPack = {
  id: 1,
  pack_id: 'repair-guardrail-abc123',
  fix_target: 'guardrail',
  labels: ['sensitive_info_leak'],
  source_sample_ids: [sample.sample_id, anotherSample.sample_id],
  source_label_ids: [1, 4],
  status: 'exported',
  export_path: 'data/repair-packs/repair-guardrail-abc123',
  manifest: {
    pack_id: 'repair-guardrail-abc123',
    fix_target: 'guardrail',
    verification_commands: ['pytest tests/services/test_data_flywheel_repair_pack_service.py -q'],
    warnings: [],
  },
  payload: {
    manifest: {
      pack_id: 'repair-guardrail-abc123',
      fix_target: 'guardrail',
      verification_commands: ['pytest tests/services/test_data_flywheel_repair_pack_service.py -q'],
      warnings: [],
    },
    cases_jsonl: [],
    readme: '# Repair Pack repair-guardrail-abc123',
    debug_files: {},
    regression_drafts: {},
  },
};

const reviewChainId = 'chain:1:session-a:3';
const nextReviewChainId = 'chain:1:session-b:4';

const dailyReviewInbox: DailyReviewInboxResponse = {
  items: [
    {
      session_id: 'session-a',
      session_card: {
        session_id: 'session-a',
        summary: '批量结算工资时参数范围被收窄',
        latest_turn_id: 4,
        risk_score: 0.92,
        severity: 'P0',
      },
      highest_risk_chain: {
        chain_id: reviewChainId,
        session_id: 'session-a',
        trigger_turn_id: 3,
        context_turn_ids: [1, 2],
        result_turn_ids: [4],
        status: 'ready_for_review',
        severity: 'P0',
        dominant_signal: 'judge',
        diagnosis: {
          title: 'tool_parameter_mismatch',
          summary: '确认执行时工具参数只保留了单个工人。',
          candidate_type: 'tool_parameter_mismatch',
          suggested_labels: ['wrong_tool_selection', 'needs_regression'],
        },
        ai_judge: {
          bad_prob: 0.91,
          issue_type: 'tool_parameter_mismatch',
          suggested_label: 'wrong_tool_selection',
          dominant_signal: 'judge',
        },
        human_review: {
          status: 'unreviewed',
          labels: [],
          quality_labels: [],
          expected_behavior: null,
          root_cause: null,
        },
        regression: {
          needs_regression: false,
          regression_ready: false,
          source_sample_id: sample.sample_id,
        },
        repair: {
          fix_target: 'router',
          regression_ready: false,
          export_blocked_reason: 'needs_human_review',
        },
      },
      candidate_chain_count: 2,
      evidence_status: 'ready_for_review',
      next_action: 'review_chain',
      status: 'ready_for_review',
      dominant_signal: 'judge',
      updated_at: '2026-06-11T08:00:00Z',
    },
  ],
  total: 1,
};

const refreshedDailyReviewInbox: DailyReviewInboxResponse = {
  items: [
    {
      session_id: 'session-b',
      session_card: {
        session_id: 'session-b',
        summary: '下一条风险链',
        latest_turn_id: 5,
        risk_score: 0.81,
        severity: 'P1',
      },
      highest_risk_chain: {
        ...dailyReviewInbox.items[0].highest_risk_chain,
        chain_id: nextReviewChainId,
        session_id: 'session-b',
        trigger_turn_id: 4,
        context_turn_ids: [3],
        result_turn_ids: [5],
        severity: 'P1',
      },
      candidate_chain_count: 1,
      evidence_status: 'ready_for_review',
      next_action: 'review_chain',
      status: 'ready_for_review',
      dominant_signal: 'rule',
      updated_at: '2026-06-11T08:10:00Z',
    },
  ],
  total: 1,
};

const reviewChainDetail: ReviewIssueChainDetail = {
  chain: dailyReviewInbox.items[0].highest_risk_chain,
  session_id: 'session-a',
  timeline: [
    {
      turn_id: 1,
      request_id: 'req:context',
      user_input_preview: '查一下张三和李四欠款',
      assistant_reply_preview: '张三和李四都有未结算工资。',
      messages: [
        { role: 'user', content: '查一下张三和李四欠款' },
        { role: 'assistant', content: '张三和李四都有未结算工资。' },
      ],
      selected_tools: ['wage.list'],
      tool_events: [],
      pending_lifecycle: [],
      router_decision: { selected_tools: ['wage.list'] },
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 1,
        event_seq_end: 4,
        event_log_status: 'available',
      },
      event_log_status: 'available',
      chain_role: 'context',
    },
    {
      turn_id: 3,
      request_id: 'req:abc',
      user_input_preview: '把这些欠款都结算掉',
      assistant_reply_preview: '我会为张三结算工资。',
      messages: sessionMessages,
      selected_tools: ['wage.batch_settle'],
      tool_events: [{ event_type: 'tool.call.finished', payload: { tool_name: 'wage.batch_settle' } }],
      pending_lifecycle: [{ event_type: 'pending.plan.created', at: '2026-06-11T08:00:01Z' }],
      router_decision: { selected_tools: ['wage.batch_settle'], args: { worker_id: 1 } },
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 11,
        event_seq_end: 18,
        event_log_status: 'available',
      },
      event_log_status: 'available',
      chain_role: 'trigger',
    },
    {
      turn_id: 4,
      request_id: 'req:confirm',
      user_input_preview: '确认',
      assistant_reply_preview: '已为张三结算。',
      messages: confirmMessages,
      selected_tools: ['wage.batch_settle'],
      tool_events: [{ event_type: 'tool.call.finished', payload: { tool_name: 'wage.batch_settle' } }],
      pending_lifecycle: [],
      router_decision: { selected_tools: ['wage.batch_settle'] },
      source: {
        event_file: 'events/debug.jsonl',
        event_seq_start: 19,
        event_seq_end: 24,
        event_log_status: 'available',
      },
      event_log_status: 'available',
      chain_role: 'result',
    },
  ],
  trigger_turn: null,
  context_turns: [],
  result_turns: [],
  turn_debug_summaries: {
    '3': {
      trace_debug_summary: {
        reflection: 'scope narrowed to one worker',
      },
    },
  },
  evidence_checklist: [
    { key: 'event_log', status: 'present', turn_id: 3 },
    { key: 'chat_messages', status: 'present', turn_id: 3 },
    { key: 'router_decision', status: 'present', turn_id: 3 },
    { key: 'tool_or_pending_evidence', status: 'needs_human', turn_id: 3 },
  ],
  evidence_status: 'ready_for_review',
  existing_labels: [],
  ai_judge: dailyReviewInbox.items[0].highest_risk_chain.ai_judge,
};

describe('DataFlywheel 页面', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    mockedList.mockResolvedValue({ items: [sample], total: 1 });
    mockedInbox.mockResolvedValue(dailyReviewInbox);
    mockedReviewChain.mockResolvedValue(reviewChainDetail);
    mockedSaveReviewChain.mockResolvedValue({
      chain: {
        ...dailyReviewInbox.items[0].highest_risk_chain,
        status: 'accepted',
        context_turn_ids: [1, 2],
        result_turn_ids: [4],
        human_review: {
          status: 'accepted',
          labels: [],
          quality_labels: ['needs_regression', 'wrong_tool_selection'],
          expected_behavior: '应保留张三和李四两个工人的批量结算范围',
          root_cause: '批量作用域被收窄为单人',
        },
        regression: {
          needs_regression: true,
          regression_ready: true,
          source_sample_id: sample.sample_id,
        },
        repair: {
          fix_target: 'router',
          regression_ready: true,
          export_blocked_reason: null,
        },
      },
    });
    mockedDetail.mockResolvedValue(detail);
    mockedRepairCandidates.mockResolvedValue({
      items: [
        {
          sample_id: sample.sample_id,
          session_id: sample.session_id,
          turn_id: sample.turn_id,
          request_id: sample.request_id,
          labels: ['sensitive_info_leak'],
          fix_target: 'guardrail',
          priority: 100,
          suggested_action: '修复敏感信息输出拦截、回复审查和安全边界测试。',
          regression_ready: true,
          verification_commands: ['pytest tests/services/test_data_flywheel_issue_detector.py -q'],
          secondary_targets: [],
        },
      ],
      total: 1,
    });
    mockedTraceDiagnostics.mockImplementation((requestId) =>
      Promise.resolve(
        requestId === 'req:abc'
          ? reflectionDiagnostics
          : emptyReflectionDiagnostics(requestId)
      )
    );
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
    mockedPrelabelBatch.mockResolvedValue({
      job_id: 'prelabel-batch-1',
      status: 'queued',
      mode: 'background',
      result: null,
      error: null,
    });
    mockedPrelabelBatchJob.mockResolvedValue({
      job_id: 'prelabel-batch-1',
      status: 'completed',
      mode: 'background',
      result: { total: 1, created: 1, skipped_existing: 0, failed: 0 },
      error: null,
    });
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
    mockedCreateRepairPack.mockResolvedValue(repairPack);
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

  it('默认进入每日质检，点击 session 加载最高风险链并提交审核 payload', async () => {
    mockedInbox
      .mockResolvedValueOnce(dailyReviewInbox)
      .mockResolvedValueOnce(refreshedDailyReviewInbox);
    render(<DataFlywheel />);

    expect(await screen.findByRole('tab', { name: /每日质检/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('批量结算工资时参数范围被收窄')).toBeInTheDocument();
    expect(screen.getByText('最高风险链')).toBeInTheDocument();
    expect(screen.getAllByText('P0').length).toBeGreaterThan(0);
    expect(screen.getByText('候选链 2')).toBeInTheDocument();
    expect(screen.getAllByText('ready_for_review').length).toBeGreaterThan(0);
    expect(screen.getAllByText('judge').length).toBeGreaterThan(0);
    expect(screen.getByText('review_chain')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('risk-session-session-a'));

    await waitFor(() => {
      expect(mockedReviewChain).toHaveBeenCalledWith(reviewChainId);
    });
    expect(await screen.findByText((content) => content.includes('把这些欠款都结算掉'))).toBeInTheDocument();
    const triggerArticle = document.querySelector('#turn-3');
    expect(triggerArticle).not.toBeNull();
    expect(screen.getAllByRole('link', { name: /turn #3/ })[0]).toHaveAttribute('href', '#turn-3');

    fireEvent.click(within(triggerArticle as HTMLElement).getAllByRole('button', { name: /展开详情/ })[0]);
    expect(await within(triggerArticle as HTMLElement).findByText('trace_debug_summary')).toBeInTheDocument();
    expect(
      within(triggerArticle as HTMLElement).getByText((content) => content.includes('scope narrowed to one worker'))
    ).toBeInTheDocument();
    const contextArticle = document.querySelector('#turn-1') as HTMLElement;
    expect(contextArticle).not.toBeNull();
    const contextCheckbox = within(contextArticle).getByRole('checkbox', { name: 'context' });
    const resultCheckbox = within(contextArticle).getByRole('checkbox', { name: 'result' });
    expect(contextCheckbox).toBeChecked();
    fireEvent.click(resultCheckbox);
    expect(resultCheckbox).toBeChecked();
    expect(contextCheckbox).not.toBeChecked();

    fireEvent.click(screen.getByLabelText('采纳坏例'));
    fireEvent.change(screen.getByLabelText('Root cause'), { target: { value: '批量作用域被收窄为单人' } });
    fireEvent.change(screen.getByLabelText('Expected behavior'), {
      target: { value: '应保留张三和李四两个工人的批量结算范围' },
    });
    fireEvent.click(screen.getByLabelText('needs_regression'));
    fireEvent.click(screen.getByLabelText('wrong_tool_selection'));
    fireEvent.click(screen.getByRole('button', { name: /保存并下一条/ }));

    await waitFor(() => {
      expect(mockedSaveReviewChain).toHaveBeenCalledWith(reviewChainId, {
        status: 'accepted',
        context_turn_ids: [2],
        result_turn_ids: [1, 4],
        final_labels: ['needs_regression', 'wrong_tool_selection'],
        root_cause: '批量作用域被收窄为单人',
        expected_behavior: '应保留张三和李四两个工人的批量结算范围',
        false_positive_reason: undefined,
        missing_evidence: undefined,
      });
    });
    expect(mockedInbox).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 50, offset: 0 }));
    await waitFor(() => {
      expect(mockedReviewChain).toHaveBeenCalledWith(nextReviewChainId);
    });
  }, 15000);

  it('高级搜索中保留旧样本检索入口', async () => {
    render(<DataFlywheel />);

    await screen.findByText('批量结算工资时参数范围被收窄');
    fireEvent.click(screen.getByRole('tab', { name: /高级搜索/ }));

    expect(await screen.findByRole('tab', { name: /样本队列/ })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Session / Request ID')).toBeInTheDocument();
    expect(screen.getByText('帮我查一下张三这个月工资有没有漏记')).toBeInTheDocument();
  }, 15000);

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
    expect(mockedRepairCandidates).toHaveBeenCalledWith({
      sample_ids: [sample.sample_id],
      limit: 1,
    });
    expect(await screen.findByText('样本详情')).toBeInTheDocument();
    expect(screen.getByText('修复候选')).toBeInTheDocument();
    expect(screen.getByText('guardrail')).toBeInTheDocument();
    expect(screen.getByText('优先级 100')).toBeInTheDocument();
    expect(screen.getByText('可回归')).toBeInTheDocument();
    expect(screen.getAllByText('selected_tools').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('tab', { name: /pending lifecycle/ }));
    expect(screen.getByText('pending.plan.created')).toBeInTheDocument();
  });

  it('批量导出修复包只使用已标注问题列表，不使用用户会话勾选', async () => {
    const confirmedBadSample: DataFlywheelSample = {
      ...anotherSample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sample, confirmedBadSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    await userEvent.click(screen.getByTestId('archive-confirmed-issues'));
    await userEvent.click(screen.getByRole('checkbox', { name: /选择问题会话 session-b/ }));
    await userEvent.click(screen.getByRole('button', { name: '批量导出修复包' }));

    await waitFor(() => {
      expect(mockedCreateRepairPack).toHaveBeenCalledWith({
        sample_ids: [confirmedBadSample.sample_id],
        limit: 1,
      });
    });
    expect(await screen.findByText('repair-guardrail-abc123')).toBeInTheDocument();
  });

  it('已标注问题列表支持勾选问题会话后批量导出', async () => {
    const user = userEvent.setup();
    const confirmedBadSample: DataFlywheelSample = {
      ...anotherSample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [sample, confirmedBadSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    await user.click(screen.getByTestId('archive-confirmed-issues'));

    expect(screen.getByRole('button', { name: '批量导出修复包' })).toBeDisabled();

    await user.click(screen.getByRole('checkbox', { name: /选择问题会话 session-b/ }));
    const exportButton = screen.getByRole('button', { name: '批量导出修复包' });
    expect(exportButton).toHaveTextContent('批量导出修复包 1');
    expect(exportButton).toBeEnabled();
    await user.click(exportButton);

    await waitFor(() => {
      expect(mockedCreateRepairPack).toHaveBeenCalledWith({
        sample_ids: [confirmedBadSample.sample_id],
        limit: 1,
      });
    });
  });

  it('已标注问题列表支持全选问题会话后批量导出', async () => {
    const user = userEvent.setup();
    const firstProblemSample: DataFlywheelSample = {
      ...sample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    const secondProblemSample: DataFlywheelSample = {
      ...anotherSample,
      quality_labels: ['wrong_tool_selection'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [firstProblemSample, secondProblemSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    await user.click(screen.getByTestId('archive-confirmed-issues'));

    await user.click(screen.getByRole('checkbox', { name: '全选问题会话' }));
    const exportButton = screen.getByRole('button', { name: '批量导出修复包' });
    expect(exportButton).toHaveTextContent('批量导出修复包 2');
    await user.click(exportButton);

    await waitFor(() => {
      expect(mockedCreateRepairPack).toHaveBeenCalledWith({
        sample_ids: [firstProblemSample.sample_id, secondProblemSample.sample_id],
        limit: 2,
      });
    });
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
    expect(mockedList).toHaveBeenLastCalledWith(
      expect.objectContaining({
        limit: 50,
        offset: 0,
        label: undefined,
        unannotated_only: undefined,
        q: 'req:new',
      })
    );
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

  it('同一问题会话有多个已标注 turn 时右侧展示并可切换', async () => {
    const user = userEvent.setup();
    const scrolledElements: Element[] = [];
    const scrollIntoView = vi.fn(function (this: Element) {
      scrolledElements.push(this);
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });
    const firstProblemSample: DataFlywheelSample = {
      ...sample,
      quality_labels: ['bad_reply'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    const secondProblemSample: DataFlywheelSample = {
      ...sessionSecondSample,
      quality_labels: ['hallucinated_execution'],
      annotation_status: 'labeled',
      issue_candidates: [],
    };
    mockedList.mockResolvedValue({ items: [firstProblemSample, secondProblemSample], total: 2 });
    mockedDetail.mockImplementation((sampleId) => {
      if (sampleId === secondProblemSample.sample_id) {
        return Promise.resolve({
          ...detail,
          sample: secondProblemSample,
          quality_labels: ['hallucinated_execution'],
          labels: [
            {
              id: 8,
              sample_id: secondProblemSample.sample_id,
              label: 'hallucinated_execution',
              comment: '确认时幻觉执行',
              annotator_id: 'admin',
              sample_type: 'turn',
              session_id: 'session-a',
              turn_id: 4,
              request_id: 'req:confirm',
            },
          ],
        });
      }
      return Promise.resolve({
        ...detail,
        sample: firstProblemSample,
        quality_labels: ['bad_reply'],
        labels: [
          {
            id: 7,
            sample_id: firstProblemSample.sample_id,
            label: 'bad_reply',
            comment: '查询工人答错',
            annotator_id: 'admin',
            sample_type: 'turn',
            session_id: 'session-a',
            turn_id: 3,
            request_id: 'req:abc',
          },
        ],
      });
    });
    render(<DataFlywheel />);

    await screen.findByTestId('sample-row-turn:session-a:3');
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));
    fireEvent.click(screen.getByTestId('problem-session-session-a'));

    expect(await screen.findByText('本会话问题标注')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /查看问题标注 turn #4/ })).toHaveTextContent('#4');
    expect(screen.getByRole('button', { name: /查看问题标注 turn #3/ })).toHaveTextContent('#3');

    scrollIntoView.mockClear();
    scrolledElements.length = 0;
    await user.click(screen.getByRole('button', { name: /查看问题标注 turn #3/ }));

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(firstProblemSample.sample_id);
    });
    expect(screen.getAllByText('查询工人答错').length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(scrollIntoView).toHaveBeenCalled();
    });
    expect(scrolledElements.at(-1)?.getAttribute('data-testid')).toBe('session-turn-turn:session-a:3');
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
    expect((await screen.findAllByText('已为李四记录今天的浇水作业。')).length).toBeGreaterThan(0);

    await act(async () => {
      resolveFirstDetail(detail);
    });
    await waitFor(() => {
      expect(screen.queryAllByText('张三本月工资记录里缺少 6 月 8 日。')).toHaveLength(0);
    });
    expect(screen.getAllByText('已为李四记录今天的浇水作业。').length).toBeGreaterThan(0);
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
    expect(screen.getAllByText('张三本月工资记录里缺少 6 月 8 日。').length).toBeGreaterThan(0);
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

  it('完整会话中展示 Reflection summary、检查明细和关联 input', async () => {
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));

    await waitFor(() => {
      expect(mockedTraceDiagnostics).toHaveBeenCalledWith('req:abc');
    });
    expect(await screen.findByText('blocked: 是')).toBeInTheDocument();
    expect(screen.getAllByText('decision: block_write').length).toBeGreaterThan(0);
    expect(screen.getByText('issue: confirmation_param_mismatch')).toBeInTheDocument();
    expect(screen.getByText('trigger: pre_write_plan')).toBeInTheDocument();
    expect(screen.getByText('check: write_plan_consistency')).toBeInTheDocument();
    expect(screen.getByText('reason: 确认文案与待执行参数不一致。')).toBeInTheDocument();
    expect(screen.getByText('code: confirmation_param_mismatch')).toBeInTheDocument();
    expect(screen.getByText('message: 确认文案中的对象与工具参数不一致。')).toBeInTheDocument();
    expect(screen.getByText('tool_name: create_operation_work_order')).toBeInTheDocument();
    expect(screen.getByText('tool_call_ids: call-1')).toBeInTheDocument();
    expect(screen.getByText('plan_id: plan-1')).toBeInTheDocument();
    expect(screen.getByText('action_id: action-1')).toBeInTheDocument();
  });

  it('没有 Reflection checks 的 trace 展示空状态', async () => {
    mockedList.mockResolvedValue({ items: [anotherSample], total: 1 });
    render(<DataFlywheel />);

    await screen.findByText('session-b');
    fireEvent.click(screen.getByTestId('archive-session-session-b'));

    await waitFor(() => {
      expect(mockedTraceDiagnostics).toHaveBeenCalledWith('req:def');
    });
    expect(await screen.findByText('暂无 Reflection 检查')).toBeInTheDocument();
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

  it('点击批量 AI 分析会按当前筛选创建预判任务并刷新列表', async () => {
    const user = userEvent.setup();
    render(<DataFlywheel />);

    await screen.findByText('帮我查一下张三这个月工资有没有漏记');
    await user.type(screen.getByPlaceholderText('Session / Request ID'), 'req:abc');
    await user.click(screen.getByLabelText('只看未标注'));
    await user.click(screen.getByRole('button', { name: /批量 AI 分析/ }));

    await waitFor(() => {
      expect(mockedPrelabelBatch).toHaveBeenCalledWith({
        q: 'req:abc',
        label: undefined,
        unannotated_only: true,
        limit: 50,
        skip_existing: true,
      });
    });
    expect(mockedPrelabelBatchJob).toHaveBeenCalledWith('prelabel-batch-1');
    expect(mockedList).toHaveBeenCalledTimes(2);
  });

  it('开启隐藏 AI 判定正常后过滤高置信正常预判样本', async () => {
    const user = userEvent.setup();
    const normalSample: DataFlywheelSample = {
      ...anotherSample,
      latest_prelabel: {
        id: 99,
        sample_id: anotherSample.sample_id,
        sample_type: 'session_turn',
        session_id: anotherSample.session_id,
        turn_id: anotherSample.turn_id,
        request_id: anotherSample.request_id,
        source: 'llm_judge',
        status: 'pending',
        labels: ['good_reply'],
        root_cause: '回复满足用户意图',
        severity: 'low',
        confidence: 0.93,
        reason: '没有明显质量问题。',
        recommended_fix: '',
        judge_model: 'fake-judge',
        prompt_version: 'data-flywheel-prelabel-v1',
      },
      prelabels: [],
      user_input_preview: '查询今天农场概况',
    };
    mockedList.mockResolvedValue({ items: [sample, normalSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('查询今天农场概况');
    await user.click(screen.getByLabelText('隐藏 AI 判定正常'));

    expect(screen.getByText('帮我查一下张三这个月工资有没有漏记')).toBeInTheDocument();
    expect(screen.queryByText('查询今天农场概况')).not.toBeInTheDocument();
  });

  it('默认按风险加载并支持隐藏低风险与 P0 筛选', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, anotherSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('帮我查一下张三这个月工资有没有漏记');

    expect(mockedList).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: 'risk' })
    );
    expect(screen.getAllByText('Rule Risk: 0.88').length).toBeGreaterThan(0);
    expect(screen.getAllByText('P0').length).toBeGreaterThan(0);

    await user.click(screen.getByLabelText('隐藏低风险'));
    expect(mockedList).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: 'risk', min_risk: 0.3 })
    );

    await user.click(screen.getByLabelText('P0 严重'));
    expect(mockedList).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: 'risk', min_risk: 0.3, severity: 'P0' })
    );
  });

  it('URL sort=time 时按时间排序回退加载', async () => {
    window.history.pushState({}, '', '/dev/data-flywheel?sort=time');
    mockedList.mockResolvedValue({ items: [anotherSample], total: 1 });
    render(<DataFlywheel />);

    await screen.findByText('给李四补一条今天的浇水记录');

    expect(mockedList).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: 'time' })
    );
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

  it('完整会话级标注下禁用 AI 预判入口', async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValue({ items: [sample, sessionSecondSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByText('session-a');
    fireEvent.click(screen.getByTestId('archive-session-session-a'));
    await screen.findByText('完整对话记录');
    await user.click(screen.getByRole('button', { name: /标注整个会话/ }));

    const prelabelButton = screen.getByRole('button', { name: 'AI 预判' });
    expect(prelabelButton).toBeDisabled();
    await user.click(prelabelButton);

    expect(mockedCreatePrelabel).not.toHaveBeenCalled();
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

  it('加载样本详情不会自动触发 AI 预标注', async () => {
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));

    await waitFor(() => {
      expect(mockedDetail).toHaveBeenCalledWith(sample.sample_id);
    });
    expect(mockedCreatePrelabel).not.toHaveBeenCalled();
  });

  it('点击 AI 预判队列后只显示待审核预判样本', async () => {
    const pendingPrelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['wrong_tool_selection'],
      root_cause: '实时查询未调用工具',
      severity: 'high',
      confidence: 0.91,
      reason: '用户需要实时数据，但没有工具调用。',
      recommended_fix: '优先调用天气或业务查询工具。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    const predictedSample: DataFlywheelSample = {
      ...sample,
      latest_prelabel: pendingPrelabel,
      prelabels: [pendingPrelabel],
    };
    const rejectedSample: DataFlywheelSample = {
      ...anotherSample,
      latest_prelabel: { ...pendingPrelabel, id: 10, sample_id: anotherSample.sample_id, status: 'rejected' },
      prelabels: [],
    };
    mockedList.mockResolvedValue({ items: [predictedSample, rejectedSample], total: 2 });
    render(<DataFlywheel />);

    await screen.findByTestId('archive-ai-prelabels');
    fireEvent.click(screen.getByTestId('archive-ai-prelabels'));

    expect(screen.getByTestId('sample-row-turn:session-a:3')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-row-turn:session-b:4')).not.toBeInTheDocument();
    expect(screen.getByTestId('archive-ai-prelabels')).toBeInTheDocument();
  });

  it('审核 AI 预判时展示聊天内容和工具证据', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['wrong_tool_selection'],
      root_cause: '实时查询未调用工具',
      severity: 'high',
      confidence: 0.91,
      reason: '用户需要实时数据，但没有工具调用。',
      recommended_fix: '优先调用天气或业务查询工具。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    const predictedSample: DataFlywheelSample = {
      ...sample,
      latest_prelabel: prelabel,
      prelabels: [prelabel],
    };
    mockedList.mockResolvedValue({ items: [predictedSample], total: 1 });
    mockedDetail.mockResolvedValueOnce({ ...detail, sample: predictedSample, prelabels: [prelabel] });
    render(<DataFlywheel />);

    await screen.findByTestId('archive-ai-prelabels');
    fireEvent.click(screen.getByTestId('archive-ai-prelabels'));
    fireEvent.click(screen.getByTestId('sample-row-turn:session-a:3'));

    expect(await screen.findByText('审核证据')).toBeInTheDocument();
    expect(screen.getByText('用户输入')).toBeInTheDocument();
    expect(screen.getByText('助手回复')).toBeInTheDocument();
    expect(screen.getAllByText('张三本月工资记录里缺少 6 月 8 日。').length).toBeGreaterThan(0);
    expect(screen.getAllByText('selected_tools').length).toBeGreaterThan(0);
    expect(screen.getAllByText('worker.search').length).toBeGreaterThan(0);
    expect(screen.getAllByText('wage.list').length).toBeGreaterThan(0);
    expect(screen.getAllByText('actual_tools').length).toBeGreaterThan(0);
    expect(screen.getByText('1 个 pending 事件')).toBeInTheDocument();
  });

  it('采纳 AI 预判后预判队列移除样本并进入已标注问题', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['wrong_tool_selection'],
      root_cause: '实时查询未调用工具',
      severity: 'high',
      confidence: 0.91,
      reason: '用户需要实时数据，但没有工具调用。',
      recommended_fix: '优先调用天气或业务查询工具。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    const predictedSample: DataFlywheelSample = {
      ...sample,
      latest_prelabel: prelabel,
      prelabels: [prelabel],
    };
    const acceptedSample: DataFlywheelSample = {
      ...sample,
      quality_labels: ['wrong_tool_selection'],
      annotation_status: 'labeled',
      latest_prelabel: { ...prelabel, status: 'accepted' },
      prelabels: [],
    };
    mockedList
      .mockResolvedValueOnce({ items: [predictedSample], total: 1 })
      .mockResolvedValueOnce({ items: [acceptedSample], total: 1 });
    mockedDetail.mockResolvedValueOnce({ ...detail, sample: predictedSample, labels: [], prelabels: [prelabel] });
    mockedAcceptPrelabel.mockResolvedValueOnce({
      ...prelabel,
      status: 'accepted',
      accepted_label_ids: [7],
    });
    render(<DataFlywheel />);

    await screen.findByTestId('archive-ai-prelabels');
    fireEvent.click(screen.getByTestId('archive-ai-prelabels'));
    fireEvent.click(screen.getByTestId('sample-row-turn:session-a:3'));
    await userEvent.click(await screen.findByRole('button', { name: '采纳 AI 预判' }));

    await waitFor(() => {
      expect(mockedAcceptPrelabel).toHaveBeenCalledWith(sample.sample_id, 9, {
        labels: ['wrong_tool_selection'],
        comment: 'AI 预判采纳：用户需要实时数据，但没有工具调用。',
      });
    });
    expect(mockedList).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByTestId('archive-ai-prelabels'));
    expect(screen.queryByTestId('sample-row-turn:session-a:3')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('archive-confirmed-issues'));
    expect(screen.getByTestId('problem-session-session-a')).toBeInTheDocument();
  });

  it('点击 AI 预判后调用 createSamplePrelabel 并展示预判结果', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['bad_reply', 'pending_missed'],
      root_cause: '写操作缺少 pending 确认',
      severity: 'high',
      confidence: 0.86,
      reason: '回复声称已安排，但没有完整 pending lifecycle。',
      recommended_fix: '写操作执行前必须创建 pending plan。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    mockedCreatePrelabel.mockResolvedValueOnce(prelabel);
    mockedDetail.mockResolvedValueOnce(detail).mockResolvedValueOnce({
      ...detail,
      prelabels: [prelabel],
    });
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await userEvent.click(await screen.findByRole('button', { name: 'AI 预判' }));

    expect(mockedCreatePrelabel).toHaveBeenCalledWith(sample.sample_id);
    expect(await screen.findByText('写操作缺少 pending 确认')).toBeInTheDocument();
    expect(screen.getByTitle('bad_reply')).toHaveTextContent('坏回复');
    expect(screen.getByTitle('pending_missed')).toHaveTextContent('pending 漏拦截');
  });

  it('采纳 AI 预判时调用 acceptSamplePrelabel 写入建议标签', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['bad_reply', 'pending_missed'],
      root_cause: '写操作缺少 pending 确认',
      severity: 'high',
      confidence: 0.86,
      reason: '回复声称已安排，但没有完整 pending lifecycle。',
      recommended_fix: '写操作执行前必须创建 pending plan。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    mockedDetail.mockResolvedValueOnce({
      ...detail,
      prelabels: [prelabel],
    });
    mockedAcceptPrelabel.mockResolvedValueOnce({
      ...prelabel,
      status: 'accepted',
      accepted_label_ids: [7, 8],
    });
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    const commentBox = await screen.findByPlaceholderText('记录判断依据、复现条件或后续处理建议');
    await userEvent.clear(commentBox);
    await userEvent.type(commentBox, '人工确认 pending 缺失');
    await userEvent.click(await screen.findByRole('button', { name: '采纳 AI 预判' }));

    await waitFor(() => {
      expect(mockedAcceptPrelabel).toHaveBeenCalledWith(sample.sample_id, 9, {
        labels: ['bad_reply', 'pending_missed'],
        comment: '人工确认 pending 缺失',
      });
    });
  });

  it('修改 AI 建议标签后点击修改后保存使用修改后的标签', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['tool_error_ignored'],
      root_cause: '回复不可验证',
      severity: 'medium',
      confidence: 0.72,
      reason: '证据不足但回复声称完成。',
      recommended_fix: '要求补充证据。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    mockedDetail.mockResolvedValueOnce({
      ...detail,
      prelabels: [prelabel],
    });
    mockedAcceptPrelabel.mockResolvedValueOnce({
      ...prelabel,
      status: 'accepted',
      labels: ['unclear_intent'],
      accepted_label_ids: [8],
    });
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    const prelabelSelect = (await screen.findAllByLabelText('AI 建议标签'))[0];
    await userEvent.click(within(prelabelSelect).getByLabelText('close'));
    const selectInput = prelabelSelect.querySelector('.ant-select-selector');
    expect(selectInput).not.toBeNull();
    fireEvent.mouseDown(selectInput as Element);
    const unclearIntentOptions = await screen.findAllByText('意图不清');
    await userEvent.click(unclearIntentOptions[unclearIntentOptions.length - 1]);
    await userEvent.click(await screen.findByRole('button', { name: '修改后保存' }));

    await waitFor(() => {
      expect(mockedAcceptPrelabel).toHaveBeenCalledWith(sample.sample_id, 9, {
        labels: ['unclear_intent'],
        comment: '初始备注',
      });
    });
  });

  it('点击驳回 AI 预判调用 rejectSamplePrelabel 且不保存人工标签', async () => {
    const prelabel: DataFlywheelPrelabel = {
      id: 9,
      sample_id: sample.sample_id,
      sample_type: 'session_turn',
      session_id: sample.session_id,
      turn_id: sample.turn_id,
      request_id: sample.request_id,
      source: 'llm_judge',
      status: 'pending',
      labels: ['bad_reply'],
      root_cause: '误判',
      severity: 'low',
      confidence: 0.4,
      reason: '测试用误判。',
      recommended_fix: '无需处理。',
      judge_model: 'fake-judge',
      prompt_version: 'data-flywheel-prelabel-v1',
    };
    mockedDetail.mockResolvedValueOnce({
      ...detail,
      prelabels: [prelabel],
    });
    mockedRejectPrelabel.mockResolvedValueOnce({
      ...prelabel,
      status: 'rejected',
    });
    render(<DataFlywheel />);

    fireEvent.click(await screen.findByTestId('sample-row-turn:session-a:3'));
    await userEvent.click(await screen.findByRole('button', { name: '驳回 AI 预判' }));

    await waitFor(() => {
      expect(mockedRejectPrelabel).toHaveBeenCalledWith(sample.sample_id, 9);
    });
    expect(mockedAddLabel).not.toHaveBeenCalled();
  });
});
