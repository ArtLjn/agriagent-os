import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { Button, Card, Checkbox, Empty, Input, Modal, Select, Space, Spin, Tabs, Tag, Typography, message } from 'antd';
import { CloudDownloadOutlined, CloudSyncOutlined, DatabaseOutlined, EditOutlined, FolderOpenOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';

import {
  getTraceDiagnostics,
  type TraceDiagnostics,
} from '../../api/admin';
import {
  acceptSamplePrelabel,
  addSampleLabel,
  createCaseDraft,
  createRepairPack,
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
  listRepairPackCandidates,
  markBadCase,
  markRepairPackResolved,
  recordRepairPackVerificationFailure,
  rejectSamplePrelabel,
  resolveSampleLabel,
  syncDataFlywheelSessions,
  type CaseDraft,
  type DataFlywheelDetail,
  type DataFlywheelLabel,
  type DataFlywheelLabelRecord,
  type DataFlywheelRepairCandidate,
  type DataFlywheelRepairPack,
  type DataFlywheelSample,
  type DataFlywheelSessionAnnotations,
  type DataFlywheelSessionReview,
} from '../../api/dataFlywheel';
import { cardStyle, palette } from '../../styles/theme';
import AnnotationPanel from './components/AnnotationPanel';
import CaseDraftPreview from './components/CaseDraftPreview';
import CollapsibleWorkspace from './components/CollapsibleWorkspace';
import DailyReviewWorkbench from './components/DailyReviewWorkbench';
import SampleDetailPanel from './components/SampleDetailPanel';
import SampleQueueTable from './components/SampleQueueTable';
import SessionConversationView from './components/SessionConversationView';
import SessionArchivePanel, { type SessionArchiveItem } from './components/SessionArchivePanel';
import RepairPackListPanel from './components/RepairPackListPanel';
import ReviewEvidencePanel from './components/ReviewEvidencePanel';
import RepairPackPreview from './components/RepairPackPreview';

const DEFAULT_LABEL: DataFlywheelLabel = 'good_reply';
const ALL_ARCHIVE_KEY = '__all__';
const ISSUE_ARCHIVE_KEY = '__issues__';
const AI_PRELABEL_ARCHIVE_KEY = '__ai_prelabels__';
const CONFIRMED_ISSUE_ARCHIVE_KEY = '__confirmed_issues__';

interface SampleQuery {
  searchText: string;
  qualityLabel?: DataFlywheelLabel;
  unannotatedOnly: boolean;
  sortBy: 'risk' | 'time';
  hideLowRisk: boolean;
  severity: 'P0' | 'P1' | 'all';
}

type AnnotationTarget =
  | { type: 'turn'; sample: DataFlywheelSample }
  | { type: 'session'; sampleId: string; sessionId: string };

type DataFlywheelTab = 'daily-review' | 'advanced-search' | 'repair-packs' | 'datasets-evaluation';
type AdvancedSearchTab = 'queue' | 'candidates' | 'sessions' | 'turn-review';
type HeaderTone = 'queue' | 'candidate' | 'session' | 'turn';

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
  const initialSortBy = new URLSearchParams(window.location.search).get('sort') === 'time' ? 'time' : 'risk';
  const [sortBy, setSortBy] = useState<'risk' | 'time'>(initialSortBy);
  const [hideLowRisk, setHideLowRisk] = useState(false);
  const [riskSeverity, setRiskSeverity] = useState<'P0' | 'P1' | 'all'>('all');
  const [query, setQuery] = useState<SampleQuery>({
    searchText: '',
    qualityLabel: undefined,
    unannotatedOnly: false,
    sortBy: initialSortBy,
    hideLowRisk: false,
    severity: 'all',
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
  const [repairPack, setRepairPack] = useState<DataFlywheelRepairPack | null>(null);
  const [repairPackOpen, setRepairPackOpen] = useState(false);
  const [repairCandidate, setRepairCandidate] = useState<DataFlywheelRepairCandidate | null>(null);
  const [selectedProblemSessionKeys, setSelectedProblemSessionKeys] = useState<string[]>([]);
  const [activeArchiveKey, setActiveArchiveKey] = useState(ALL_ARCHIVE_KEY);
  const [sessionReview, setSessionReview] = useState<DataFlywheelSessionReview | null>(null);
  const [loadingSessionReview, setLoadingSessionReview] = useState(false);
  const [traceDiagnosticsByRequestId, setTraceDiagnosticsByRequestId] = useState<Record<string, TraceDiagnostics>>({});
  const [loadingTraceDiagnostics, setLoadingTraceDiagnostics] = useState<Record<string, boolean>>({});
  const [syncingSessions, setSyncingSessions] = useState(false);
  const [batchPrelabeling, setBatchPrelabeling] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<DataFlywheelTab>('daily-review');
  const [activeAdvancedTab, setActiveAdvancedTab] = useState<AdvancedSearchTab>('queue');
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
  const selectedRepairSampleIds = useMemo(
    () => confirmedProblemSampleIds(samples, selectedProblemSessionKeys),
    [samples, selectedProblemSessionKeys]
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
  const candidateSamples = useMemo(
    () => samples.filter(isProblemCandidateSample),
    [samples]
  );
  const candidateVisibleSamples = useMemo(() => {
    if (activeArchiveKey === ISSUE_ARCHIVE_KEY) {
      return visibleSamples.filter((sample) => sample.issue_candidates.length > 0);
    }
    if (activeArchiveKey === AI_PRELABEL_ARCHIVE_KEY) {
      return visibleSamples.filter(hasPendingAiPrelabel);
    }
    return candidateSamples;
  }, [activeArchiveKey, candidateSamples, visibleSamples]);
  const p0Count = useMemo(
    () => samples.filter((sample) => sample.risk_severity === 'P0').length,
    [samples]
  );
  const missingEventCount = useMemo(
    () => samples.filter((sample) => sample.event_log_status === 'missing').length,
    [samples]
  );
  const reviewSamples = useMemo(
    () => selectedSample ? [selectedSample] : candidateSamples,
    [candidateSamples, selectedSample]
  );
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
        sort: nextQuery.sortBy,
        min_risk: nextQuery.hideLowRisk ? 0.3 : undefined,
        severity: nextQuery.severity === 'all' ? undefined : nextQuery.severity,
        q: trimmed || undefined,
      });
      if (requestSeq !== listRequestSeq.current) return;
      setSamples(result.items);
      setTotal(result.total);
      const problemSessionKeys = new Set(
        result.items
          .filter(hasTurnConfirmedIssue)
          .map(sessionArchiveKey)
      );
      setSelectedProblemSessionKeys((current) =>
        current.filter((key) => problemSessionKeys.has(key))
      );
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

  const applyQuery = (nextQuery: SampleQuery) => {
    setActiveArchiveKey(ALL_ARCHIVE_KEY);
    setSessionReview(null);
    clearSelection();
    setQuery(nextQuery);
  };

  const currentQuery = (
    overrides: Partial<Pick<SampleQuery, 'sortBy' | 'hideLowRisk' | 'severity'>> = {}
  ): SampleQuery => ({
      searchText,
      qualityLabel,
      unannotatedOnly,
      sortBy,
      hideLowRisk,
      severity: riskSeverity,
      ...overrides,
  });

  const submitQuery = () => {
    applyQuery(currentQuery());
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
      void loadRepairCandidate(sample.sample_id);
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
      setRepairCandidate(null);
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

  const loadRepairCandidate = async (sampleId: string) => {
    try {
      const result = await listRepairPackCandidates({
        sample_ids: [sampleId],
        limit: 1,
      });
      setRepairCandidate(result.items[0] ?? null);
    } catch {
      setRepairCandidate(null);
    }
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

  const handleCreateRepairPack = async () => {
    if (!selectedSample) return;
    setActing(true);
    try {
      const result = await createRepairPack({
        sample_ids: [selectedSample.sample_id],
        limit: 1,
      });
      setRepairPack(result);
      setRepairPackOpen(true);
      if (result.deduplicated) {
        message.info(`检测到重复，已复用 pack ${result.pack_id}`);
      } else {
        message.success('已生成失败案例修复包');
      }
    } catch {
      message.error('生成修复包失败');
    } finally {
      setActing(false);
    }
  };

  const handleCreateBatchRepairPack = async () => {
    if (selectedRepairSampleIds.length === 0) return;
    setActing(true);
    try {
      const result = await createRepairPack({
        sample_ids: selectedRepairSampleIds,
        limit: selectedRepairSampleIds.length,
      });
      setRepairPack(result);
      setRepairPackOpen(true);
      if (result.deduplicated) {
        message.info(`检测到重复，已复用 pack ${result.pack_id}`);
      } else {
        message.success(`已生成 ${selectedRepairSampleIds.length} 条失败案例修复包`);
      }
    } catch {
      message.error('批量生成修复包失败，请按修复目标分组后重试');
    } finally {
      setActing(false);
    }
  };

  const handleOpenRepairPackDetail = useCallback((pack: DataFlywheelRepairPack) => {
    setRepairPack(pack);
    setRepairPackOpen(true);
  }, []);

  const handleResolveRepairPack = async () => {
    if (!repairPack) return;
    setActing(true);
    try {
      const result = await markRepairPackResolved(repairPack.pack_id, {
        repair_note: 'vibecoding 修复完成并通过验证',
        verification_summary: { passed: true },
      });
      setRepairPack(result);
      message.success('修复包已标记为已修复');
      await fetchSamples(query);
      if (selectedSample) {
        await loadDetail(selectedSample);
      }
      await refreshSessionReviewIfActive();
    } catch {
      message.error('标记修复包失败');
    } finally {
      setActing(false);
    }
  };

  const handleFailRepairPackVerification = async () => {
    if (!repairPack) return;
    Modal.confirm({
      title: '记录验证失败',
      content: '这会保留关联 bad labels 为 open，方便继续修复。',
      okText: '记录失败',
      cancelText: '取消',
      onOk: async () => {
        setActing(true);
        try {
          const result = await recordRepairPackVerificationFailure(repairPack.pack_id, {
            verification_summary: { passed: false },
          });
          setRepairPack(result);
          message.warning('已记录验证失败，标签保持未解决');
          await fetchSamples(query);
        } catch {
          message.error('记录验证失败失败');
        } finally {
          setActing(false);
        }
      },
    });
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
    setRepairCandidate(null);
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
    setActiveTab('advanced-search');
    setActiveAdvancedTab(tabForArchiveKey(key));
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
    setActiveTab('advanced-search');
    setActiveAdvancedTab('sessions');
    clearSelection();
    loadSessionReview(key);
    const problemTurn = latestConfirmedProblemTurn(samples, key);
    if (problemTurn) {
      loadDetail(problemTurn);
      return;
    }
    loadSessionAnnotations(key);
  };

  const filterBar = (
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
        <Checkbox
          checked={hideLowRisk}
          onChange={(event) => {
            const checked = event.target.checked;
            setHideLowRisk(checked);
            applyQuery(currentQuery({ hideLowRisk: checked }));
          }}
        >
          隐藏低风险
        </Checkbox>
        <Checkbox
          checked={riskSeverity === 'P0'}
          onChange={(event) => {
            const severity = event.target.checked ? 'P0' : 'all';
            setRiskSeverity(severity);
            applyQuery(currentQuery({ severity }));
          }}
        >
          P0 严重
        </Checkbox>
        <Select
          aria-label="排序方式"
          value={sortBy}
          onChange={(value) => {
            setSortBy(value);
            applyQuery(currentQuery({ sortBy: value }));
          }}
          options={[
            { label: '风险排序', value: 'risk' },
            { label: '时间排序', value: 'time' },
          ]}
          style={{ width: 116 }}
        />
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
        <Button
          aria-label="批量导出修复包"
          icon={<CloudDownloadOutlined />}
          loading={acting}
          disabled={selectedRepairSampleIds.length === 0}
          onClick={handleCreateBatchRepairPack}
        >
          {selectedRepairSampleIds.length > 0
            ? `批量导出修复包 ${selectedRepairSampleIds.length}`
            : '批量导出修复包'}
        </Button>
        <Typography.Text style={{ color: palette.textMuted }}>共 {total} 条</Typography.Text>
      </Space>
    </Card>
  );

  const archiveContent = (
    <SessionArchivePanel
      title={null}
      orientation="horizontal"
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

  const queueMainContent = (
    <SampleListCard
      title="全部 turn"
      count={visibleSamples.length}
      samples={visibleSamples}
      loading={loadingList}
      selectedSampleId={selectedSample?.sample_id}
      onSelect={loadDetail}
    />
  );

  const candidateMainContent = (
    <CandidateTriageBoard
      samples={candidateVisibleSamples}
      loading={loadingList}
      selectedSampleId={selectedSample?.sample_id}
      onSelect={loadDetail}
    />
  );

  const sessionMainContent = activeArchiveKey === CONFIRMED_ISSUE_ARCHIVE_KEY ? (
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
      selectedKeys={selectedProblemSessionKeys}
      onSelectedKeysChange={setSelectedProblemSessionKeys}
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
    <EmptyCard title="Session 复盘" description="从顶部会话归档选择一个 session 查看完整对话" />
  );

  const turnReviewMainContent = selectedSample ? (
    <TurnReviewWorkbench
      sample={selectedSample}
      detail={detail}
      loading={loadingDetail}
      traceDiagnosticsByRequestId={traceDiagnosticsByRequestId}
      loadingTraceDiagnostics={loadingTraceDiagnostics}
      onSelectTurn={loadDetail}
      onSelectSession={() => selectedSample.session_id && loadSessionAnnotations(selectedSample.session_id)}
    />
  ) : (
    <SampleListCard
      title="待审核 turn"
      count={reviewSamples.length}
      samples={reviewSamples}
      loading={loadingList}
      onSelect={loadDetail}
      emptyText="从样本队列或问题候选选择一个 turn"
    />
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
        repairCandidate={repairCandidate}
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
        onCreateRepairPack={handleCreateRepairPack}
      />
    </div>
  );

  const queueContent = (
    <>
      <WorkbenchHeader
        title="样本队列"
        description="保留正常对话和全部 turn，用于浏览、搜索、回溯原始样本。"
        tone="queue"
        stats={[
          { label: '当前样本', value: visibleSamples.length },
          { label: '正常对话保留', value: Math.max(0, visibleSamples.length - candidateVisibleSamples.length) },
          { label: '事件缺失', value: missingEventCount },
        ]}
        flow="浏览原始 turn -> 选择样本 -> 右侧查看证据 / 标注"
      />
      {filterBar}
      <CollapsibleWorkspace
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onLeftCollapsedChange={setLeftCollapsed}
        onRightCollapsedChange={setRightCollapsed}
        left={archiveContent}
        main={queueMainContent}
        right={detailContent}
      />
    </>
  );

  const candidateContent = (
    <>
      <WorkbenchHeader
        title="问题候选"
        description="只处理规则命中、AI 预判或风险分较高的 turn，默认不展示正常对话。"
        tone="candidate"
        stats={[
          { label: '候选 turn', value: candidateVisibleSamples.length },
          { label: '规则命中', value: issueCount },
          { label: 'AI 待审', value: aiPrelabelCount },
          { label: 'P0', value: p0Count },
        ]}
        flow="先判优先级 -> 打开单 turn -> 采纳 / 驳回 / 标注"
      />
      {filterBar}
      <CollapsibleWorkspace
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onLeftCollapsedChange={setLeftCollapsed}
        onRightCollapsedChange={setRightCollapsed}
        left={archiveContent}
        main={candidateMainContent}
        right={detailContent}
      />
    </>
  );

  const sessionContent = (
    <>
      <WorkbenchHeader
        title="Session 复盘"
        description="按完整会话复盘上下文，保存 session 级标签；选择 turn 后可进入 turn 级审核。"
        tone="session"
        stats={[
          { label: '会话归档', value: archiveGroups.length },
          { label: '问题会话', value: confirmedIssueGroups.length },
          { label: '已标注问题', value: confirmedIssueCount },
        ]}
        flow="选择 session -> 看完整上下文 -> 标注整个会话或下钻 turn"
      />
      {filterBar}
      <CollapsibleWorkspace
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onLeftCollapsedChange={setLeftCollapsed}
        onRightCollapsedChange={setRightCollapsed}
        left={archiveContent}
        main={sessionMainContent}
        right={detailContent}
      />
    </>
  );

  const turnReviewContent = (
    <>
      <WorkbenchHeader
        title="Turn 审核"
        description="聚焦单轮输入、回复、工具链路、pending lifecycle、AI 预判和 turn 级标注。"
        tone="turn"
        stats={[
          { label: '当前 turn', value: selectedSample ? `#${selectedSample.turn_id}` : '-' },
          { label: '风险', value: selectedSample?.risk_score?.toFixed(2) ?? '-' },
          { label: '工具链路', value: selectedSample ? `${selectedSample.selected_tools.length}/${selectedSample.actual_tools.length}` : '-' },
        ]}
        flow="核对用户输入 -> 对比回复和工具 -> 保存 turn 级结论"
      />
      {filterBar}
      <CollapsibleWorkspace
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onLeftCollapsedChange={setLeftCollapsed}
        onRightCollapsedChange={setRightCollapsed}
        left={archiveContent}
        main={turnReviewMainContent}
        right={detailContent}
      />
    </>
  );

  const advancedSearchContent = (
    <Tabs
      activeKey={activeAdvancedTab}
      onChange={(key) => setActiveAdvancedTab(key as AdvancedSearchTab)}
      destroyOnHidden
      items={[
        {
          key: 'queue',
          label: (
            <span>
              <EditOutlined /> 样本队列
            </span>
          ),
          children: queueContent,
        },
        {
          key: 'candidates',
          label: (
            <span>
              <SearchOutlined /> 问题候选
            </span>
          ),
          children: candidateContent,
        },
        {
          key: 'sessions',
          label: (
            <span>
              <FolderOpenOutlined /> Session 复盘
            </span>
          ),
          children: sessionContent,
        },
        {
          key: 'turn-review',
          label: (
            <span>
              <EditOutlined /> Turn 审核
            </span>
          ),
          children: turnReviewContent,
        },
      ]}
    />
  );

  const datasetsEvaluationContent = (
    <Card title="数据集/评测" style={workspaceCardStyle}>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="数据集、simulation 与 evaluation 趋势入口将在后续切片接入" />
    </Card>
  );

  return (
    <div style={pageShellStyle}>
      <Space direction="vertical" size={4} style={{ flexShrink: 0 }}>
        <Typography.Title level={3} style={{ color: palette.text, margin: 0 }}>
          Agent 数据飞轮
        </Typography.Title>
        <Typography.Text style={{ color: palette.textMuted }}>
          将真实对话沉淀为问题候选、session 复盘、turn 审核和修复包闭环。
        </Typography.Text>
      </Space>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as DataFlywheelTab)}
        destroyOnHidden
        items={[
          {
            key: 'daily-review',
            label: (
              <span>
                <EditOutlined /> 每日质检
              </span>
            ),
            children: <DailyReviewWorkbench />,
          },
          {
            key: 'advanced-search',
            label: (
              <span>
                <SearchOutlined /> 高级搜索
              </span>
            ),
            children: advancedSearchContent,
          },
          {
            key: 'repair-packs',
            label: (
              <span>
                <FolderOpenOutlined /> 修复包
              </span>
            ),
            children: <RepairPackListPanel onOpenDetail={handleOpenRepairPackDetail} />,
          },
          {
            key: 'datasets-evaluation',
            label: (
              <span>
                <DatabaseOutlined /> 数据集/评测
              </span>
            ),
            children: datasetsEvaluationContent,
          },
        ]}
      />

      <CaseDraftPreview draft={draft} open={draftOpen} onClose={() => setDraftOpen(false)} />
      <RepairPackPreview
        pack={repairPack}
        open={repairPackOpen}
        acting={acting}
        onClose={() => setRepairPackOpen(false)}
        onResolve={handleResolveRepairPack}
        onVerificationFailed={handleFailRepairPackVerification}
      />
    </div>
  );
}

const pageShellStyle: CSSProperties = {
  color: palette.text,
  minHeight: 'calc(100vh - 134px)',
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
  overflow: 'visible',
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

function workbenchHeaderStyle(tone: HeaderTone): CSSProperties {
  const colorByTone: Record<HeaderTone, string> = {
    queue: palette.accent,
    candidate: palette.warning,
    session: palette.purple,
    turn: palette.success,
  };
  const color = colorByTone[tone];
  return {
    flexShrink: 0,
    display: 'grid',
    gridTemplateColumns: 'minmax(260px, 1.1fr) minmax(360px, 1.4fr) minmax(260px, 0.9fr)',
    gap: 14,
    alignItems: 'stretch',
    padding: '14px 16px',
    border: `1px solid ${palette.border}`,
    borderLeft: `4px solid ${color}`,
    borderRadius: 8,
    background: `linear-gradient(90deg, ${color}1f, ${palette.bgElevated} 34%, ${palette.bgElevated})`,
  };
}

const headerStatsStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(104px, 1fr))',
  gap: 8,
};

const headerStatStyle: CSSProperties = {
  minWidth: 0,
  padding: '8px 10px',
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  background: 'rgba(13, 17, 23, 0.46)',
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
};

const headerFlowStyle: CSSProperties = {
  color: palette.textMuted,
  border: `1px dashed ${palette.borderSoft}`,
  borderRadius: 6,
  padding: '10px 12px',
  alignSelf: 'stretch',
  display: 'flex',
  alignItems: 'center',
};

const triageBoardStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(220px, 1fr))',
  gap: 12,
  alignItems: 'start',
  minHeight: '100%',
};

function triageColumnStyle(color: string): CSSProperties {
  return {
    minWidth: 0,
    minHeight: 260,
    padding: 10,
    border: `1px solid ${palette.border}`,
    borderTop: `3px solid ${color}`,
    borderRadius: 8,
    background: palette.bg,
  };
}

const emptyLaneStyle: CSSProperties = {
  padding: '24px 10px',
  border: `1px dashed ${palette.borderSoft}`,
  borderRadius: 6,
  color: palette.textMuted,
  textAlign: 'center',
  fontSize: 12,
};

function candidateCardStyle(active: boolean): CSSProperties {
  return {
    width: '100%',
    border: `1px solid ${active ? palette.accentStrong : palette.borderSoft}`,
    borderRadius: 8,
    background: active ? 'rgba(31, 111, 235, 0.14)' : palette.bgElevated,
    color: palette.text,
    cursor: 'pointer',
    padding: 10,
  };
}

const turnWorkbenchStyle: CSSProperties = {
  display: 'grid',
  gridTemplateRows: 'max-content minmax(0, 1fr)',
  gap: 12,
  height: '100%',
  minHeight: 0,
};

const turnSummaryCardStyle: CSSProperties = {
  ...cardStyle,
  flexShrink: 0,
};

const turnAuditGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
  gap: 8,
};

const auditFactStyle: CSSProperties = {
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  padding: '8px 10px',
  borderRadius: 6,
  background: palette.bg,
  border: `1px solid ${palette.borderSoft}`,
};

function WorkbenchHeader({
  title,
  description,
  tone,
  stats,
  flow,
}: {
  title: string;
  description: string;
  tone: HeaderTone;
  stats: Array<{ label: string; value: string | number }>;
  flow: string;
}) {
  return (
    <div style={workbenchHeaderStyle(tone)}>
      <Space direction="vertical" size={4} style={{ minWidth: 260 }}>
        <Typography.Title level={4} style={{ color: palette.text, margin: 0 }}>
          {title}
        </Typography.Title>
        <Typography.Text style={{ color: palette.textMuted }}>{description}</Typography.Text>
      </Space>
      <div style={headerStatsStyle}>
        {stats.map((stat) => (
          <div key={stat.label} style={headerStatStyle}>
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{stat.label}</Typography.Text>
            <Typography.Text strong style={{ color: palette.text, fontSize: 18 }}>{stat.value}</Typography.Text>
          </div>
        ))}
      </div>
      <Typography.Text style={headerFlowStyle}>{flow}</Typography.Text>
    </div>
  );
}

function SampleListCard({
  title,
  count,
  samples,
  loading,
  selectedSampleId,
  emptyText = '暂无样本',
  onSelect,
}: {
  title: string;
  count: number;
  samples: DataFlywheelSample[];
  loading: boolean;
  selectedSampleId?: string;
  emptyText?: string;
  onSelect: (sample: DataFlywheelSample) => void;
}) {
  return (
    <Card
      title={title}
      extra={
        <Typography.Text style={{ color: palette.textMuted }}>
          {title}：{count} 条
        </Typography.Text>
      }
      style={workspaceCardStyle}
      styles={{ body: { padding: 0, minHeight: 0, flex: 1, overflow: 'hidden' } }}
    >
      {samples.length === 0 && !loading ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
      ) : (
        <SampleQueueTable
          samples={samples}
          loading={loading}
          selectedSampleId={selectedSampleId}
          onSelect={onSelect}
        />
      )}
    </Card>
  );
}

function EmptyCard({ title, description }: { title: string; description: string }) {
  return (
    <Card title={title} style={workspaceCardStyle}>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />
    </Card>
  );
}

function CandidateTriageBoard({
  samples,
  loading,
  selectedSampleId,
  onSelect,
}: {
  samples: DataFlywheelSample[];
  loading: boolean;
  selectedSampleId?: string;
  onSelect: (sample: DataFlywheelSample) => void;
}) {
  const p0Samples = samples.filter((sample) => sample.risk_severity === 'P0' || (sample.risk_score ?? 0) >= 0.7);
  const p0Ids = new Set(p0Samples.map((sample) => sample.sample_id));
  const aiSamples = samples.filter((sample) => hasPendingAiPrelabel(sample) && !p0Ids.has(sample.sample_id));
  const assignedFirstPassIds = new Set([...p0Ids, ...aiSamples.map((sample) => sample.sample_id)]);
  const ruleSamples = samples.filter(
    (sample) => sample.issue_candidates.length > 0 && !assignedFirstPassIds.has(sample.sample_id)
  );
  const buckets = [
    {
      key: 'p0',
      title: 'P0 / 高风险',
      description: '先处理会造成错误执行或严重误导的 turn',
      color: palette.danger,
      samples: p0Samples,
    },
    {
      key: 'ai',
      title: 'AI 待确认',
      description: '模型已给出判断，等待人工采纳或驳回',
      color: palette.accent,
      samples: aiSamples,
    },
    {
      key: 'rule',
      title: '规则候选',
      description: '规则命中但需要结合上下文确认',
      color: palette.warning,
      samples: ruleSamples,
    },
  ];
  const assignedIds = new Set(buckets.flatMap((bucket) => bucket.samples.map((sample) => sample.sample_id)));
  const uncategorizedSamples = samples.filter((sample) => !assignedIds.has(sample.sample_id));
  const visibleBuckets = uncategorizedSamples.length > 0
    ? [
        ...buckets,
        {
          key: 'other',
          title: '其他风险',
          description: '风险分或 judge 信号较高，需要抽检',
          color: palette.purple,
          samples: uncategorizedSamples,
        },
      ]
    : buckets;

  return (
    <Card
      title="候选处理看板"
      extra={<Typography.Text style={{ color: palette.textMuted }}>待处理：{samples.length} 条</Typography.Text>}
      style={workspaceCardStyle}
      styles={{ body: { padding: 12, minHeight: 0, flex: 1, overflow: 'auto', scrollbarGutter: 'stable' } }}
    >
      <Spin spinning={loading}>
        {samples.length === 0 && !loading ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无风险候选" />
        ) : (
          <div style={triageBoardStyle}>
            {visibleBuckets.map((bucket) => (
              <section key={bucket.key} style={triageColumnStyle(bucket.color)}>
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Typography.Text strong style={{ color: palette.text }}>{bucket.title}</Typography.Text>
                    <Tag color={bucket.samples.length > 0 ? 'blue' : 'default'}>{bucket.samples.length}</Tag>
                  </Space>
                  <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
                    {bucket.description}
                  </Typography.Text>
                </Space>
                <Space direction="vertical" size={8} style={{ width: '100%', marginTop: 10 }}>
                  {bucket.samples.length === 0 ? (
                    <div style={emptyLaneStyle}>暂无</div>
                  ) : (
                    bucket.samples.map((sample) => (
                      <CandidateCard
                        key={sample.sample_id}
                        sample={sample}
                        active={sample.sample_id === selectedSampleId}
                        onSelect={() => onSelect(sample)}
                      />
                    ))
                  )}
                </Space>
              </section>
            ))}
          </div>
        )}
      </Spin>
    </Card>
  );
}

function CandidateCard({
  sample,
  active,
  onSelect,
}: {
  sample: DataFlywheelSample;
  active: boolean;
  onSelect: () => void;
}) {
  const prelabel = latestAiPrelabel(sample);
  return (
    <button
      type="button"
      data-testid={`sample-row-${sample.sample_id}`}
      onClick={onSelect}
      style={candidateCardStyle(active)}
    >
      <Space direction="vertical" size={8} style={{ width: '100%', textAlign: 'left' }}>
        <Space wrap size={6}>
          <Tag color={sample.risk_severity === 'P0' ? 'red' : 'purple'}>
            {sample.risk_severity ?? 'risk'} {sample.risk_score?.toFixed(2) ?? '-'}
          </Tag>
          <Tag color={sample.annotation_status === 'labeled' ? 'success' : 'warning'}>
            {sample.annotation_status}
          </Tag>
          {prelabel && hasPendingAiPrelabel(sample) && <Tag color="blue">AI {prelabel.confidence.toFixed(2)}</Tag>}
        </Space>
        <Typography.Text ellipsis style={{ color: palette.text, maxWidth: '100%' }}>
          #{sample.turn_id} {sample.user_input_preview || '无输入摘要'}
        </Typography.Text>
        <Typography.Text ellipsis style={{ color: palette.textMuted, fontSize: 12, maxWidth: '100%' }}>
          {sample.session_id || 'unknown-session'} / {sample.request_id || '-'}
        </Typography.Text>
        <Typography.Text ellipsis style={{ color: palette.warning, fontSize: 12, maxWidth: '100%' }}>
          {candidateReason(sample)}
        </Typography.Text>
      </Space>
    </button>
  );
}

function TurnReviewWorkbench({
  sample,
  detail,
  loading,
  traceDiagnosticsByRequestId,
  loadingTraceDiagnostics,
  onSelectTurn,
  onSelectSession,
}: {
  sample: DataFlywheelSample;
  detail: DataFlywheelDetail | null;
  loading: boolean;
  traceDiagnosticsByRequestId: Record<string, TraceDiagnostics>;
  loadingTraceDiagnostics: Record<string, boolean>;
  onSelectTurn: (sample: DataFlywheelSample) => void;
  onSelectSession: () => void;
}) {
  return (
    <div style={turnWorkbenchStyle}>
      <Card
        title="当前审核对象"
        style={turnSummaryCardStyle}
        styles={{ body: { padding: 12 } }}
      >
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Space wrap>
            <Tag color={sample.risk_severity === 'P0' ? 'red' : 'purple'}>
              {sample.risk_severity ?? 'risk'} {sample.risk_score?.toFixed(2) ?? '-'}
            </Tag>
            <Tag color={sample.annotation_status === 'labeled' ? 'success' : 'warning'}>
              {sample.annotation_status}
            </Tag>
            <Tag color={sample.event_log_status === 'missing' ? 'orange' : 'default'}>
              {sample.event_log_status ?? 'event'}
            </Tag>
          </Space>
          <div style={turnAuditGridStyle}>
            <AuditFact label="Session" value={sample.session_id || '-'} />
            <AuditFact label="Request" value={sample.request_id || '-'} />
            <AuditFact label="工具链路" value={`${sample.selected_tools.length}/${sample.actual_tools.length}`} />
            <AuditFact label="成本" value={`${sample.token_total ?? '-'} tokens`} />
          </div>
          <Typography.Paragraph style={{ color: palette.text, margin: 0 }}>
            {sample.user_input_preview || '无用户输入摘要'}
          </Typography.Paragraph>
          <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
            审核顺序：先看用户意图，再核对助手回复和工具调用，最后保存 turn 级标签。
          </Typography.Text>
        </Space>
      </Card>
      <SessionConversationView
        review={singleTurnReview(sample, detail)}
        loading={loading}
        selectedSampleId={sample.sample_id}
        traceDiagnosticsByRequestId={traceDiagnosticsByRequestId}
        loadingTraceDiagnostics={loadingTraceDiagnostics}
        onSelectTurn={onSelectTurn}
        onSelectSession={onSelectSession}
      />
    </div>
  );
}

function AuditFact({ label, value }: { label: string; value: string }) {
  return (
    <div style={auditFactStyle}>
      <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>{label}</Typography.Text>
      <Typography.Text ellipsis style={{ color: palette.text }}>{value}</Typography.Text>
    </div>
  );
}

function tabForArchiveKey(key: string): AdvancedSearchTab {
  if (key === ALL_ARCHIVE_KEY) return 'queue';
  if (key === ISSUE_ARCHIVE_KEY || key === AI_PRELABEL_ARCHIVE_KEY) return 'candidates';
  return 'sessions';
}

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isProblemCandidateSample(sample: DataFlywheelSample) {
  const risk = sample.risk_score ?? 0;
  return (
    risk >= 0.3 ||
    sample.risk_severity === 'P0' ||
    sample.risk_severity === 'P1' ||
    sample.issue_candidates.length > 0 ||
    hasPendingAiPrelabel(sample)
  );
}

function candidateReason(sample: DataFlywheelSample) {
  const prelabel = latestAiPrelabel(sample);
  if (hasPendingAiPrelabel(sample) && prelabel?.reason) return `AI 预判：${prelabel.reason}`;
  if (sample.issue_candidates[0]) return `规则候选：${sample.issue_candidates[0].reason}`;
  if (sample.judge_issue_type) return `Judge：${sample.judge_issue_type}`;
  if (sample.event_log_status === 'missing') return '事件文件缺失，可同步重建';
  return '风险分较高，建议抽检';
}

function singleTurnReview(
  sample: DataFlywheelSample,
  detail: DataFlywheelDetail | null
): DataFlywheelSessionReview {
  return {
    session_id: sample.session_id ?? 'unknown-session',
    turns: [
      {
        sample,
        messages: detail?.messages ?? [
          { role: 'user', content: sample.user_input_preview || '' },
          { role: 'assistant', content: sample.assistant_reply_preview || '' },
        ],
        router_decision: detail?.router_decision ?? null,
        tool_events: detail?.tool_events ?? [],
        pending_lifecycle: detail?.pending_lifecycle ?? [],
        source: detail?.source ?? {
          event_file: null,
          event_seq_start: null,
          event_seq_end: null,
          event_log_status: sample.event_log_status,
          chat_record_source: sample.chat_record_source,
        },
      },
    ],
  };
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

function confirmedProblemSampleIds(samples: DataFlywheelSample[], sessionKeys: string[]) {
  const selectedSessions = new Set(sessionKeys);
  return samples
    .filter((sample) => hasTurnConfirmedIssue(sample) && selectedSessions.has(sessionArchiveKey(sample)))
    .map((sample) => sample.sample_id);
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
