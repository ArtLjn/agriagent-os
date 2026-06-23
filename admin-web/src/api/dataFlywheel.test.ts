import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import {
  acceptSamplePrelabel,
  addSampleLabel,
  createCaseDraft,
  createRepairPack,
  createSamplePrelabel,
  createSamplePrelabelBatch,
  discardRepairPack,
  exportSampleJsonl,
  getSampleDetail,
  getRepairPack,
  getSessionReview,
  getDataFlywheelSyncJob,
  getSamplePrelabelBatchJob,
  getSessionAnnotations,
  listDataFlywheelSamples,
  listRepairPackCandidates,
  listRepairPacks,
  markBadCase,
  markRepairPackResolved,
  rebuildRepairPack,
  recordRepairPackVerificationFailure,
  reopenRepairPack,
  deleteSampleLabel,
  rejectSamplePrelabel,
  resolveSampleLabel,
  syncDataFlywheelSessions,
  type AcceptPrelabelRequest,
} from './dataFlywheel';

vi.mock('./client', () => ({
  default: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('dataFlywheel api', () => {
  it('传递筛选参数读取数据飞轮样本列表', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            sample_id: 'turn:1:s:1',
            sample_type: 'turn',
            quality_labels: ['good_reply'],
            annotation_status: 'unlabeled',
            session_id: 's:1',
            turn_id: 1,
            request_id: 'req:1',
            user_input_preview: '查一下天气',
            assistant_reply_preview: '今天适合下地',
            selected_tools: ['weather'],
            actual_tools: ['weather'],
            issue_candidates: [],
            token_total: 128,
            latency_ms: 320,
            source_type: 'event_log',
            created_at: '2026-06-11T08:00:00Z',
          },
        ],
        total: 1,
      },
    });

    const params = {
      session_id: 's:1',
      label: 'good_reply',
      unannotated_only: true,
      limit: 20,
      offset: 0,
    };

    const result = await listDataFlywheelSamples(params);

    expect(mockedApiClient.get).toHaveBeenCalledWith('/admin/data-flywheel/samples', { params });
    expect(result.items[0].sample_id).toBe('turn:1:s:1');
  });

  it('传递筛选参数读取 repair pack 修复候选', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            sample_id: 'turn:1:s:1',
            session_id: 's:1',
            turn_id: 1,
            request_id: 'req:1',
            labels: ['pending_missed'],
            fix_target: 'pending_plan',
            priority: 90,
            suggested_action: '修复 pending lifecycle',
            regression_ready: true,
            verification_commands: ['pytest tests/services/test_pending_plan.py'],
            secondary_targets: [],
          },
        ],
        total: 1,
      },
    });

    const params = {
      label: 'pending_missed',
      fix_target: 'pending_plan',
      regression_ready: true,
      min_priority: 80,
      q: 's:1',
      limit: 10,
    };
    const result = await listRepairPackCandidates(params);

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-candidates',
      { params, paramsSerializer: { indexes: null } }
    );
    expect(result.items[0].fix_target).toBe('pending_plan');
  });

  it('编码 sample_id 后读取样本详情', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        sample: { sample_id: 'turn:1:s:1' },
        quality_labels: [],
        labels: [],
        messages: [{ id: 1, role: 'user', content: '你好' }],
        turn: null,
        router_decision: null,
        tool_events: [],
        pending_lifecycle: [],
        issue_candidates: [],
        debug_export: null,
        source: {
          event_file: 'events.jsonl',
          event_seq_start: 1,
          event_seq_end: 3,
        },
      },
    });

    const result = await getSampleDetail('turn:1:s:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith('/admin/data-flywheel/samples/turn%3A1%3As%3A1');
    expect(result.messages[0].content).toBe('你好');
  });

  it('编码 session_id 后读取完整会话审阅', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        session_id: 'playground:s:1',
        turns: [],
      },
    });

    const result = await getSessionReview('playground:s:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/sessions/playground%3As%3A1/review'
    );
    expect(result.session_id).toBe('playground:s:1');
  });

  it('编码 session_id 后读取会话级标注', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        sample_id: 'session:1:playground:s:1',
        sample_type: 'session',
        session_id: 'playground:s:1',
        quality_labels: ['needs_regression'],
        labels: [],
      },
    });

    const result = await getSessionAnnotations('playground:s:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/sessions/playground%3As%3A1/annotations'
    );
    expect(result.sample_type).toBe('session');
  });

  it('向 labels 路径提交样本标签和备注', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 7,
        sample_id: 'turn:1:s:1',
        label: 'bad_reply',
        comment: '答非所问',
        annotator_id: 'admin',
      },
    });

    const body = {
      label: 'bad_reply' as const,
      comment: '答非所问',
    };

    const result = await addSampleLabel('turn:1:s:1', body);

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/data-flywheel/samples/turn%3A1%3As%3A1/labels', body);
    expect(result.label).toBe('bad_reply');
  });

  it('删除指定样本标注', async () => {
    mockedApiClient.delete.mockResolvedValueOnce({
      data: {
        deleted: true,
        id: 7,
      },
    });

    const result = await deleteSampleLabel('turn:1:s:1', 7);

    expect(mockedApiClient.delete).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/labels/7'
    );
    expect(result.deleted).toBe(true);
  });

  it('将指定样本标注标记为已解决', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 7,
        sample_id: 'turn:1:s:1',
        label: 'bad_reply',
        status: 'resolved',
      },
    });

    const result = await resolveSampleLabel('turn:1:s:1', 7);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/labels/7/resolve'
    );
    expect(result.status).toBe('resolved');
  });

  it('向 bad-case 路径提交坏例标注', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 8,
        sample_id: 'turn:1:s:1',
        label: 'needs_regression',
        comment: '需要回归',
        annotator_id: 'admin',
      },
    });

    const body = {
      label: 'needs_regression' as const,
      comment: '需要回归',
    };

    const result = await markBadCase('turn:1:s:1', body);

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/data-flywheel/samples/turn%3A1%3As%3A1/bad-case', body);
    expect(result.label).toBe('needs_regression');
  });

  it('按 sample_id 导出 JSONL', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        content: '{"sample_id":"turn:1:s:1"}',
        filename: 'data-flywheel.jsonl',
      },
    });

    const result = await exportSampleJsonl('turn:1:s:1');

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/data-flywheel/export-jsonl', {
      sample_id: 'turn:1:s:1',
    });
    expect(result.filename).toBe('data-flywheel.jsonl');
  });

  it('向 case-draft 路径提交目标类型创建草稿', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 12,
        draft_id: 'draft:1',
        source_sample_id: 'turn:1:s:1',
        target_type: 'evaluation_replay',
        status: 'draft',
        case_json: { sample_id: 'turn:1:s:1' },
        created_by: 'admin',
      },
    });

    const result = await createCaseDraft('turn:1:s:1', 'evaluation_replay');

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/data-flywheel/samples/turn%3A1%3As%3A1/case-draft', {
      target_type: 'evaluation_replay',
    });
    expect(result.draft_id).toBe('draft:1');
  });

  it('按样本集合生成 repair pack', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 1,
        pack_id: 'repair-pending-plan-abc',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:1:s:1'],
        status: 'exported',
        export_path: 'data/repair-packs/repair-pending-plan-abc',
        manifest: { pack_id: 'repair-pending-plan-abc' },
        payload: {
          manifest: { pack_id: 'repair-pending-plan-abc' },
          cases_jsonl: [],
          readme: '# Repair Pack',
          debug_files: {},
          regression_drafts: {},
        },
      },
    });

    const body = {
      sample_ids: ['turn:1:s:1'],
      fix_target: 'pending_plan',
      limit: 5,
    };
    const result = await createRepairPack(body);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs',
      body
    );
    expect(result.pack_id).toBe('repair-pending-plan-abc');
  });

  it('编码 pack_id 后读取 repair pack 详情', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        id: 1,
        pack_id: 'repair:1',
        fix_target: 'pending_plan',
        labels: [],
        source_sample_ids: [],
        status: 'exported',
        export_path: null,
        manifest: {},
      },
    });

    const result = await getRepairPack('repair:1');

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair%3A1'
    );
    expect(result.pack_id).toBe('repair:1');
  });

  it('标记 repair pack 已修复', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 1,
        pack_id: 'repair-1',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:1:s:1'],
        status: 'resolved',
        export_path: null,
        manifest: {},
        repair_note: '已修复',
      },
    });

    const body = {
      repair_note: '已修复',
      verification_summary: { passed: true },
    };
    const result = await markRepairPackResolved('repair-1', body);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair-1/resolve',
      body
    );
    expect(result.status).toBe('resolved');
  });

  it('记录 repair pack 验证失败', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 1,
        pack_id: 'repair-1',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:1:s:1'],
        status: 'verification_failed',
        export_path: null,
        manifest: {},
        verification_summary: { passed: false },
      },
    });

    const body = { verification_summary: { passed: false } };
    const result = await recordRepairPackVerificationFailure('repair-1', body);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair-1/verification-failed',
      body
    );
    expect(result.status).toBe('verification_failed');
  });

  it('提交后台同步会话任务', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        job_id: 'session-sync-1',
        status: 'queued',
        mode: 'background',
        session_id: 'session-a',
      },
    });

    const result = await syncDataFlywheelSessions({
      session_id: 'session-a',
      only_missing: true,
      limit: 100,
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith('/admin/data-flywheel/sync-sessions', {
      session_id: 'session-a',
      only_missing: true,
      limit: 100,
    });
    expect(result.job_id).toBe('session-sync-1');
  });

  it('查询会话同步任务状态', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        job_id: 'session-sync-1',
        status: 'completed',
        result: { synced_turns: 2 },
      },
    });

    const result = await getDataFlywheelSyncJob('session-sync-1');

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/sync-sessions/session-sync-1'
    );
    expect(result.status).toBe('completed');
  });

  it('触发样本 LLM 预标注', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 3,
        sample_id: 'turn:1:s:1',
        source: 'llm_judge',
        status: 'pending',
        labels: ['bad_reply'],
        root_cause: '回复不可验证',
        severity: 'medium',
        confidence: 0.72,
        reason: '证据不足但回复声称完成。',
        recommended_fix: '要求补充证据。',
        judge_model: 'fake-judge',
        prompt_version: 'data-flywheel-prelabel-v1',
      },
    });

    const result = await createSamplePrelabel('turn:1:s:1');

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabel'
    );
    expect(result.source).toBe('llm_judge');
  });

  it('触发批量 LLM 预判任务', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        job_id: 'prelabel-batch-1',
        status: 'queued',
        mode: 'background',
        result: null,
        error: null,
      },
    });

    const body = {
      q: 'session-a',
      unannotated_only: true,
      limit: 50,
      skip_existing: true,
    };
    const result = await createSamplePrelabelBatch(body);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/prelabels/batch',
      body
    );
    expect(result.job_id).toBe('prelabel-batch-1');
  });

  it('查询批量 LLM 预判任务状态', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        job_id: 'prelabel-batch-1',
        status: 'completed',
        mode: 'background',
        result: { created: 2, skipped_existing: 1, failed: 0 },
        error: null,
      },
    });

    const result = await getSamplePrelabelBatchJob('prelabel-batch-1');

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/prelabels/batch/prelabel-batch-1'
    );
    expect(result.status).toBe('completed');
  });

  it('采纳并可修改样本 LLM 预标注', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 3,
        sample_id: 'turn:1:s:1',
        status: 'accepted',
        labels: ['pending_missed', 'needs_regression'],
        accepted_label_ids: [7, 8],
      },
    });

    const body: AcceptPrelabelRequest = {
      labels: ['pending_missed', 'needs_regression'],
      comment: '人工修改后采纳',
    };
    const result = await acceptSamplePrelabel('turn:1:s:1', 3, body);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabels/3/accept',
      body
    );
    expect(result.status).toBe('accepted');
  });

  it('驳回样本 LLM 预标注', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 3,
        sample_id: 'turn:1:s:1',
        status: 'rejected',
        labels: ['bad_reply'],
      },
    });

    const result = await rejectSamplePrelabel('turn:1:s:1', 3);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/samples/turn%3A1%3As%3A1/prelabels/3/reject'
    );
    expect(result.status).toBe('rejected');
  });

  it('分页列出 repair pack', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            pack_id: 'repair-router-abc',
            fix_target: 'router',
            labels: ['bad_reply'],
            source_sample_ids: ['turn:1:s:1'],
            status: 'exported',
            export_path: 'data/repair-packs/repair-router-abc',
            manifest: { pack_id: 'repair-router-abc' },
            dedup_key: 'deadbeefdeadbeef',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
      },
    });

    const result = await listRepairPacks({
      status: 'exported',
      fix_target: 'router',
      include_discarded: true,
      page: 1,
      page_size: 10,
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs',
      {
        params: {
          status: 'exported',
          fix_target: 'router',
          include_discarded: true,
          page: 1,
          page_size: 10,
        },
      }
    );
    expect(result.total).toBe(1);
    expect(result.items[0].pack_id).toBe('repair-router-abc');
  });

  it('标记 repair pack 为废弃', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 2,
        pack_id: 'repair-pending-plan-xyz',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:2:s:1'],
        status: 'discarded',
        export_path: 'data/repair-packs/repair-pending-plan-xyz',
        manifest: {},
        repair_note: 'duplicate',
      },
    });

    const result = await discardRepairPack('repair-pending-plan-xyz', {
      reason: 'duplicate',
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair-pending-plan-xyz/discard',
      { reason: 'duplicate' }
    );
    expect(result.status).toBe('discarded');
  });

  it('恢复 repair pack 状态', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 2,
        pack_id: 'repair-pending-plan-xyz',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:2:s:1'],
        status: 'exported',
        export_path: 'data/repair-packs/repair-pending-plan-xyz',
        manifest: {},
      },
    });

    const result = await reopenRepairPack('repair-pending-plan-xyz');

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair-pending-plan-xyz/reopen'
    );
    expect(result.status).toBe('exported');
  });

  it('同步重建 repair pack 本地文件', async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        id: 2,
        pack_id: 'repair-pending-plan-xyz',
        fix_target: 'pending_plan',
        labels: ['pending_missed'],
        source_sample_ids: ['turn:2:s:1'],
        status: 'exported',
        export_path: 'data/repair-packs/repair-pending-plan-xyz',
        manifest: {},
      },
    });

    const result = await rebuildRepairPack('repair-pending-plan-xyz');

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      '/admin/data-flywheel/repair-packs/repair-pending-plan-xyz/rebuild'
    );
    expect(result.pack_id).toBe('repair-pending-plan-xyz');
  });
});
