import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Card, Checkbox, Col, Input, Row, Select, Space, Typography, message } from 'antd';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';

import {
  addSampleLabel,
  createCaseDraft,
  exportSampleJsonl,
  getSampleDetail,
  listDataFlywheelSamples,
  markBadCase,
  type CaseDraft,
  type DataFlywheelDetail,
  type DataFlywheelLabel,
  type DataFlywheelSample,
} from '../../api/dataFlywheel';
import { cardStyle, palette } from '../../styles/theme';
import AnnotationPanel from './components/AnnotationPanel';
import CaseDraftPreview from './components/CaseDraftPreview';
import SampleDetailPanel from './components/SampleDetailPanel';
import SampleQueueTable from './components/SampleQueueTable';

const DEFAULT_LABEL: DataFlywheelLabel = 'good_reply';

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
  const listRequestSeq = useRef(0);
  const detailRequestSeq = useRef(0);

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
        request_id: trimmed || undefined,
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
    setQuery({
      searchText,
      qualityLabel,
      unannotatedOnly,
    });
  };

  const refreshSamples = () => {
    fetchSamples(query);
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
        <Col xs={24} xl={14}>
          <Card title="样本队列" style={cardStyle} styles={{ body: { padding: 0 } }}>
            <SampleQueueTable
              samples={samples}
              loading={loadingList}
              selectedSampleId={selectedSample?.sample_id}
              onSelect={loadDetail}
            />
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <SampleDetailPanel detail={detail} loading={loadingDetail} />
        </Col>

        <Col xs={24} xl={4}>
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
