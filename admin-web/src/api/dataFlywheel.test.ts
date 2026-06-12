import { describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import {
  addSampleLabel,
  createCaseDraft,
  exportSampleJsonl,
  getSampleDetail,
  getSessionReview,
  getDataFlywheelSyncJob,
  getSessionAnnotations,
  listDataFlywheelSamples,
  markBadCase,
  deleteSampleLabel,
  syncDataFlywheelSessions,
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
});
