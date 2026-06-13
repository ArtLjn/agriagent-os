import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { Button, Card, Checkbox, Input, Select, Space, Typography, message } from 'antd';
import { CloudSyncOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';

import {
  getTraceDiagnostics,
  type TraceDiagnostics,
} from '../../api/admin';
import {
  acceptSamplePrelabel,
  addSampleLabel,
  createCaseDraft,
  createSamplePrelabel,
  createSamplePrelabelBatch,
  deleteSampleLabel,
  exportSampleJsonl,
  getDataFlywheelSyncJob,
  getSampleDetail,
  getSamplePrelabelBatchJob,
  getSessionAnnotations,
  getSessionReview,
  listDataFlywheelSamples,
  markBadCase,
  rejectSamplePrelabel,
  resolveSampleLabel,
  syncDataFlywheelSessions,
  type CaseDraft,
  type DataFlywheelDetail,
  type DataFlywheelLabel,
  type DataFlywheelLabelRecord,
  type DataFlywheelSample,
  type DataFlywheelSessionAnnotations,
  type DataFlywheelSessionReview,
} from '../../api/dataFlywheel';
import { cardStyle, palette } from '../../styles/theme';
import AnnotationPanel from './components/AnnotationPanel';
import CaseDraftPreview from './components/CaseDraftPreview';
import CollapsibleWorkspace from './components/CollapsibleWorkspace';
import SampleDetailPanel from './components/SampleDetailPanel';
import SampleQueueTable from './components/SampleQueueTable';
import SessionConversationView from './components/SessionConversationView';
import SessionArchivePanel, { type SessionArchiveItem } from './components/SessionArchivePanel';
import ReviewEvidencePanel from './components/ReviewEvidencePanel';

const DEFAULT_LABEL: DataFlywheelLabel = 'good_reply';
const ALL_ARCHIVE_KEY = '__all__';
const ISSUE_ARCHIVE_KEY = '__issues__';
const AI_PRELABEL_ARCHIVE_KEY = '__ai_prelabels__';
const CONFIRMED_ISSUE_ARCHIVE_KEY = '__confirmed_issues__';

interface SampleQuery {
  searchText: string;
  qualityLabel?: DataFlywheelLabel;
  unannotatedOnly: boolean;
}

type AnnotationTarget =
  | { type: 'turn'; sample: DataFlywheelSample }
  | { type: 'session'; sampleId: string; sessionId: string };

const labelOptions: Array<{ label: string; value: DataFlywheelLabel }> = [
  { label: '好回复', value: 'good_reply' },
  { label: '坏回复', value: 'bad_reply' },
  { label: '工具选错', value: 'wrong_tool_selection' },
  { label: 'pending 漏拦截', value: 'pending_missed' },
  { label: '幻觉执行', value: 'hallucinated_execution' },
  { label: '工具错误被忽略', value: 'tool_error_ignored' },
  { label: '答非所问', value: 'off_topic' },
  { label: '意图不清', value: 'unclear_intent' },
  { label: '参数/提示泄露', value: 'sensitive_info_leak' },
  { label: '工资缺失', value: 'missing_wage' },
  { label: '禁用工人', value: 'disabled_worker_used' },
  { label: '需要回归', value: 'needs_regression' },
  { label: '暂不处理', value: 'not_actionable' },
];

export default function DataFlywheel() {
  const [samples, setSamples] = useState<DataFlywheelSample[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [acting, setActing] = useState(false);
  const [prelabeling, setPrelabeling] = useState(false);
  const [reviewingPrelabel, setReviewingPrelabel] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [qualityLabel, setQualityLabel] = useState<DataFlywheelLabel | undefined>();
  const [unannotatedOnly, setUnannotatedOnly] = useState(false);
  const [hideAiNormal, setHideAiNormal] = useState(false);
  const [query, setQuery] = useState<SampleQuery>({
    searchText: '',
    qualityLabel: undefined,
    unannotatedOnly: false,
  });
  const [selectedSample, setSelectedSample] = useState<DataFlywheelSample | null>(null);
  const [detail, setDetail] = useState<DataFlywheelDetail | null>(null);
  const [sessionAnnotations, setSessionAnnotations] = useState<DataFlywheelSessionAnnotations | null>(null);
  const [sessionAnnotationCache, setSessionAnnotationCache] = useState<Record<string, DataFlywheelSessionAnnotations>>({});
  const [annotationTarget, setAnnotationTarget] = useState<AnnotationTarget | null>(null);
  const [currentLabel, setCurrentLabel] = useState<DataFlywheelLabel>(DEFAULT_LABEL);
  const [selectedPrelabelLabels, setSelectedPrelabelLabels] = useState<DataFlywheelLabel[]>([]);
  const [comment, setComment] = useState('');
  const [draft, setDraft] = useState<CaseDraft | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [activeArchiveKey, setActiveArchiveKey] = useState(ALL_ARCHIVE_KEY);
  const [sessionReview, setSessionReview] = useState<DataFlywheelSessionReview | null>(null);
  const [loadingSessionReview, setLoadingSessionReview] = useState(false);
  const [traceDiagnosticsByRequestId, setTraceDiagnosticsByRequestId] = useState<Record<string, TraceDiagnostics>>({});
  const [loadingTraceDiagnostics, setLoadingTraceDiagnostics] = useState<Record<string, boolean>>({});
  const [syncingSessions, setSyncingSessions] = useState(false);
  const [batchPrelabeling, setBatchPrelabeling] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(true);
  const listRequestSeq = useRef(0);
  const detailRequestSeq = useRef(0);
  const sessionReviewRequestSeq = useRef(0);
  const traceDiagnosticsLoadedRef = useRef<Set<string>>(new Set());
  const traceDiagnosticsLoadingRef = useRef<Set<string>>(new Set());

  const sessionAnnotationOverlays = useMemo(
    () => mergeSessionAnnotations(Object.values(sessionAnnotationCache), sessionAnnotations),
    [sessionAnnotationCache, sessionAnnotations]
  );
  const archiveGroups = useMemo(
    () => buildArchiveGroups(samples, sessionAnnotationOverlays),
    [samples, sessionAnnotationOverlays]
  );
  const confirmedIssueGroups = useMemo(
    () => archiveGroups.filter((group) => group.badCases > 0),
    [archiveGroups]
  );
  const issueCount = useMemo(
    () => samples.filter((sample) => sample.issue_candidates.length > 0).length,
    [samples]
  );
  const aiPrelabelCount = useMemo(
    () => samples.filter(hasPendingAiPrelabel).length,
    [samples]
  );
  const confirmedIssueCount = useMemo(
    () => confirmedIssueTotal(samples, sessionAnnotationOverlays),
    [samples, sessionAnnotationOverlays]
  );
  const visibleSamples = useMemo(() => {
    const baseSamples = hideAiNormal ? samples.filter((sample) => !isAiNormalSample(sample)) : samples;
    if (activeArchiveKey === ALL_ARCHIVE_KEY) return baseSamples;
    if (activeArchiveKey === ISSUE_ARCHIVE_KEY) {
      return baseSamples.filter((sample) => sample.issue_candidates.length > 0);
    }
    if (activeArchiveKey === AI_PRELABEL_ARCHIVE_KEY) {
      return baseSamples.filter(hasPendingAiPrelabel);
    }
    if (activeArchiveKey === CONFIRMED_ISSUE_ARCHIVE_KEY) {
      return [];
    }
    return baseSamples.filter((sample) => sessionArchiveKey(sample) === activeArchiveKey);
  }, [activeArchiveKey, hideAiNormal, samples]);
  const isSessionArchiveActive =
    activeArchiveKey !== ALL_ARCHIVE_KEY &&
    activeArchiveKey !== ISSUE_ARCHIVE_KEY &&
    activeArchiveKey !== AI_PRELABEL_ARCHIVE_KEY &&
    activeArchiveKey !== CONFIRMED_ISSUE_ARCHIVE_KEY;

  useEffect(() => {
    if (
      activeArchiveKey === ALL_ARCHIVE_KEY ||
      activeArchiveKey === ISSUE_ARCHIVE_KEY ||
      activeArchiveKey === AI_PRELABEL_ARCHIVE_KEY ||
      activeArchiveKey === CONFIRMED_ISSUE_ARCHIVE_KEY
    ) {
      return;
    }
    if (archiveGroups.some((group) => group.key === activeArchiveKey)) return;
    setActiveArchiveKey(ALL_ARCHIVE_KEY);
  }, [activeArchiveKey, archiveGroups]);

  const fetchSamples = useCallback(async (nextQuery: SampleQuery) => {
    const requestSeq = listRequestSeq.current + 1;
    listRequestSeq.current = requestSeq;
    setLoadingList(true);
    try {
      const trimmed = nextQuery.searchText.trim();
      const result = await listDataFlywheelSamples({
        limit: 50,
        offset: 0,
        label: nextQuery.qualityLabel,
        unannotated_only: nextQuery.unannotatedOnly || undefined,
        q: trimmed || undefined,
      });
      if (requestSeq !== listRequestSeq.current) return;
      setSamples(result.items);
      setTotal(result.total);
      setSelectedSample((current) => {
        if (!current || result.items.some((item) => item.sample_id === current.sample_id)) {
          return current;
        }
        setDetail(null);
        return null;
      });
    } catch {
      if (requestSeq === listRequestSeq.current) {
        message.error('加载数据飞轮样本失败');
      }
    } finally {
      if (requestSeq === listRequestSeq.current) {
        setLoadingList(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchSamples(query);
  }, [fetchSamples, query]);

  const loadTraceDiagnostics = useCallback(async (requestId: string) => {
    if (
      traceDiagnosticsLoadedRef.current.has(requestId) ||
      traceDiagnosticsLoadingRef.current.has(requestId)
    ) {
      return;
    }
    traceDiagnosticsLoadingRef.current.add(requestId);
    setLoadingTraceDiagnostics((current) => ({ ...current, [requestId]: true }));
    try {
      const result = await getTraceDiagnostics(requestId);
      traceDiagnosticsLoadedRef.current.add(requestId);
      setTraceDiagnosticsByRequestId((current) => ({ ...current, [requestId]: result }));
    } catch {
      traceDiagnosticsLoadedRef.current.add(requestId);
      setTraceDiagnosticsByRequestId((current) => ({
        ...current,
        [requestId]: emptyTraceDiagnostics(requestId),
      }));
    } finally {
      traceDiagnosticsLoadingRef.current.delete(requestId);
      setLoadingTraceDiagnostics((current) => ({ ...current, [requestId]: false }));
    }
  }, []);

  const loadTraceDiagnosticsForReview = useCallback(
    async (review: DataFlywheelSessionReview) => {
      const requestIds = Array.from(
        new Set(
          review.turns
            .map((turn) => turn.sample.request_id)
            .filter((requestId): requestId is string => Boolean(requestId))
        )
      );
      await Promise.all(requestIds.map((requestId) => loadTraceDiagnostics(requestId)));
    },
    [loadTraceDiagnostics]
  );

  const loadSessionReview = useCallback(
    async (sessionId: string) => {
      const requestSeq = sessionReviewRequestSeq.current + 1;
      sessionReviewRequestSeq.current = requestSeq;
      setLoadingSessionReview(true);
      try {
        const result = await getSessionReview(sessionId);
        if (requestSeq !== sessionReviewRequestSeq.current) return;
        setSessionReview(result);
        void loadTraceDiagnosticsForReview(result);
      } catch {
        if (requestSeq === sessionReviewRequestSeq.current) {
          message.error('加载完整会话记录失败');
        }
      } finally {
        if (requestSeq === sessionReviewRequestSeq.current) {
          setLoadingSessionReview(false);
        }
      }
    },
    [loadTraceDiagnosticsForReview]
  );

  const submitQuery = () => {
    setActiveArchiveKey(ALL_ARCHIVE_KEY);
    setSessionReview(null);
    clearSelection();
    setQuery({
      searchText,
      qualityLabel,
      unannotatedOnly,
    });
  };

  const refreshSamples = () => {
    fetchSamples(query);
    if (isSessionArchiveActive) {
      loadSessionReview(activeArchiveKey);
    }
  };

  const loadDetail = async (sample: DataFlywheelSample) => {
    const requestSeq = detailRequestSeq.current + 1;
    detailRequestSeq.current = requestSeq;
    setSelectedSample(sample);
    setRightCollapsed(false);
    setLoadingDetail(true);
    try {
      const result = await getSampleDetail(sample.sample_id);
      if (requestSeq !== detailRequestSeq.current) return;
      setDetail(result);
      if (result.sample.request_id) {
        void loadTraceDiagnostics(result.sample.request_id);
      }
      setSelectedPrelabelLabels(result.prelabels[0]?.labels ?? []);
      setSessionAnnotations(null);
      setAnnotationTarget({ type: 'turn', sample });
      const firstLabel = result.labels[0];
      setCurrentLabel(firstLabel?.label ?? DEFAULT_LABEL);
      setComment(firstLabel?.comment ?? '');
    } catch {
      if (requestSeq === detailRequestSeq.current) {
        message.error('加载样本详情失败');
      }
    } finally {
      if (requestSeq === detailRequestSeq.current) {
        setLoadingDetail(false);
      }
    }
  };

  const loadSessionAnnotations = async (sessionId: string) => {
    try {
      const result = await getSessionAnnotations(sessionId);
      setSelectedSample(null);
      setDetail(null);
      setSelectedPrelabelLabels([]);
      setSessionAnnotations(result);
      setSessionAnnotationCache((current) => ({
        ...current,
        [result.session_id]: result,
      }));
      setAnnotationTarget({
        type: 'session',
        sampleId: result.sample_id,
        sessionId: result.session_id,
      });
      const firstLabel = result.labels[0];
      setCurrentLabel(firstLabel?.label ?? DEFAULT_LABEL);
      setComment(firstLabel?.comment ?? '');
      setRightCollapsed(false);
    } catch {
      message.error('加载会话级标注失败');
    }
  };

  const labelBody = (label: DataFlywheelLabel) => {
    if (!annotationTarget) return null;
    if (annotationTarget.type === 'session') {
      return {
        label,
        comment,
        sample_type: 'session',
        session_id: annotationTarget.sessionId,
      };
    }
    const selected = annotationTarget.sample;
    return {
      label,
      comment,
      sample_type: selected.sample_type,
      session_id: selected.session_id ?? undefined,
      turn_id: selected.turn_id,
      request_id: selected.request_id ?? undefined,
    };
  };

  const handleSave = async () => {
    if (!annotationTarget) return;
    const body = labelBody(currentLabel);
    if (!body) return;
    setSaving(true);
    try {
      await addSampleLabel(annotationSampleId(annotationTarget), body);
      message.success('标注已保存');
      await refreshAnnotationTarget(annotationTarget);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('保存标注失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteLabel = async (label: DataFlywheelLabelRecord) => {
    if (!annotationTarget) return;
    setActing(true);
    try {
      await deleteSampleLabel(annotationSampleId(annotationTarget), label.id);
      message.success('标注已删除');
      await refreshAnnotationTarget(annotationTarget);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('删除标注失败');
    } finally {
      setActing(false);
    }
  };

  const handleResolveLabel = async (label: DataFlywheelLabelRecord) => {
    if (!annotationTarget) return;
    setActing(true);
    try {
      await resolveSampleLabel(annotationSampleId(annotationTarget), label.id);
      message.success('标注已标记为已完成');
      await refreshAnnotationTarget(annotationTarget);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('标记已完成失败');
    } finally {
      setActing(false);
    }
  };

  const refreshAnnotationTarget = async (target: AnnotationTarget) => {
    if (target.type === 'session') {
      await loadSessionAnnotations(target.sessionId);
      return;
    }
    await loadDetail(target.sample);
  };

  const handleCopyDebug = async () => {
    if (!detail?.debug_export) {
      message.warning('当前样本没有 debug_export');
      return;
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(detail.debug_export, null, 2));
      message.success('debug JSON 已复制');
    } catch {
      message.error('复制 debug JSON 失败');
    }
  };

  const handleExportJsonl = async () => {
    if (!selectedSample) return;
    setActing(true);
    try {
      const result = await exportSampleJsonl(selectedSample.sample_id);
      await navigator.clipboard.writeText(result.content);
      message.success(`已复制 JSONL：${result.filename}`);
    } catch {
      message.error('导出 JSONL 失败');
    } finally {
      setActing(false);
    }
  };

  const handleMarkBadCase = async () => {
    if (!selectedSample) return;
    const body = labelBody('bad_reply');
    if (!body) return;
    setActing(true);
    try {
      await markBadCase(selectedSample.sample_id, body);
      message.success('已标记 bad case');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('标记 bad case 失败');
    } finally {
      setActing(false);
    }
  };

  const handleCreateRegressionCase = async () => {
    if (!selectedSample) return;
    setActing(true);
    try {
      const result = await createCaseDraft(selectedSample.sample_id, 'evaluation_replay');
      setDraft(result);
      setDraftOpen(true);
      message.success('已生成 regression case 草稿');
    } catch {
      message.error('生成 regression case 失败');
    } finally {
      setActing(false);
    }
  };

  const handleCreatePrelabel = async () => {
    if (!selectedSample) return;
    setPrelabeling(true);
    try {
      const result = await createSamplePrelabel(selectedSample.sample_id);
      setSelectedPrelabelLabels(result.labels);
      message.success('AI 预判已生成');
      await loadDetail(selectedSample);
      await fetchSamples(query);
    } catch {
      message.error('生成 AI 预判失败');
    } finally {
      setPrelabeling(false);
    }
  };

  const handleAcceptPrelabel = async () => {
    const latestPrelabel = detail?.prelabels[0];
    if (!selectedSample || !latestPrelabel) return;
    setReviewingPrelabel(true);
    try {
      await acceptSamplePrelabel(selectedSample.sample_id, latestPrelabel.id, {
        labels: selectedPrelabelLabels,
        comment: comment.trim() || `AI 预判采纳：${latestPrelabel.reason}`,
      });
      message.success('AI 预判已保存为人工标注');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('采纳 AI 预判失败');
    } finally {
      setReviewingPrelabel(false);
    }
  };

  const handleRejectPrelabel = async () => {
    const latestPrelabel = detail?.prelabels[0];
    if (!selectedSample || !latestPrelabel) return;
    setReviewingPrelabel(true);
    try {
      await rejectSamplePrelabel(selectedSample.sample_id, latestPrelabel.id);
      message.success('AI 预判已驳回');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('驳回 AI 预判失败');
    } finally {
      setReviewingPrelabel(false);
    }
  };

  const handleSyncSessions = async () => {
    setSyncingSessions(true);
    const sessionId = isSessionArchiveActive ? activeArchiveKey : undefined;
    try {
      const job = await syncDataFlywheelSessions({
        session_id: sessionId,
        only_missing: true,
        limit: 100,
      });
      message.success(sessionId ? '当前会话同步任务已提交' : '最近会话同步任务已提交');
      await waitForSyncJob(job.job_id);
      await fetchSamples(query);
      if (sessionId) {
        await loadSessionReview(sessionId);
      }
      message.success('会话同步已完成');
    } catch {
      message.error('同步会话失败');
    } finally {
      setSyncingSessions(false);
    }
  };

  const waitForSyncJob = async (jobId: string) => {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      const job = await getDataFlywheelSyncJob(jobId);
      if (job.status === 'completed') return;
      if (job.status === 'failed') {
        throw new Error(job.error || 'SYNC_JOB_FAILED');
      }
      await sleep(1000);
    }
  };

  const handleBatchPrelabel = async () => {
    setBatchPrelabeling(true);
    try {
      const trimmed = searchText.trim();
      const job = await createSamplePrelabelBatch({
        q: trimmed || undefined,
        label: qualityLabel,
        unannotated_only: unannotatedOnly,
        limit: 50,
        skip_existing: true,
      });
      message.success('批量 AI 分析任务已提交');
      const result = await waitForPrelabelBatchJob(job.job_id);
      await fetchSamples(query);
      const created = Number(result?.created ?? 0);
      const skipped = Number(result?.skipped_existing ?? 0);
      const failed = Number(result?.failed ?? 0);
      message.success(`批量 AI 分析完成：新增 ${created}，跳过 ${skipped}，失败 ${failed}`);
    } catch {
      message.error('批量 AI 分析失败');
    } finally {
      setBatchPrelabeling(false);
    }
  };

  const waitForPrelabelBatchJob = async (jobId: string) => {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const job = await getSamplePrelabelBatchJob(jobId);
      if (job.status === 'completed') return job.result ?? null;
      if (job.status === 'failed') {
        throw new Error(job.error || 'PRELABEL_BATCH_JOB_FAILED');
      }
      await sleep(1000);
    }
    return null;
  };

  const clearSelection = () => {
    detailRequestSeq.current += 1;
    setSelectedSample(null);
    setDetail(null);
    setSessionAnnotations(null);
    setAnnotationTarget(null);
    setCurrentLabel(DEFAULT_LABEL);
    setSelectedPrelabelLabels([]);
    setComment('');
    setLoadingDetail(false);
  };

  const refreshSessionReviewIfActive = async () => {
    if (isSessionArchiveActive) {
      await loadSessionReview(activeArchiveKey);
    }
  };

  const handleSelectArchive = (key: string) => {
    setActiveArchiveKey(key);
    clearSelection();
    if (
      key === ALL_ARCHIVE_KEY ||
      key === ISSUE_ARCHIVE_KEY ||
      key === AI_PRELABEL_ARCHIVE_KEY ||
      key === CONFIRMED_ISSUE_ARCHIVE_KEY
    ) {
      sessionReviewRequestSeq.current += 1;
      setSessionReview(null);
      setLoadingSessionReview(false);
      return;
    }
    loadSessionReview(key);
  };

  const handleSelectProblemSession = (key: string) => {
    setActiveArchiveKey(key);
    clearSelection();
    loadSessionReview(key);
    const problemTurn = latestConfirmedProblemTurn(samples, key);
    if (problemTurn) {
      loadDetail(problemTurn);
      return;
    }
    loadSessionAnnotations(key);
  };

  const archiveContent = (
    <SessionArchivePanel
      groups={archiveGroups}
      total={samples.length}
      issueCount={issueCount}
      aiPrelabelCount={aiPrelabelCount}
      confirmedIssueCount={confirmedIssueCount}
      activeKey={activeArchiveKey}
      allKey={ALL_ARCHIVE_KEY}
      issueKey={ISSUE_ARCHIVE_KEY}
      aiPrelabelKey={AI_PRELABEL_ARCHIVE_KEY}
      confirmedIssueKey={CONFIRMED_ISSUE_ARCHIVE_KEY}
      onSelect={handleSelectArchive}
    />
  );
  const mainContent = activeArchiveKey === CONFIRMED_ISSUE_ARCHIVE_KEY ? (
    <SessionArchivePanel
      title="问题会话归档"
      groups={confirmedIssueGroups}
      total={confirmedIssueGroups.reduce((sum, group) => sum + group.total, 0)}
      issueCount={0}
      aiPrelabelCount={0}
      confirmedIssueCount={confirmedIssueCount}
      activeKey=""
      allKey={ALL_ARCHIVE_KEY}
      issueKey={ISSUE_ARCHIVE_KEY}
      aiPrelabelKey={AI_PRELABEL_ARCHIVE_KEY}
      confirmedIssueKey={CONFIRMED_ISSUE_ARCHIVE_KEY}
      showBuckets={false}
      testIdPrefix="problem-session"
      onSelect={handleSelectProblemSession}
    />
  ) : isSessionArchiveActive ? (
    <SessionConversationView
      review={sessionReview}
      loading={loadingSessionReview}
      selectedSampleId={selectedSample?.sample_id}
      traceDiagnosticsByRequestId={traceDiagnosticsByRequestId}
      loadingTraceDiagnostics={loadingTraceDiagnostics}
      onSelectTurn={loadDetail}
      onSelectSession={() => loadSessionAnnotations(activeArchiveKey)}
    />
  ) : (
    <Card
      title="会话 turn"
      extra={
        <Typography.Text style={{ color: palette.textMuted }}>
          会话 turn：{visibleSamples.length} 条
        </Typography.Text>
      }
      style={workspaceCardStyle}
      styles={{ body: { padding: 0, minHeight: 0, flex: 1, overflow: 'hidden' } }}
    >
      <SampleQueueTable
        samples={visibleSamples}
        loading={loadingList}
        selectedSampleId={selectedSample?.sample_id}
        onSelect={loadDetail}
      />
    </Card>
  );
  const detailContent = (
    <div style={detailRailStyle}>
      <ReviewEvidencePanel detail={detail} />
      <SampleDetailPanel
        detail={detail}
        loading={loadingDetail}
        traceDiagnostics={
          detail?.sample.request_id
            ? traceDiagnosticsByRequestId[detail.sample.request_id] ?? null
            : null
        }
        loadingTraceDiagnostics={
          detail?.sample.request_id
            ? Boolean(loadingTraceDiagnostics[detail.sample.request_id])
            : false
        }
      />
      <AnnotationPanel
        selectedSample={annotationTarget ? selectedSample ?? sessionAnnotationPlaceholder(annotationTarget) : null}
        label={currentLabel}
        comment={comment}
        saving={saving}
        acting={acting}
        prelabels={detail?.prelabels ?? selectedSample?.prelabels ?? []}
        canPrelabel={annotationTarget?.type === 'turn' && !!selectedSample}
        prelabeling={prelabeling}
        reviewingPrelabel={reviewingPrelabel}
        selectedPrelabelLabels={selectedPrelabelLabels}
        annotationTargetLabel={annotationTargetLabel(annotationTarget)}
        existingLabels={annotationLabels(detail, sessionAnnotations)}
        sessionProblemItems={sessionProblemItems(samples, activeArchiveKey)}
        onLabelChange={setCurrentLabel}
        onCommentChange={setComment}
        onSelectSessionProblem={loadDetail}
        onSelectedPrelabelLabelsChange={setSelectedPrelabelLabels}
        onCreatePrelabel={handleCreatePrelabel}
        onAcceptPrelabel={handleAcceptPrelabel}
        onRejectPrelabel={handleRejectPrelabel}
        onSave={handleSave}
        onDeleteLabel={handleDeleteLabel}
        onResolveLabel={handleResolveLabel}
        onCopyDebug={handleCopyDebug}
        onExportJsonl={handleExportJsonl}
        onMarkBadCase={handleMarkBadCase}
        onCreateRegressionCase={handleCreateRegressionCase}
      />
    </div>
  );

  return (
    <div style={pageShellStyle}>
      <Space direction="vertical" size={4} style={{ flexShrink: 0 }}>
        <Typography.Title level={4} style={{ color: palette.text, margin: 0 }}>
          Agent 数据飞轮
        </Typography.Title>
        <Typography.Text style={{ color: palette.textMuted }}>
          真实会话与调试事件样本标注工作台，用于沉淀 Agent 回复调优与回归样本。
        </Typography.Text>
      </Space>

      <Card size="small" style={filterCardStyle} styles={{ body: { padding: 12 } }}>
        <Space wrap>
          <Input
            allowClear
            placeholder="Session / Request ID"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            onPressEnter={submitQuery}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder="质量标签"
            value={qualityLabel}
            onChange={setQualityLabel}
            options={labelOptions}
            style={{ width: 180 }}
          />
          <Checkbox checked={unannotatedOnly} onChange={(event) => setUnannotatedOnly(event.target.checked)}>
            只看未标注
          </Checkbox>
          <Checkbox checked={hideAiNormal} onChange={(event) => setHideAiNormal(event.target.checked)}>
            隐藏 AI 判定正常
          </Checkbox>
          <Button type="primary" icon={<SearchOutlined />} loading={loadingList} onClick={submitQuery}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} loading={loadingList} onClick={refreshSamples}>
            刷新
          </Button>
          <Button icon={<CloudSyncOutlined />} loading={syncingSessions} onClick={handleSyncSessions}>
            同步会话
          </Button>
          <Button
            icon={<CloudSyncOutlined />}
            loading={batchPrelabeling}
            disabled={loadingList}
            onClick={handleBatchPrelabel}
          >
            批量 AI 分析
          </Button>
          <Typography.Text style={{ color: palette.textMuted }}>共 {total} 条</Typography.Text>
        </Space>
      </Card>

      <CollapsibleWorkspace
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onLeftCollapsedChange={setLeftCollapsed}
        onRightCollapsedChange={setRightCollapsed}
        left={archiveContent}
        main={mainContent}
        right={detailContent}
      />

      <CaseDraftPreview draft={draft} open={draftOpen} onClose={() => setDraftOpen(false)} />
    </div>
  );
}

const pageShellStyle: CSSProperties = {
  color: palette.text,
  height: 'calc(100vh - 134px)',
  minHeight: 620,
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
  overflow: 'hidden',
};

const filterCardStyle: CSSProperties = {
  ...cardStyle,
  flexShrink: 0,
};

const workspaceCardStyle: CSSProperties = {
  ...cardStyle,
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  minHeight: 0,
};

const detailRailStyle: CSSProperties = {
  height: '100%',
  minHeight: 0,
  overflow: 'auto',
  paddingRight: 2,
  scrollbarGutter: 'stable',
};

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isAiNormalSample(sample: DataFlywheelSample) {
  const prelabel = latestAiPrelabel(sample);
  if (!prelabel || !hasPendingAiPrelabel(sample)) return false;
  if (prelabel.confidence < 0.85) return false;
  const labels = new Set(prelabel.labels);
  const normalLabel = labels.has('good_reply') || labels.has('not_actionable');
  const lowRiskSeverity = prelabel.severity === 'low' || prelabel.severity === 'medium';
  return normalLabel && lowRiskSeverity;
}

function hasPendingAiPrelabel(sample: DataFlywheelSample) {
  return latestAiPrelabel(sample)?.status === 'pending';
}

function latestAiPrelabel(sample: DataFlywheelSample) {
  return sample.latest_prelabel ?? sample.prelabels?.[0] ?? null;
}

function annotationSampleId(target: AnnotationTarget) {
  return target.type === 'session' ? target.sampleId : target.sample.sample_id;
}

function annotationLabels(
  detail: DataFlywheelDetail | null,
  sessionAnnotations: DataFlywheelSessionAnnotations | null
) {
  return sessionAnnotations?.labels ?? detail?.labels ?? [];
}

function mergeSessionAnnotations(
  cached: DataFlywheelSessionAnnotations[],
  active: DataFlywheelSessionAnnotations | null
) {
  if (!active) return cached;
  return [
    ...cached.filter((item) => item.session_id !== active.session_id),
    active,
  ];
}

function annotationTargetLabel(target: AnnotationTarget | null) {
  if (!target) return undefined;
  if (target.type === 'session') return '完整会话';
  return `turn #${target.sample.turn_id}`;
}

function sessionAnnotationPlaceholder(target: AnnotationTarget): DataFlywheelSample | null {
  if (target.type !== 'session') return null;
  return {
    sample_id: target.sampleId,
    sample_type: 'session',
    quality_labels: [],
    annotation_status: 'unlabeled',
    session_id: target.sessionId,
    turn_id: 0,
    request_id: null,
    user_input_preview: '完整会话',
    assistant_reply_preview: null,
    selected_tools: [],
    actual_tools: [],
    issue_candidates: [],
    token_total: null,
    latency_ms: null,
    source_type: 'session',
    created_at: null,
  };
}

function sessionArchiveKey(sample: DataFlywheelSample) {
  return sample.session_id ?? 'unknown-session';
}

function emptyTraceDiagnostics(requestId: string): TraceDiagnostics {
  return {
    request_id: requestId,
    reflection_checks: [],
    reflection_diagnostic: {
      blocked: false,
      decisions: [],
      issue_codes: [],
    },
  };
}

function latestConfirmedProblemTurn(samples: DataFlywheelSample[], sessionKey: string) {
  return confirmedProblemTurns(samples, sessionKey)[0];
}

function sessionProblemItems(samples: DataFlywheelSample[], sessionKey: string) {
  return confirmedProblemTurns(samples, sessionKey).map((sample) => ({ sample }));
}

function confirmedProblemTurns(samples: DataFlywheelSample[], sessionKey: string) {
  return samples
    .filter((sample) => sessionArchiveKey(sample) === sessionKey && hasTurnConfirmedIssue(sample))
    .sort((left, right) => right.turn_id - left.turn_id);
}

function hasTurnConfirmedIssue(sample: DataFlywheelSample) {
  return sample.quality_labels.some((label) => confirmedIssueLabels.has(label));
}

function hasSessionConfirmedIssue(
  sample: DataFlywheelSample,
  sessionAnnotations: DataFlywheelSessionAnnotations[] = []
) {
  return sessionQualityLabels(sample, sessionAnnotations).some((label) => confirmedIssueLabels.has(label));
}

function confirmedIssueTotal(
  samples: DataFlywheelSample[],
  sessionAnnotations: DataFlywheelSessionAnnotations[] = []
) {
  const sessionIssueKeys = new Set<string>();
  let total = 0;
  samples.forEach((sample) => {
    if (hasTurnConfirmedIssue(sample)) {
      total += 1;
    }
    if (hasSessionConfirmedIssue(sample, sessionAnnotations)) {
      sessionIssueKeys.add(sessionArchiveKey(sample));
    }
  });
  return total + sessionIssueKeys.size;
}

const confirmedIssueLabels = new Set<DataFlywheelLabel>([
  'bad_reply',
  'wrong_tool_selection',
  'pending_missed',
  'hallucinated_execution',
  'off_topic',
  'sensitive_info_leak',
  'missing_wage',
  'disabled_worker_used',
  'needs_regression',
]);

function buildArchiveGroups(
  samples: DataFlywheelSample[],
  sessionAnnotations: DataFlywheelSessionAnnotations[] = []
): SessionArchiveItem[] {
  const groups = new Map<string, SessionArchiveItem>();
  const countedSessionIssues = new Set<string>();

  samples.forEach((sample) => {
    const key = sessionArchiveKey(sample);
    const current = groups.get(key);
    const turnBadCase = hasTurnConfirmedIssue(sample);
    const sessionLabels = sessionQualityLabels(sample, sessionAnnotations);
    const sessionBadCase = sessionLabels.some((label) => confirmedIssueLabels.has(label)) && !countedSessionIssues.has(key);
    if (sessionBadCase) {
      countedSessionIssues.add(key);
    }
    const badCaseCount = (turnBadCase ? 1 : 0) + (sessionBadCase ? 1 : 0);
    const sessionLabelCount = sessionLabels.length;

    if (!current) {
      groups.set(key, {
        key,
        sessionId: sample.session_id,
        total: 1,
        unannotated: sample.annotation_status === 'unlabeled' ? 1 : 0,
        sessionLabels: sessionLabelCount,
        badCases: badCaseCount,
        latestTurnId: sample.turn_id,
        latestInputPreview: sample.user_input_preview,
      });
      return;
    }

    current.total += 1;
    current.unannotated += sample.annotation_status === 'unlabeled' ? 1 : 0;
    current.sessionLabels = Math.max(current.sessionLabels, sessionLabelCount);
    current.badCases += badCaseCount;
    if (sample.turn_id >= current.latestTurnId) {
      current.latestTurnId = sample.turn_id;
      current.latestInputPreview = sample.user_input_preview;
    }
  });

  return Array.from(groups.values()).sort((left, right) => right.latestTurnId - left.latestTurnId);
}

function sessionQualityLabels(
  sample: DataFlywheelSample,
  sessionAnnotations: DataFlywheelSessionAnnotations[] = []
) {
  const overlay = sessionAnnotations.find(
    (item) => item.session_id === sample.session_id
  );
  return overlay?.quality_labels ?? sample.session_quality_labels ?? [];
}
