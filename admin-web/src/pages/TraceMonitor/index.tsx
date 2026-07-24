import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import type { CSSProperties } from 'react';
import {
  Input,
  Button,
  Space,
  message,
  Modal,
  Drawer,
  DatePicker,
  Typography,
  Tag,
  Pagination,
  Tooltip,
} from 'antd';
import { SearchOutlined, ClearOutlined, CopyOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import {
  listTraceRequests,
  getTimeline,
  deleteTracesBefore,
  type TraceRequestSummary,
  type TraceTimeline,
  type TraceNodeDetail,
  type TraceRootError,
  type TraceMetrics,
} from '../../api/admin';
import { useLocation } from 'react-router-dom';
import GanttTimeline from '../../components/GanttTimeline';
import type { GanttNode } from '../../components/GanttTimeline/types';
import { getNodeLabel } from '../../constants/trace';
import SkillOutputFormatter from '../../components/SkillOutputFormatter';
import {
  formatTracePayload,
  hasTracePayload,
  normalizeTracePayload,
  sanitizeTracePayload,
} from '../../utils/tracePayload';

const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';
const PANEL_BG = '#0d1117';

interface TraceItem {
  request_id: string;
  session_id: string | null;
  farm_id: number;
  node_count: number;
  total_duration_ms: number;
  created_at: string | null;
  summary: TraceRequestSummary;
  timeline: TraceTimeline | null;
  timelineLoading: boolean;
}

interface TraceSessionGroup {
  key: string;
  session_id: string | null;
  request_count: number;
  node_count: number;
  total_duration_ms: number;
  created_at: string | null;
  items: TraceItem[];
}

const toTraceItems = (records: TraceRequestSummary[]): TraceItem[] =>
  records.map((record) => ({
    request_id: record.request_id,
    session_id: record.session_id,
    farm_id: record.farm_id,
    node_count: record.node_count,
    total_duration_ms: record.total_duration_ms,
    created_at: record.created_at,
    summary: record,
    timeline: null,
    timelineLoading: true,
  }));

const aggregateSessionGroups = (items: TraceItem[]): TraceSessionGroup[] => {
  const groups = new Map<string, TraceItem[]>();
  items.forEach((item) => {
    const key = item.session_id || `request:${item.request_id}`;
    const arr = groups.get(key) || [];
    arr.push(item);
    groups.set(key, arr);
  });

  return Array.from(groups.entries()).map(([key, groupItems]) => ({
    key,
    session_id: groupItems[0].session_id,
    request_count: groupItems.length,
    node_count: groupItems.reduce((sum, item) => sum + item.node_count, 0),
    total_duration_ms: groupItems.reduce(
      (sum, item) => sum + item.total_duration_ms,
      0
    ),
    created_at: groupItems[0].created_at,
    items: groupItems,
  }));
};

function formatTraceTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime()) || date.getTime() <= 0) return '-';
  return date.toLocaleString('zh-CN');
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asRecordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.map(asRecord).filter((item): item is Record<string, unknown> => Boolean(item))
    : [];
}

function payloadRecord(value: unknown): Record<string, unknown> | null {
  return asRecord(sanitizeTracePayload(normalizeTracePayload(value)));
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function displayList(value: unknown): string {
  if (!Array.isArray(value)) return displayValue(value);
  return value.map(displayValue).join(', ');
}

function statusTagColor(status: string | null | undefined): string {
  if (status === 'success') return 'success';
  if (status === 'blocked') return 'warning';
  if (status === 'failed' || status === 'error') return 'error';
  if (status === 'timeout') return 'orange';
  return 'default';
}

function metricNumber(value: unknown): string {
  return typeof value === 'number' ? value.toLocaleString() : displayValue(value);
}

function summaryFromTimeline(
  item: TraceItem,
  timeline: TraceTimeline | null,
): TraceRequestSummary {
  if (timeline?.summary) return timeline.summary;
  if (!timeline) return item.summary;
  const nodes = timeline.rounds.flatMap((round) => round.nodes);
  const rootNode = nodes.find((node) => node.status && node.status !== 'success');
  const totalDuration = nodes.reduce((sum, node) => sum + (node.duration_ms || 0), 0);
  return {
    ...item.summary,
    node_count: nodes.length || item.node_count,
    total_duration_ms: totalDuration || item.total_duration_ms,
    status: rootNode ? rootNode.status : item.summary.status ?? 'success',
    status_reason: rootNode?.error_code ?? item.summary.status_reason ?? null,
    error_count: nodes.filter((node) => node.status && node.status !== 'success').length,
    root_error: rootNode
      ? {
          node_id: rootNode.id,
          node_type: rootNode.node_type,
          node_name: rootNode.node_name,
          code: rootNode.error_code,
          message: rootNode.error_message,
          recover: rootNode.recover,
        }
      : item.summary.root_error ?? null,
  };
}

function TraceRequestOverview({ item }: { item: TraceItem }) {
  const summary = summaryFromTimeline(item, item.timeline);
  const rootError = summary.root_error;
  const metrics = summary.metrics ?? {};
  return (
    <Space direction="vertical" style={{ width: '100%', marginBottom: 14 }} size="middle">
      <section style={summaryPanelStyle}>
        <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
          <span>Trace 摘要</span>
          <Tag color={statusTagColor(summary.status)}>{summary.status ?? 'success'}</Tag>
        </div>
        <div style={metricGridStyle}>
          <Metric label="status_reason" value={summary.status_reason} />
          <Metric label="node_count" value={summary.node_count} />
          <Metric label="error_count" value={summary.error_count ?? 0} />
          <Metric label="duration_ms" value={metricNumber(summary.total_duration_ms)} />
          <Metric label="started_at" value={formatTraceTime(summary.started_at)} />
          <Metric label="ended_at" value={formatTraceTime(summary.ended_at)} />
        </div>
      </section>
      {rootError && <TraceRootErrorPanel rootError={rootError} />}
      <TraceMetricsPanel metrics={metrics} />
    </Space>
  );
}

function TraceRootErrorPanel({ rootError }: { rootError: TraceRootError }) {
  return (
    <section style={{ ...summaryPanelStyle, borderColor: '#7c2d12', background: '#1f130c' }}>
      <div style={{ ...sectionTitleStyle, color: '#ffb86c' }}>根因</div>
      <div style={metricGridStyle}>
        <Metric label="code" value={rootError.code} />
        <Metric label="node" value={rootError.node_name} />
        <Metric label="type" value={rootError.node_type} />
        <Metric label="node_id" value={rootError.node_id} />
      </div>
      {rootError.message && (
        <div style={{ ...previewStyle, marginTop: 10, borderColor: '#7c2d12' }}>
          {rootError.message}
        </div>
      )}
      {rootError.recover && (
        <div style={{ marginTop: 10 }}>
          <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 4 }}>recover</div>
          <div style={{ color: TEXT, fontSize: 13, wordBreak: 'break-word' }}>
            {rootError.recover}
          </div>
        </div>
      )}
    </section>
  );
}

function TraceMetricsPanel({ metrics }: { metrics: TraceMetrics }) {
  const hasMetrics = Object.keys(metrics).length > 0;
  if (!hasMetrics) return null;
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>执行指标</div>
      <div style={metricGridStyle}>
        <Metric label="llm_calls" value={metrics.llm_calls} />
        <Metric label="tool_calls" value={metrics.tool_calls} />
        <Metric label="skill_calls" value={metrics.skill_calls} />
        <Metric label="total_tokens" value={metricNumber(metrics.total_tokens)} />
        <Metric label="llm_duration_ms" value={metricNumber(metrics.llm_duration_ms)} />
        <Metric label="tool_duration_ms" value={metricNumber(metrics.tool_duration_ms)} />
      </div>
    </section>
  );
}

function isContextTracePayload(value: unknown): boolean {
  const record = payloadRecord(value);
  if (!record) return false;
  return Boolean(
    record.sections ||
    record.selected_blocks ||
    record.token_budget ||
    record.token_estimate ||
    (record.blocks && record.policy_intent)
  );
}

function isContextInputPayload(value: unknown): boolean {
  const record = payloadRecord(value);
  if (!record) return false;
  return Boolean(record.block_count || record.selected_keys || record.policy_intent);
}

function ContextTraceSummary({ outputData }: { outputData: unknown }) {
  const payload = payloadRecord(outputData);
  if (!payload) {
    return (
      <RawTraceDetails label="查看原始输出" value={outputData} />
    );
  }

  const policy = asRecord(payload.policy);
  const policyIntent = policy?.intent ?? payload.policy_intent;
  const explicitSections = asRecordList(payload.sections);
  const fallbackBlocks = asRecordList(payload.blocks ?? payload.selected_blocks);
  const sections = explicitSections.length > 0
    ? explicitSections
    : fallbackBlocks.length > 0
      ? [{ name: 'Blocks', token_estimate: payload.token_estimate, blocks: fallbackBlocks }]
      : [];
  const ragSummaries = collectRagSummaries(payload, sections);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <section style={summaryPanelStyle}>
        <div style={sectionTitleStyle}>Context 摘要</div>
        <div style={metricGridStyle}>
          <Metric label="token_budget" value={payload.token_budget} />
          <Metric label="token_estimate" value={payload.token_estimate} />
          <Metric label="policy intent" value={policyIntent} />
        </div>
      </section>

      {sections.map((section, index) => (
        <ContextSection key={`${displayValue(section.name)}-${index}`} section={section} />
      ))}

      {ragSummaries.length > 0 && (
        <section style={summaryPanelStyle}>
          <div style={sectionTitleStyle}>RAG 摘要</div>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {ragSummaries.map((rag, index) => (
              <RagSummary key={`${displayValue(rag.collection)}-${index}`} rag={rag} />
            ))}
          </Space>
        </section>
      )}

      <RawTraceDetails label="查看原始输出 JSON" value={payload} />
    </Space>
  );
}

function ContextInputSummary({ inputData }: { inputData: unknown }) {
  const payload = payloadRecord(inputData);
  if (!payload) {
    return <RawTraceDetails label="查看原始输入 JSON" value={inputData} />;
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <section style={summaryPanelStyle}>
        <div style={sectionTitleStyle}>Context 输入</div>
        <div style={metricGridStyle}>
          <Metric label="block_count" value={payload.block_count} />
          <Metric label="selected_keys" value={displayList(payload.selected_keys)} />
          <Metric label="policy intent" value={payload.policy_intent} />
        </div>
      </section>
      <RawTraceDetails label="查看原始输入 JSON" value={payload} />
    </Space>
  );
}

function ContextSection({ section }: { section: Record<string, unknown> }) {
  const blocks = asRecordList(section.blocks);

  return (
    <section style={summaryPanelStyle}>
      <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
        <span>{displayValue(section.name)}</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          token_estimate: {displayValue(section.token_estimate)}
        </span>
      </div>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {blocks.length > 0 ? (
          blocks.map((block, index) => (
            <ContextBlock key={`${displayValue(block.key)}-${index}`} block={block} />
          ))
        ) : (
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>暂无 block</span>
        )}
      </Space>
    </section>
  );
}

function ContextBlock({ block }: { block: Record<string, unknown> }) {
  return (
    <div style={blockStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ color: ACCENT, fontFamily: 'monospace', fontWeight: 600 }}>
          {displayValue(block.key)}
        </span>
        <Tag>{displayValue(block.source)}</Tag>
        <Tag color={block.required ? 'processing' : 'default'}>
          required: {displayValue(block.required)}
        </Tag>
        <Tag color={block.compressed ? 'warning' : 'default'}>
          compressed: {displayValue(block.compressed)}
        </Tag>
      </div>
      <div style={blockMetaGridStyle}>
        <Metric label="purpose" value={block.purpose} />
        <Metric label="priority" value={block.priority} />
        <Metric label="token_estimate" value={block.token_estimate} />
        <Metric label="reason" value={block.reason} />
      </div>
      {hasTracePayload(block.preview) && (
        <div style={previewStyle}>{displayValue(block.preview)}</div>
      )}
    </div>
  );
}

function RagSummary({ rag }: { rag: Record<string, unknown> }) {
  const sources = asRecordList(rag.sources);

  return (
    <div style={blockStyle}>
      <div style={metricGridStyle}>
        <Metric label="collection" value={rag.collection} />
        <Metric label="mode" value={rag.mode} />
        <Metric label="actual_mode" value={rag.actual_mode} />
        <Metric label="warning" value={rag.warning} />
        <Metric label="source_count" value={rag.source_count} />
        <Metric label="top_score" value={rag.top_score} />
      </div>
      {sources.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {sources.map((source, index) => {
            const metadata = asRecord(source.metadata);
            return (
              <div key={`${displayValue(source.doc_id)}-${index}`} style={sourceStyle}>
                <span style={{ color: ACCENT, fontFamily: 'monospace' }}>
                  {displayValue(source.doc_id)}
                </span>
                <span>chunk: {displayValue(source.chunk_index)}</span>
                <span>score: {displayValue(source.score)}</span>
                {hasTracePayload(metadata?.title) && <span>{displayValue(metadata?.title)}</span>}
                {hasTracePayload(metadata?.source) && <span>{displayValue(metadata?.source)}</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 2 }}>{label}</div>
      <div style={{ color: TEXT, fontSize: 13, wordBreak: 'break-word' }}>
        {displayValue(value)}
      </div>
    </div>
  );
}

function RawTraceDetails({ label, value }: { label: string; value: unknown }) {
  return (
    <details style={{ cursor: 'pointer' }}>
      <summary style={{ color: TEXT_DIM, fontSize: 12, userSelect: 'none' }}>
        {label}
      </summary>
      <pre style={{
        backgroundColor: CARD,
        padding: 12,
        borderRadius: 6,
        border: `1px solid ${BORDER}`,
        fontSize: 12,
        margin: '8px 0 0 0',
        maxHeight: 320,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
      }}>
        {formatTracePayload(value)}
      </pre>
    </details>
  );
}

function collectRagSummaries(
  payload: Record<string, unknown>,
  sections: Record<string, unknown>[],
): Record<string, unknown>[] {
  const summaries: Record<string, unknown>[] = [];
  const seen = new Set<string>();
  const blocks = [
    ...asRecordList(payload.blocks),
    ...asRecordList(payload.selected_blocks),
    ...sections.flatMap((section) => asRecordList(section.blocks)),
  ];

  blocks.forEach((block) => {
    const rag = asRecord(block.rag);
    addRagSummary(summaries, seen, rag);
  });

  const selectorMetadata = asRecord(payload.selector_metadata);
  const knowledge = asRecord(selectorMetadata?.knowledge);
  addRagSummary(summaries, seen, knowledge);

  return summaries;
}

function addRagSummary(
  summaries: Record<string, unknown>[],
  seen: Set<string>,
  rag: Record<string, unknown> | null,
) {
  if (!rag) return;
  const key = ragSummaryKey(rag);
  if (seen.has(key)) return;
  seen.add(key);
  summaries.push(rag);
}

function ragSummaryKey(rag: Record<string, unknown>): string {
  return JSON.stringify({
    collection: rag.collection ?? '',
    mode: rag.mode ?? '',
    actual_mode: rag.actual_mode ?? '',
    source_count: rag.source_count ?? '',
    top_score: rag.top_score ?? '',
    sources: asRecordList(rag.sources).map((source) => ({
      doc_id: source.doc_id ?? '',
      chunk_index: source.chunk_index ?? '',
      score: source.score ?? '',
    })),
  });
}

const summaryPanelStyle: CSSProperties = {
  background: PANEL_BG,
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  padding: 12,
};

const sectionTitleStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  color: TEXT,
  fontSize: 14,
  fontWeight: 600,
  marginBottom: 10,
};

const metricGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
  gap: 10,
};

const blockMetaGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
  gap: 8,
};

const blockStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  background: CARD,
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 10,
};

const previewStyle: CSSProperties = {
  color: TEXT,
  background: '#111923',
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 8,
  fontSize: 12,
  lineHeight: 1.6,
  whiteSpace: 'pre-wrap',
};

const sourceStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
  color: TEXT_DIM,
  fontSize: 12,
};

export default function TraceMonitor() {
  const location = useLocation();
  const initialFilters = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return {
      request_id: params.get('request_id') ?? '',
      session_id: params.get('session_id') ?? '',
      farm_id: params.get('farm_id') ?? '',
    };
  }, [location.search]);
  const [items, setItems] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(initialFilters);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<TraceNodeDetail | null>(null);
  const [cleanupDate, setCleanupDate] = useState<Dayjs | null>(null);
  const [cleanupModalOpen, setCleanupModalOpen] = useState(false);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const sessionGroups = useMemo(() => aggregateSessionGroups(items), [items]);
  const didInitialFetch = useRef(false);

  const loadTimeline = useCallback(async (requestId: string) => {
    try {
      const res = await getTimeline(requestId);
      setItems((prev) =>
        prev.map((item) =>
          item.request_id === requestId
            ? {
                ...item,
                summary: res.summary ?? item.summary,
                timeline: res,
                timelineLoading: false,
              }
            : item
        )
      );
    } catch {
      setItems((prev) =>
        prev.map((item) =>
          item.request_id === requestId
            ? { ...item, timeline: null, timelineLoading: false }
            : item
        )
      );
    }
  }, []);

  const fetchData = useCallback(
    async (p = page, ps = pageSize) => {
      setLoading(true);
      try {
        const params: Record<string, unknown> = {
          limit: ps,
          offset: (p - 1) * ps,
        };
        if (filters.request_id.trim()) params.request_id = filters.request_id.trim();
        if (filters.session_id.trim()) params.session_id = filters.session_id.trim();
        if (filters.farm_id.trim()) params.farm_id = Number(filters.farm_id.trim());

        const res = await listTraceRequests(params);
        const aggregated = toTraceItems(res.items);
        setItems(aggregated);
        setTotal(res.total);
        setPage(p);
        setPageSize(ps);
        if (filters.request_id.trim() && aggregated.some((item) => item.request_id === filters.request_id.trim())) {
          setExpandedCards(new Set([filters.request_id.trim()]));
          loadTimeline(filters.request_id.trim());
        } else {
          setExpandedCards(new Set());
        }
      } catch {
        message.error('加载 Trace 列表失败');
      } finally {
        setLoading(false);
      }
    },
    [filters, page, pageSize, loadTimeline]
  );

  useEffect(() => {
    if (didInitialFetch.current) return;
    didInitialFetch.current = true;
    fetchData();
  }, [fetchData]);

  const handleNodeClick = (
    requestId: string,
    _roundIndex: number,
    _nodeIndex: number,
    nodeData: GanttNode
  ) => {
    const detail: TraceNodeDetail = {
      id: nodeData.id ?? 0,
      request_id: requestId,
      round_index: _roundIndex,
      node_type: nodeData.node_type,
      node_name: nodeData.node_name,
      input_data: nodeData.input_data ?? null,
      output_data: nodeData.output_data ?? null,
      duration_ms: nodeData.duration_ms,
      token_usage: null,
      status: nodeData.status,
      error_message: nodeData.error_message ?? null,
      error_code: nodeData.error_code ?? null,
      recover: nodeData.recover ?? null,
      start_time: nodeData.start_time,
      end_time: nodeData.end_time ?? null,
    };
    setNodeDetail(detail);
    setDrawerOpen(true);
  };

  function computeTimingReport(timeline: TraceTimeline): string {
    const typeStats = new Map<string, { duration: number; count: number }>();
    let totalDuration = 0;

    for (const round of timeline.rounds) {
      for (const node of round.nodes) {
        if (node.duration_ms && node.duration_ms > 0) {
          const existing = typeStats.get(node.node_type) || { duration: 0, count: 0 };
          existing.duration += node.duration_ms;
          existing.count += 1;
          typeStats.set(node.node_type, existing);
          totalDuration += node.duration_ms;
        }
      }
    }

    const NODE_TYPE_LABELS: Record<string, string> = {
      routing: '路由决策',
      prompt_render: 'Prompt 渲染',
      llm_call: 'LLM 调用',
      skill_call: 'Skill 执行',
      error: '错误',
    };

    let md = '### Trace 耗时分析\n\n';
    md += '| 节点类型 | 累计耗时(ms) | 占比 | 节点数 |\n';
    md += '|----------|-------------|------|--------|\n';

    for (const [type, stats] of typeStats) {
      const label = NODE_TYPE_LABELS[type] || type;
      const pct = totalDuration > 0 ? ((stats.duration / totalDuration) * 100).toFixed(1) : '0.0';
      md += `| ${label} | ${stats.duration} | ${pct}% | ${stats.count} |\n`;
    }

    md += `| **总计** | **${totalDuration}** | **100%** | **${Array.from(typeStats.values()).reduce((s, v) => s + v.count, 0)}** |\n`;

    return md;
  }

  async function copyTimingReport(timeline: TraceTimeline) {
    try {
      const report = computeTimingReport(timeline);
      await navigator.clipboard.writeText(report);
      message.success('耗时分析已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  }

  const handleCleanup = async () => {
    if (!cleanupDate) {
      message.warning('请选择清理日期');
      return;
    }
    setCleanupModalOpen(true);
  };

  const confirmCleanup = async () => {
    if (!cleanupDate) return;
    try {
      const before = cleanupDate.format('YYYY-MM-DD');
      const res = await deleteTracesBefore(before);
      message.success(`已清理 ${res.deleted} 条历史记录`);
      setCleanupModalOpen(false);
      setCleanupDate(null);
      fetchData(1);
    } catch {
      message.error('清理失败');
    }
  };

  const toggleCard = (requestId: string) => {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(requestId)) {
        next.delete(requestId);
      } else {
        next.add(requestId);
        const item = items.find((i) => i.request_id === requestId);
        if (item && !item.timeline) {
          loadTimeline(requestId);
        }
      }
      return next;
    });
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        链路追踪
      </Typography.Title>

      {/* 筛选区 */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Request ID"
          value={filters.request_id}
          onChange={(e) => setFilters((f) => ({ ...f, request_id: e.target.value }))}
          style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Input
          placeholder="Session ID"
          value={filters.session_id}
          onChange={(e) => setFilters((f) => ({ ...f, session_id: e.target.value }))}
          style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Input
          placeholder="Farm ID"
          value={filters.farm_id}
          onChange={(e) => setFilters((f) => ({ ...f, farm_id: e.target.value }))}
          style={{ width: 120, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={() => fetchData(1)} loading={loading}>
          查询
        </Button>
      </Space>

      {/* Trace 列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
        {sessionGroups.map((group) => (
          <div key={group.key} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                padding: '8px 12px',
                fontSize: 13,
                color: TEXT_DIM,
                borderLeft: `3px solid ${ACCENT}`,
                background: '#0d1117',
              }}
            >
              <span style={{ color: TEXT, fontWeight: 600 }}>
                Session 组次
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>Session: </span>
                <span style={{ fontFamily: 'monospace', color: ACCENT }}>
                  {group.session_id ? `${group.session_id.slice(0, 24)}...` : '未绑定'}
                </span>
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>请求: </span>
                <span style={{ color: TEXT }}>{group.request_count}</span>
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>节点: </span>
                <span style={{ color: TEXT }}>{group.node_count}</span>
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>累计耗时: </span>
                <span style={{ color: TEXT }}>{group.total_duration_ms}ms</span>
              </span>
              <span style={{ marginLeft: 'auto' }}>
                {formatTraceTime(group.created_at)}
              </span>
            </div>

            {group.items.map((item) => (
              <div
                key={item.request_id}
                style={{
                  background: CARD,
                  border: `1px solid ${BORDER}`,
                  borderRadius: 8,
                  overflow: 'hidden',
                }}
              >
                {/* Trace 头部信息 - 可点击折叠/展开 */}
                <div
                  onClick={() => toggleCard(item.request_id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px 16px',
                    borderBottom: expandedCards.has(item.request_id)
                      ? `1px solid ${BORDER}`
                      : 'none',
                    gap: 24,
                    fontSize: 13,
                    cursor: 'pointer',
                    transition: 'background 0.2s',
                  }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ color: TEXT_DIM }}>Request ID:</span>
                    <span style={{ fontFamily: 'monospace', color: ACCENT }}>
                      {item.request_id}
                    </span>
                    <Tooltip title="复制 Request ID">
                      <CopyOutlined
                        onClick={(e) => {
                          e.stopPropagation();
                          void navigator.clipboard.writeText(item.request_id).then(() => {
                            message.success('已复制 Request ID');
                          }).catch(() => {
                            message.error('复制失败');
                          });
                        }}
                        style={{ color: TEXT_DIM, fontSize: 12, cursor: 'pointer' }}
                      />
                    </Tooltip>
                  </span>
                  {item.session_id && (
                    <span>
                      <span style={{ color: TEXT_DIM }}>Session: </span>
                      <span style={{ fontFamily: 'monospace', color: TEXT_DIM }}>
                        {item.session_id.slice(0, 16)}...
                      </span>
                    </span>
                  )}
                  <span>
                    <span style={{ color: TEXT_DIM }}>Farm: </span>
                    <span style={{ color: TEXT }}>{item.farm_id}</span>
                  </span>
                  <span>
                    <span style={{ color: TEXT_DIM }}>节点: </span>
                    <span style={{ color: TEXT }}>{item.node_count}</span>
                  </span>
                  <span>
                    <span style={{ color: TEXT_DIM }}>耗时: </span>
                    <span style={{ color: TEXT }}>{item.total_duration_ms}ms</span>
                  </span>
                  <Tag color={statusTagColor(item.summary.status)} style={{ marginInlineEnd: 0 }}>
                    {item.summary.status ?? 'success'}
                  </Tag>
                  {item.summary.status_reason && (
                    <span style={{ color: TEXT_DIM, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.summary.status_reason}
                    </span>
                  )}
                  <span style={{ marginLeft: 'auto', color: TEXT_DIM, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                    {expandedCards.has(item.request_id) && item.timeline && (
                      <Button
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={(e) => { e.stopPropagation(); copyTimingReport(item.timeline!); }}
                        style={{ background: 'transparent', borderColor: BORDER, color: TEXT_DIM, fontSize: 12 }}
                      >
                        复制耗时
                      </Button>
                    )}
                    <span style={{ minWidth: 150, textAlign: 'right' }}>
                      {formatTraceTime(item.created_at)}
                    </span>
                    <span style={{ color: ACCENT }}>
                      {expandedCards.has(item.request_id) ? '收起 ▲' : '展开 ▼'}
                    </span>
                  </span>
                </div>

                {/* Gantt 图 - 展开时显示 */}
                {expandedCards.has(item.request_id) && (
                <div style={{ padding: 16 }}>
                  <TraceRequestOverview item={item} />
                  {item.timelineLoading ? (
                    <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 24 }}>
                      加载 Timeline...
                    </div>
                  ) : item.timeline ? (
                    <GanttTimeline
                      rounds={item.timeline.rounds.map((r) => ({
                        round_index: r.round_index,
                        nodes: r.nodes.map((n) => ({
                          node_type: n.node_type,
                          node_name: n.node_name,
                          id: n.id,
                          duration_ms: n.duration_ms,
                          status: n.status,
                          start_time: n.start_time,
                          end_time: n.end_time,
                          input_data: n.input_data,
                          output_data: n.output_data,
                          error_message: n.error_message,
                          error_code: n.error_code,
                          recover: n.recover,
                        })),
                      }))}
                      onNodeClick={(roundIdx, nodeIdx, node) =>
                        handleNodeClick(item.request_id, roundIdx, nodeIdx, node)
                      }
                    />
                  ) : (
                    <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 24 }}>
                      <div style={{ marginBottom: 8 }}>暂无 Timeline 数据（可能该 Trace 已过期或未记录链路）</div>
                      <Button size="small" onClick={() => loadTimeline(item.request_id)}>
                        重试加载
                      </Button>
                    </div>
                  )}
                </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* 分页 */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger
          pageSizeOptions={[10, 20, 50]}
          onChange={(p, ps) => fetchData(p, ps)}
          style={{ color: TEXT }}
        />
      </div>

      {/* 清理操作 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: 16,
          background: CARD,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
        }}
      >
        <span style={{ color: TEXT_DIM }}>清理历史数据：</span>
        <DatePicker
          placeholder="选择日期"
          value={cleanupDate}
          onChange={setCleanupDate}
          style={{ width: 200, background: CARD, borderColor: BORDER }}
        />
        <Button danger icon={<ClearOutlined />} onClick={handleCleanup}>
          清理历史
        </Button>
      </div>

      {/* 确认弹窗 */}
      <Modal
        title="确认清理"
        open={cleanupModalOpen}
        onOk={confirmCleanup}
        onCancel={() => setCleanupModalOpen(false)}
        okText="确认清理"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p style={{ color: TEXT }}>
          确定要清理 <strong>{cleanupDate?.format('YYYY-MM-DD')}</strong> 之前的所有 Trace 记录吗？
        </p>
        <p style={{ color: TEXT_DIM }}>此操作不可恢复。</p>
      </Modal>

      {/* 节点详情 Drawer */}
      <Drawer
        title="节点详情"
        placement="right"
        width={640}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
      >
        {nodeDetail ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Tag color={nodeDetail.status === 'success' ? 'success' : 'error'}>
                {nodeDetail.status}
              </Tag>
              <Tag color="processing">{getNodeLabel(nodeDetail.node_type)}</Tag>
              <span style={{ color: TEXT_DIM }}>
                {nodeDetail.duration_ms?.toLocaleString() ?? '-'} ms
              </span>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>节点名称</div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>{nodeDetail.node_name}</div>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>Request ID</div>
              <div style={{ fontFamily: 'monospace', fontSize: 12 }}>{nodeDetail.request_id}</div>
            </div>
            {nodeDetail.start_time && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>开始时间</div>
                <div>{new Date(nodeDetail.start_time).toLocaleString('zh-CN')}</div>
              </div>
            )}
            {nodeDetail.error_message && (
              <div>
                <div style={{ color: '#ff4d4f', marginBottom: 4, fontSize: 12 }}>错误信息</div>
                <pre style={{
                  backgroundColor: '#2a1215',
                  padding: 12,
                  borderRadius: 6,
                  border: '1px solid #58181c',
                  color: '#ff4d4f',
                  fontSize: 12,
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                }}>
                  {nodeDetail.error_message}
                </pre>
              </div>
            )}
            {(nodeDetail.error_code || nodeDetail.recover) && (
              <section style={summaryPanelStyle}>
                <div style={sectionTitleStyle}>错误诊断</div>
                <div style={metricGridStyle}>
                  <Metric label="error_code" value={nodeDetail.error_code} />
                  <Metric label="recover" value={nodeDetail.recover} />
                </div>
              </section>
            )}
            {hasTracePayload(nodeDetail.input_data) && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输入数据</div>
                {isContextInputPayload(nodeDetail.input_data) ? (
                  <ContextInputSummary inputData={nodeDetail.input_data} />
                ) : (
                  <pre style={{
                    backgroundColor: '#161b22',
                    padding: 12,
                    borderRadius: 6,
                    border: '1px solid #30363d',
                    fontSize: 12,
                    margin: 0,
                    maxHeight: 300,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {formatTracePayload(nodeDetail.input_data)}
                  </pre>
                )}
              </div>
            )}
            {hasTracePayload(nodeDetail.output_data) && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输出数据</div>
                {isContextTracePayload(nodeDetail.output_data) ? (
                  <ContextTraceSummary outputData={nodeDetail.output_data} />
                ) : nodeDetail.node_type === 'skill_call' ? (
                  <SkillOutputFormatter outputData={nodeDetail.output_data} />
                ) : (
                  <pre style={{
                    backgroundColor: '#161b22',
                    padding: 12,
                    borderRadius: 6,
                    border: '1px solid #30363d',
                    fontSize: 12,
                    margin: 0,
                    maxHeight: 500,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {formatTracePayload(nodeDetail.output_data)}
                  </pre>
                )}
              </div>
            )}
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
