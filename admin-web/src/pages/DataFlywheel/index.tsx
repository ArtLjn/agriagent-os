import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Checkbox, Col, Input, Row, Select, Space, Typography, message } from 'antd';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';

import {
  addSampleLabel,
  createCaseDraft,
  exportSampleJsonl,
  getSampleDetail,
  getSessionReview,
  listDataFlywheelSamples,
  markBadCase,
  type CaseDraft,
  type DataFlywheelDetail,
  type DataFlywheelLabel,
  type DataFlywheelSample,
  type DataFlywheelSessionReview,
} from '../../api/dataFlywheel';
import { cardStyle, palette } from '../../styles/theme';
import AnnotationPanel from './components/AnnotationPanel';
import CaseDraftPreview from './components/CaseDraftPreview';
import SampleDetailPanel from './components/SampleDetailPanel';
import SampleQueueTable from './components/SampleQueueTable';
import SessionConversationView from './components/SessionConversationView';
import SessionArchivePanel, { type SessionArchiveItem } from './components/SessionArchivePanel';

const DEFAULT_LABEL: DataFlywheelLabel = 'good_reply';
const ALL_ARCHIVE_KEY = '__all__';
const ISSUE_ARCHIVE_KEY = '__issues__';

interface SampleQuery {
  searchText: string;
  qualityLabel?: DataFlywheelLabel;
  unannotatedOnly: boolean;
}

const labelOptions: Array<{ label: string; value: DataFlywheelLabel }> = [
  { label: '好回复', value: 'good_reply' },
  { label: '坏回复', value: 'bad_reply' },
  { label: '工具选错', value: 'wrong_tool_selection' },
  { label: 'pending 漏拦截', value: 'pending_missed' },
  { label: '幻觉执行', value: 'hallucinated_execution' },
  { label: '答非所问', value: 'off_topic' },
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
  const [searchText, setSearchText] = useState('');
  const [qualityLabel, setQualityLabel] = useState<DataFlywheelLabel | undefined>();
  const [unannotatedOnly, setUnannotatedOnly] = useState(false);
  const [query, setQuery] = useState<SampleQuery>({
    searchText: '',
    qualityLabel: undefined,
    unannotatedOnly: false,
  });
  const [selectedSample, setSelectedSample] = useState<DataFlywheelSample | null>(null);
  const [detail, setDetail] = useState<DataFlywheelDetail | null>(null);
  const [currentLabel, setCurrentLabel] = useState<DataFlywheelLabel>(DEFAULT_LABEL);
  const [comment, setComment] = useState('');
  const [draft, setDraft] = useState<CaseDraft | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [activeArchiveKey, setActiveArchiveKey] = useState(ALL_ARCHIVE_KEY);
  const [sessionReview, setSessionReview] = useState<DataFlywheelSessionReview | null>(null);
  const [loadingSessionReview, setLoadingSessionReview] = useState(false);
  const listRequestSeq = useRef(0);
  const detailRequestSeq = useRef(0);
  const sessionReviewRequestSeq = useRef(0);

  const archiveGroups = useMemo(() => buildArchiveGroups(samples), [samples]);
  const issueCount = useMemo(
    () => samples.filter((sample) => sample.issue_candidates.length > 0).length,
    [samples]
  );
  const visibleSamples = useMemo(() => {
    if (activeArchiveKey === ALL_ARCHIVE_KEY) return samples;
    if (activeArchiveKey === ISSUE_ARCHIVE_KEY) {
      return samples.filter((sample) => sample.issue_candidates.length > 0);
    }
    return samples.filter((sample) => sessionArchiveKey(sample) === activeArchiveKey);
  }, [activeArchiveKey, samples]);
  const isSessionArchiveActive =
    activeArchiveKey !== ALL_ARCHIVE_KEY && activeArchiveKey !== ISSUE_ARCHIVE_KEY;

  useEffect(() => {
    if (activeArchiveKey === ALL_ARCHIVE_KEY || activeArchiveKey === ISSUE_ARCHIVE_KEY) return;
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
    setLoadingDetail(true);
    try {
      const result = await getSampleDetail(sample.sample_id);
      if (requestSeq !== detailRequestSeq.current) return;
      setDetail(result);
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

  const labelBody = (label: DataFlywheelLabel) => {
    if (!selectedSample) return null;
    return {
      label,
      comment,
      sample_type: selectedSample.sample_type,
      session_id: selectedSample.session_id ?? undefined,
      turn_id: selectedSample.turn_id,
      request_id: selectedSample.request_id ?? undefined,
    };
  };

  const handleSave = async () => {
    if (!selectedSample) return;
    const body = labelBody(currentLabel);
    if (!body) return;
    setSaving(true);
    try {
      await addSampleLabel(selectedSample.sample_id, body);
      message.success('标注已保存');
      await loadDetail(selectedSample);
      await fetchSamples(query);
      await refreshSessionReviewIfActive();
    } catch {
      message.error('保存标注失败');
    } finally {
      setSaving(false);
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

  const clearSelection = () => {
    detailRequestSeq.current += 1;
    setSelectedSample(null);
    setDetail(null);
    setCurrentLabel(DEFAULT_LABEL);
    setComment('');
    setLoadingDetail(false);
  };

  const refreshSessionReviewIfActive = async () => {
    if (isSessionArchiveActive) {
      await loadSessionReview(activeArchiveKey);
    }
  };

  const loadSessionReview = useCallback(async (sessionId: string) => {
    const requestSeq = sessionReviewRequestSeq.current + 1;
    sessionReviewRequestSeq.current = requestSeq;
    setLoadingSessionReview(true);
    try {
      const result = await getSessionReview(sessionId);
      if (requestSeq !== sessionReviewRequestSeq.current) return;
      setSessionReview(result);
    } catch {
      if (requestSeq === sessionReviewRequestSeq.current) {
        message.error('加载完整会话记录失败');
      }
    } finally {
      if (requestSeq === sessionReviewRequestSeq.current) {
        setLoadingSessionReview(false);
      }
    }
  }, []);

  const handleSelectArchive = (key: string) => {
    setActiveArchiveKey(key);
    clearSelection();
    if (key === ALL_ARCHIVE_KEY || key === ISSUE_ARCHIVE_KEY) {
      sessionReviewRequestSeq.current += 1;
      setSessionReview(null);
      setLoadingSessionReview(false);
      return;
    }
    loadSessionReview(key);
  };

  return (
    <div style={{ color: palette.text }}>
      <Space direction="vertical" size={4} style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ color: palette.text, margin: 0 }}>
          Agent 数据飞轮
        </Typography.Title>
        <Typography.Text style={{ color: palette.textMuted }}>
          真实会话与调试事件样本标注工作台，用于沉淀 Agent 回复调优与回归样本。
        </Typography.Text>
      </Space>

      <Card size="small" style={{ ...cardStyle, marginBottom: 14 }} styles={{ body: { padding: 12 } }}>
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
          <Button type="primary" icon={<SearchOutlined />} loading={loadingList} onClick={submitQuery}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} loading={loadingList} onClick={refreshSamples}>
            刷新
          </Button>
          <Typography.Text style={{ color: palette.textMuted }}>共 {total} 条</Typography.Text>
        </Space>
      </Card>

      <Row gutter={[14, 14]} align="top">
        <Col xs={24} xl={5}>
          <SessionArchivePanel
            groups={archiveGroups}
            total={samples.length}
            issueCount={issueCount}
            activeKey={activeArchiveKey}
            allKey={ALL_ARCHIVE_KEY}
            issueKey={ISSUE_ARCHIVE_KEY}
            onSelect={handleSelectArchive}
          />
        </Col>

        <Col xs={24} xl={8}>
          {isSessionArchiveActive ? (
            <SessionConversationView
              review={sessionReview}
              loading={loadingSessionReview}
              selectedSampleId={selectedSample?.sample_id}
              onSelectTurn={loadDetail}
            />
          ) : (
            <Card
              title="会话 turn"
              extra={
                <Typography.Text style={{ color: palette.textMuted }}>
                  会话 turn：{visibleSamples.length} 条
                </Typography.Text>
              }
              style={cardStyle}
              styles={{ body: { padding: 0 } }}
            >
              <SampleQueueTable
                samples={visibleSamples}
                loading={loadingList}
                selectedSampleId={selectedSample?.sample_id}
                onSelect={loadDetail}
              />
            </Card>
          )}
        </Col>

        <Col xs={24} xl={11}>
          <SampleDetailPanel detail={detail} loading={loadingDetail} />
          <AnnotationPanel
            selectedSample={selectedSample}
            label={currentLabel}
            comment={comment}
            saving={saving}
            acting={acting}
            onLabelChange={setCurrentLabel}
            onCommentChange={setComment}
            onSave={handleSave}
            onCopyDebug={handleCopyDebug}
            onExportJsonl={handleExportJsonl}
            onMarkBadCase={handleMarkBadCase}
            onCreateRegressionCase={handleCreateRegressionCase}
          />
        </Col>
      </Row>

      <CaseDraftPreview draft={draft} open={draftOpen} onClose={() => setDraftOpen(false)} />
    </div>
  );
}

function sessionArchiveKey(sample: DataFlywheelSample) {
  return sample.session_id ?? 'unknown-session';
}

function buildArchiveGroups(samples: DataFlywheelSample[]): SessionArchiveItem[] {
  const groups = new Map<string, SessionArchiveItem>();

  samples.forEach((sample) => {
    const key = sessionArchiveKey(sample);
    const current = groups.get(key);
    const isBadCase =
      sample.quality_labels.includes('bad_reply') ||
      sample.quality_labels.includes('wrong_tool_selection') ||
      sample.quality_labels.includes('pending_missed') ||
      sample.quality_labels.includes('hallucinated_execution');

    if (!current) {
      groups.set(key, {
        key,
        sessionId: sample.session_id,
        total: 1,
        unannotated: sample.annotation_status === 'unlabeled' ? 1 : 0,
        badCases: isBadCase ? 1 : 0,
        latestTurnId: sample.turn_id,
        latestInputPreview: sample.user_input_preview,
      });
      return;
    }

    current.total += 1;
    current.unannotated += sample.annotation_status === 'unlabeled' ? 1 : 0;
    current.badCases += isBadCase ? 1 : 0;
    if (sample.turn_id >= current.latestTurnId) {
      current.latestTurnId = sample.turn_id;
      current.latestInputPreview = sample.user_input_preview;
    }
  });

  return Array.from(groups.values()).sort((left, right) => right.latestTurnId - left.latestTurnId);
}
