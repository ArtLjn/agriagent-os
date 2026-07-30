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

function displayAuditValue(value: unknown): string {
  const text = displayValue(value);
  return text === '-' ? '未记录' : text;
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

function isRouterTracePayload(value: unknown): boolean {
  const record = payloadRecord(value);
  if (!record) return false;
  const planDraft = asRecord(record.plan_draft);
  return Boolean(
    record.schema_version === 2 ||
    record.summary ||
    record.selected ||
    record.recall ||
    record.candidate_explanations ||
    record.plan ||
    record.frames ||
    record.selected_tools ||
    record.selected_operations ||
    record.context_dependencies ||
    record.rejected_tools ||
    record.policy_violations ||
    record.tool_choice ||
    planDraft?.steps ||
    planDraft?.intent_frames
  );
}

function ContextTraceSummary({
  outputData,
  showRaw = true,
}: {
  outputData: unknown;
  showRaw?: boolean;
}) {
  const payload = payloadRecord(outputData);
  if (!payload) {
    return <RawTraceDetails label="查看原始输出" value={outputData} />;
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

      {showRaw && <RawTraceDetails label="查看原始输出 JSON" value={payload} />}
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

function RouterTraceSummary({
  outputData,
  showRaw = true,
}: {
  outputData: unknown;
  showRaw?: boolean;
}) {
  const payload = payloadRecord(outputData);
  if (!payload) {
    return <RawTraceDetails label="查看原始输出 JSON" value={outputData} />;
  }

  const summary = asRecord(payload.summary);
  const selected = asRecord(payload.selected);
  const recall = asRecord(payload.recall);
  const plan = asRecord(payload.plan);
  const planDraft = asRecord(payload.plan_draft);
  const planPayload = plan ?? planDraft;
  const evidence = asRecord(payload.evidence);
  const validation = asRecord(planPayload?.validation);
  const frames = asRecordList(payload.frames ?? planDraft?.intent_frames);
  const steps = asRecordList(planPayload?.steps);
  const selectedTools = selected?.tools ?? payload.selected_tools;
  const selectedOperations = selected?.operations ?? payload.selected_operations;
  const forceBinding = selected?.force_binding ?? payload.force_binding;
  const toolChoice = selected?.tool_choice ?? payload.tool_choice;
  const selectedCandidates = asRecordList(
    payload.candidate_explanations ?? evidence?.selected_candidates,
  );
  const rejectedCandidates = [
    ...asRecordList(payload.rejected_candidates),
    ...asRecordList(evidence?.rejected_candidates),
  ];
  const violations = Array.isArray(summary?.policy_violations)
    ? summary?.policy_violations
    : Array.isArray(payload.policy_violations)
      ? payload.policy_violations
    : [];
  const fallback = summary?.fallback ?? payload.fallback;
  const fallbackReason = summary?.fallback_reason ?? payload.fallback_reason;
  const reason = summary?.selection_reason ?? payload.reason;
  const selectedRoutes = summary?.selected_routes;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <section style={summaryPanelStyle}>
        <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
          <span>路由决策</span>
          <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <Tag color="processing">tool_choice: {displayValue(toolChoice)}</Tag>
            <Tag color={fallback ? 'warning' : 'success'}>
              fallback: {displayValue(fallback)}
            </Tag>
          </span>
        </div>
        <div style={metricGridStyle}>
          <Metric label="selection_path" value={summary?.selection_path ?? recall?.path} />
          <Metric label="retrieval_engine" value={recall?.retrieval_engine} />
          <Metric label="reason" value={reason} />
          <Metric label="route_type" value={planPayload?.route_type} />
          <Metric label="source" value={planDraft?.source} />
          <Metric label="validation" value={validation?.status} />
          <Metric label="safe_route_type" value={validation?.safe_route_type} />
          <Metric label="clarification" value={payload.clarification} />
        </div>
        {hasTracePayload(fallbackReason) && (
          <div style={{ ...previewStyle, marginTop: 10 }}>
            fallback_reason: {displayValue(fallbackReason)}
          </div>
        )}
      </section>

      {recall && <RecallSummary recall={recall} />}

      <section style={summaryPanelStyle}>
        <div style={sectionTitleStyle}>命中范围</div>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <PillRow label="selected_routes" value={selectedRoutes} color="blue" />
          <PillRow label="selected_tools" value={selectedTools} color="blue" />
          <OperationMatrix operations={selectedOperations} />
          <PillRow label="context_dependencies" value={payload.context_dependencies} color="cyan" />
          <PillRow label="force_binding" value={forceBinding} color="geekblue" />
          <PillRow label="rejected_tools" value={payload.rejected_tools} color="red" />
          <PillRow label="policy_violations" value={violations} color="volcano" />
        </Space>
      </section>

      <ScoreMatrix title="全局评分" scores={payload.scores} />

      {frames.length > 0 && (
        <section style={summaryPanelStyle}>
          <div style={sectionTitleStyle}>意图帧</div>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {frames.map((frame, index) => (
              <IntentFrameCard key={`${displayValue(frame.intent)}-${index}`} frame={frame} />
            ))}
          </Space>
        </section>
      )}

      {selectedCandidates.length > 0 && (
        <CandidateList title="已选择候选" candidates={selectedCandidates} tone="selected" />
      )}

      {rejectedCandidates.length > 0 && (
        <CandidateList title="已拒绝候选" candidates={rejectedCandidates} tone="rejected" />
      )}

      {steps.length > 0 && (
        <section style={summaryPanelStyle}>
          <div style={sectionTitleStyle}>计划草案</div>
          <div style={metricGridStyle}>
            <Metric label="session_id" value={planDraft?.session_id} />
            <Metric label="farm_id" value={planDraft?.farm_id} />
            <Metric label="raw_user_input" value={planDraft?.raw_user_input} />
            <Metric label="missing_fields" value={displayList(planDraft?.missing_fields)} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
            {steps.map((step, index) => (
              <PlanStepCard key={`${displayValue(step.step_id)}-${index}`} step={step} index={index} />
            ))}
          </div>
        </section>
      )}

      {showRaw && <RawTraceDetails label="查看原始输出 JSON" value={payload} />}
    </Space>
  );
}

function RecallSummary({ recall }: { recall: Record<string, unknown> }) {
  const status = String(recall.status ?? 'unknown');
  const ragUsed = Boolean(recall.rag_service_used ?? recall.quillrag_retrieve_used);
  const embeddingLocation = displayValue(recall.embedding_location);
  const embeddingUsed =
    Boolean(recall.external_embedding_requested) ||
    (embeddingLocation !== '-' && embeddingLocation !== 'none');
  const localDocEmbeds = recall.local_doc_embedding_calls ?? recall.local_doc_embeds ?? 0;
  const headline =
    status === 'used'
      ? '已执行 BM25 + RAG 混合召回'
      : '规则或策略已命中，未执行向量召回';
  const meaning =
    recall.meaning ??
    (status === 'used'
      ? '本轮通过混合检索生成候选 Skill，再交给路由策略选择。'
      : '本轮直接使用规则分类器结果，RAG 与外部 embedding 均未调用。');

  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>召回路径</div>
      <div style={recallOverviewStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Tag color={status === 'used' ? 'success' : 'default'}>{displayValue(status)}</Tag>
            <span style={{ color: TEXT, fontSize: 16, fontWeight: 700 }}>{headline}</span>
          </div>
          <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 8, lineHeight: 1.6 }}>
            {displayValue(meaning)}
          </div>
        </div>
        <div style={recallSignalGridStyle}>
          <RecallSignal label="外部 RAG" value={ragUsed ? '已调用' : '未调用'} active={ragUsed} />
          <RecallSignal label="Embedding" value={embeddingUsed ? embeddingLocation : '未调用'} active={embeddingUsed} />
          <RecallSignal label="本地文档向量" value={`${displayValue(localDocEmbeds)} 次`} active={Number(localDocEmbeds) > 0} />
        </div>
      </div>

      <div style={recallDetailGridStyle}>
        <Metric label="path" value={recall.path} />
        <Metric label="strategy" value={recall.strategy} />
        <Metric label="skip_reason" value={recall.skip_reason} />
        <Metric label="vector_status" value={recall.vector_status} />
        <Metric label="vector_scored_count" value={recall.vector_scored_count} />
      </div>
      {hasTracePayload(recall.scoring_formula) && (
        <div style={formulaStyle}>
          <span style={{ color: TEXT_DIM }}>评分公式</span>
          <span style={{ color: ACCENT, fontFamily: 'monospace' }}>
            {displayValue(recall.scoring_formula)}
          </span>
        </div>
      )}
    </section>
  );
}

function RecallSignal({
  label,
  value,
  active,
}: {
  label: string;
  value: string;
  active: boolean;
}) {
  return (
    <div style={{
      ...recallSignalStyle,
      borderColor: active ? '#1f6feb' : BORDER,
      background: active ? 'rgba(31, 111, 235, 0.12)' : '#111923',
    }}>
      <div style={{ color: TEXT_DIM, fontSize: 11 }}>{label}</div>
      <div style={{
        color: active ? ACCENT : TEXT,
        fontSize: 13,
        fontWeight: 700,
        overflowWrap: 'anywhere',
      }}>
        {value}
      </div>
    </div>
  );
}

function IntentFrameCard({ frame }: { frame: Record<string, unknown> }) {
  const evidence = asRecord(frame.evidence);
  const matchedCandidates = asRecordList(evidence?.matched_candidates);

  return (
    <div style={blockStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ color: ACCENT, fontFamily: 'monospace', fontWeight: 600 }}>
            {displayValue(frame.intent)}
          </span>
          <Tag>{displayValue(frame.domain)}</Tag>
          <Tag color={riskTagColor(frame.risk)}>{displayValue(frame.risk)}</Tag>
          {frame.requires_confirmation ? <Tag color="warning">需要确认</Tag> : <Tag>无需确认</Tag>}
        </div>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>
          confidence {displayValue(frame.confidence)} · score {displayValue(frame.score)}
        </span>
      </div>
      <div style={metricGridStyle}>
        <Metric label="capability" value={frame.capability} />
        <Metric label="operation" value={frame.operation} />
        <Metric label="operation_hint" value={frame.operation_hint} />
        <Metric label="missing_fields" value={displayList(frame.missing_fields)} />
        <Metric label="depends_on" value={displayList(frame.depends_on)} />
      </div>
      <Space direction="vertical" style={{ width: '100%' }} size={6}>
        <PillRow label="entities" value={frame.entities} color="cyan" />
        <PillRow label="candidate_tools" value={frame.candidate_tools} color="blue" />
      </Space>
      <ScoreMatrix title="帧评分证据" scores={frameScoreGroups(evidence)} compact />
      {matchedCandidates.length > 0 && (
        <CandidateList title="匹配候选" candidates={matchedCandidates} tone="matched" nested />
      )}
    </div>
  );
}

function PlanStepCard({ step, index }: { step: Record<string, unknown>; index: number }) {
  return (
    <div style={sourceCardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ color: ACCENT, fontFamily: 'monospace', fontWeight: 600 }}>
          {index + 1}. {displayValue(step.step_id)}
        </span>
        <Tag color={riskTagColor(step.risk)}>{displayValue(step.risk)}</Tag>
      </div>
      <div style={metricGridStyle}>
        <Metric label="skill_name" value={step.skill_name} />
        <Metric label="operation" value={step.operation} />
        <Metric label="depends_on" value={displayList(step.depends_on)} />
        <Metric label="params" value={step.params} />
      </div>
    </div>
  );
}

function CandidateList({
  title,
  candidates,
  tone,
  nested = false,
}: {
  title: string;
  candidates: Record<string, unknown>[];
  tone: 'selected' | 'rejected' | 'matched';
  nested?: boolean;
}) {
  const sectionStyle = nested ? nestedPanelStyle : summaryPanelStyle;
  return (
    <section style={sectionStyle}>
      <div style={sectionTitleStyle}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {candidates.map((candidate, index) => (
          <div key={`${candidateDisplayName(candidate)}-${index}`} style={sourceCardStyle}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color: ACCENT, fontFamily: 'monospace', fontWeight: 600 }}>
                {candidateDisplayName(candidate)}
              </span>
              {candidate.selected !== undefined && (
                <Tag color={candidate.selected ? 'success' : 'default'}>
                  {candidate.selected ? 'selected' : 'candidate'}
                </Tag>
              )}
              <Tag color={candidateTagColor(tone)}>{displayValue(candidate.operation)}</Tag>
              <Tag>{displayValue(candidate.domain)}</Tag>
              <Tag color={riskTagColor(candidate.risk)}>{displayValue(candidate.risk)}</Tag>
              {candidate.enabled !== undefined && (
                <Tag color={candidate.enabled ? 'success' : 'default'}>
                  enabled: {displayValue(candidate.enabled)}
                </Tag>
              )}
            </div>
            <div style={blockMetaGridStyle}>
              <Metric label="capability" value={candidate.capability} />
              <Metric label="legacy_alias" value={candidate.legacy_alias} />
              <Metric label="reason" value={candidate.reason} />
              <Metric label="why_selected" value={candidate.why_selected} />
            </div>
            <ScoreMatrix title="候选评分" scores={candidate.scores} compact />
          </div>
        ))}
      </div>
    </section>
  );
}

function candidateDisplayName(candidate: Record<string, unknown>): string {
  return displayValue(
    candidate.route ??
    candidate.name ??
    candidate.skill ??
    candidate.capability ??
    '-',
  );
}

function OperationMatrix({ operations }: { operations: unknown }) {
  const record = asRecord(operations);
  if (!record || Object.keys(record).length === 0) {
    return <PillRow label="selected_operations" value={[]} color="blue" />;
  }

  return (
    <div>
      <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 6 }}>selected_operations</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Object.entries(record).map(([tool, operationList]) => (
          <div key={tool} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: ACCENT, fontFamily: 'monospace', fontSize: 12 }}>{tool}</span>
            {Array.isArray(operationList) && operationList.length > 0 ? (
              operationList.map((operation) => (
                <Tag key={`${tool}-${displayValue(operation)}`} color="blue">
                  {displayValue(operation)}
                </Tag>
              ))
            ) : (
              <Tag>{displayValue(operationList)}</Tag>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PillRow({
  label,
  value,
  color,
}: {
  label: string;
  value: unknown;
  color: string;
}) {
  const values = Array.isArray(value) ? value : hasTracePayload(value) ? [value] : [];
  return (
    <div>
      <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {values.length > 0 ? (
          values.map((item, index) => (
            <Tag
              key={`${label}-${displayValue(item)}-${index}`}
              color={color}
              style={tagWrapStyle}
            >
              {displayValue(item)}
            </Tag>
          ))
        ) : (
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>无</span>
        )}
      </div>
    </div>
  );
}

function ScoreMatrix({
  title,
  scores,
  compact = false,
}: {
  title: string;
  scores: unknown;
  compact?: boolean;
}) {
  const groups = scoreGroups(scores);
  if (groups.length === 0) return null;

  return (
    <section style={compact ? nestedPanelStyle : summaryPanelStyle}>
      <div style={sectionTitleStyle}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {groups.map(([group, entries]) => (
          <div key={group} style={scoreGroupStyle}>
            <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 8 }}>{group}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {entries.map(([label, score]) => (
                <ScoreBar key={`${group}-${label}`} label={label} value={score} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const percent = Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
        <span style={{ color: TEXT, fontSize: 12, fontFamily: 'monospace' }}>{label}</span>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>{displayValue(value)}</span>
      </div>
      <div style={scoreTrackStyle}>
        <div style={{ ...scoreFillStyle, width: `${percent}%`, background: scoreColor(percent) }} />
      </div>
    </div>
  );
}

function frameScoreGroups(evidence: Record<string, unknown> | null): Record<string, unknown> {
  if (!evidence) return {};
  return {
    domain: evidence.domain_scores,
    capability: evidence.capability_scores,
    operation: evidence.operation_scores,
  };
}

function scoreGroups(scores: unknown): Array<[string, Array<[string, number]>]> {
  const record = asRecord(scores);
  if (!record) return [];
  const flatEntries = scoreEntries(record);
  const nestedGroups = Object.entries(record)
    .map(([group, nested]) => [group, scoreEntries(nested)] as [string, Array<[string, number]>])
    .filter(([, entries]) => entries.length > 0);
  if (flatEntries.length > 0) {
    return [['score', flatEntries], ...nestedGroups];
  }
  return nestedGroups;
}

function scoreEntries(value: unknown): Array<[string, number]> {
  const record = asRecord(value);
  if (!record) return [];
  return Object.entries(record)
    .map(([key, score]) => [key, Number(score)] as [string, number])
    .filter(([, score]) => Number.isFinite(score));
}

function scoreColor(percent: number): string {
  if (percent >= 80) return '#2ea043';
  if (percent >= 50) return '#d29922';
  return '#f85149';
}

function candidateTagColor(tone: 'selected' | 'rejected' | 'matched'): string {
  if (tone === 'rejected') return 'red';
  if (tone === 'matched') return 'cyan';
  return 'green';
}

function riskTagColor(risk: unknown): string {
  if (risk === 'write' || risk === 'delete') return 'warning';
  if (risk === 'read') return 'success';
  return 'default';
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
      <div style={{ ...containedTextStyle, color: TEXT, fontSize: 13 }}>
        {displayValue(value)}
      </div>
    </div>
  );
}

function NodeTraceVisualization({ node }: { node: TraceNodeDetail }) {
  return (
    <Space direction="vertical" style={detailStackStyle} size="middle">
      <NodeHeader node={node} />
      {hasTracePayload(node.input_data) && (
        <TracePayloadSummary title="输入数据" value={node.input_data} nodeType={node.node_type} mode="input" />
      )}
      {hasTracePayload(node.output_data) && (
        <TracePayloadSummary title="输出数据" value={node.output_data} nodeType={node.node_type} nodeName={node.node_name} mode="output" />
      )}
      <RawTraceDetails label="查看完整节点 JSON" value={nodeDetailPayload(node)} />
    </Space>
  );
}

function NodeHeader({ node }: { node: TraceNodeDetail }) {
  const tokenUsage = payloadRecord(node.token_usage);
  return (
    <section style={nodeHeroStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
            <Tag color={statusTagColor(node.status)}>{node.status}</Tag>
            <Tag color="processing">{getNodeLabel(node.node_type)}</Tag>
            <span style={{ color: TEXT, fontSize: 20, fontWeight: 700, lineHeight: 1.2 }}>
              {node.node_name}
            </span>
          </div>
          <div style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
            request_id: {node.request_id}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ color: ACCENT, fontSize: 22, fontWeight: 700 }}>
            {node.duration_ms?.toLocaleString() ?? '-'} ms
          </div>
          <div style={{ color: TEXT_DIM, fontSize: 12 }}>
            round {node.round_index}
          </div>
        </div>
      </div>
      <div style={{ ...metricGridStyle, marginTop: 14 }}>
        <Metric label="开始时间" value={formatTraceTime(node.start_time)} />
        <Metric label="结束时间" value={formatTraceTime(node.end_time)} />
        <Metric label="error_code" value={node.error_code} />
        <Metric label="recover" value={node.recover} />
        <Metric label="tokens" value={tokenUsage?.total_tokens ?? tokenUsage?.prompt_tokens} />
      </div>
      {node.error_message && (
        <div style={{ ...previewStyle, marginTop: 12, borderColor: '#7c2d12', background: '#1f130c', color: '#ffb86c' }}>
          {node.error_message}
        </div>
      )}
    </section>
  );
}

function TracePayloadSummary({
  title,
  value,
  nodeType,
  nodeName,
  mode,
}: {
  title: string;
  value: unknown;
  nodeType: string;
  nodeName?: string;
  mode: 'input' | 'output';
}) {
  const payload = payloadRecord(value);
  if (!payload) {
    return (
      <section style={summaryPanelStyle}>
        <div style={sectionTitleStyle}>{title}</div>
        <div style={previewStyle}>{displayValue(value)}</div>
      </section>
    );
  }
  if (mode === 'input') {
    if (isContextInputPayload(payload)) return <ContextInputSummary inputData={payload} />;
    return <GenericPayloadSummary title={title} payload={payload} />;
  }
  if (isContextTracePayload(payload)) return <ContextTraceSummary outputData={payload} showRaw={false} />;
  if (isRouterTracePayload(payload)) return <RouterTraceSummary outputData={payload} showRaw={false} />;
  if (nodeType === 'final_context') return <FinalContextTraceSummary outputData={payload} />;
  if (nodeType === 'output_guard') return <OutputGuardTraceSummary outputData={payload} />;
  if (nodeType === 'llm_call') return <LlmTraceSummary outputData={payload} />;
  if (nodeType === 'skill_call') return <SkillCallTraceSummary outputData={payload} />;
  if (nodeType === 'tool_selection') return <ToolSelectionTraceSummary outputData={payload} />;
  if (nodeType === 'prompt_budget') return <PromptBudgetTraceSummary outputData={payload} nodeName={nodeName} />;
  if (nodeType === 'prompt_render') return <PromptRenderTraceSummary outputData={payload} />;
  if (nodeType === 'response') return <ResponseTraceSummary outputData={payload} />;
  if (nodeType === 'agent_response') return <AgentResponseTraceSummary outputData={payload} />;
  return <GenericPayloadSummary title={title} payload={payload} />;
}

function LlmTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  const error = asRecord(outputData.error);
  const toolCalls = asRecordList(outputData.tool_calls);
  return (
    <section style={summaryPanelStyle}>
      <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
        <span>LLM 结果</span>
        <Tag color={error ? 'error' : outputData.finish_reason === 'tool_calls' ? 'blue' : 'success'}>
          {displayValue(error?.code ?? outputData.finish_reason)}
        </Tag>
      </div>
      <div style={metricGridStyle}>
        <Metric label="finish_reason" value={outputData.finish_reason} />
        <Metric label="reply_len" value={outputData.reply_len} />
        <Metric label="tool_call_count" value={toolCalls.length} />
        <Metric label="recover" value={error?.recover} />
      </div>
      {hasTracePayload(outputData.reply_preview) && (
        <div style={{ ...previewStyle, marginTop: 10 }}>{displayValue(outputData.reply_preview)}</div>
      )}
      {toolCalls.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
          {toolCalls.map((toolCall, index) => (
            <div key={`${displayValue(toolCall.id)}-${index}`} style={sourceCardStyle}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Tag color="blue">{displayValue(toolCall.name)}</Tag>
                <span style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
                  {displayValue(toolCall.id)}
                </span>
              </div>
              <Metric label="args_summary" value={toolCall.args_summary} />
            </div>
          ))}
        </div>
      )}
      {error && <div style={{ ...previewStyle, marginTop: 10, borderColor: '#7c2d12' }}>{displayValue(error.message)}</div>}
    </section>
  );
}

function FinalContextTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  const toolResults = asRecordList(outputData.tool_results);
  return (
    <section style={summaryPanelStyle}>
      <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
        <span>Final 上下文边界</span>
        <Tag color={outputData.dropped_tool_call_history ? 'warning' : 'success'}>
          dropped_tool_call_history: {displayAuditValue(outputData.dropped_tool_call_history)}
        </Tag>
      </div>
      <div style={metricGridStyle}>
        <Metric label="source_message_count" value={outputData.source_message_count ?? '未记录'} />
        <Metric label="final_message_count" value={outputData.final_message_count ?? '未记录'} />
        <Metric label="tool_result_count" value={outputData.tool_result_count ?? '未记录'} />
        <Metric label="dropped_tool_call_history" value={outputData.dropped_tool_call_history ?? '未记录'} />
      </div>
      {toolResults.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
          {toolResults.map((result, index) => (
            <div key={`${displayValue(result.tool_name)}-${index}`} style={sourceCardStyle}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Tag color={statusTagColor(String(result.status ?? 'success'))}>
                  {displayAuditValue(result.status)}
                </Tag>
                <span style={{ color: ACCENT, fontFamily: 'monospace', fontWeight: 600 }}>
                  {displayAuditValue(result.tool_name)}
                </span>
                <span style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
                  {displayAuditValue(result.tool_call_id)}
                </span>
              </div>
              <div style={{ marginTop: 8 }}>
                <PillRow label="facts" value={result.facts} color="cyan" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ ...previewStyle, marginTop: 10 }}>tool_results: 未记录</div>
      )}
    </section>
  );
}

function OutputGuardTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  const passed = outputData.passed === true;
  return (
    <section style={summaryPanelStyle}>
      <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
        <span>最终回复防泄漏</span>
        <Tag color={passed ? 'success' : 'warning'}>
          {passed ? '通过' : '拦截'}
        </Tag>
      </div>
      <div style={metricGridStyle}>
        <Metric label="passed" value={outputData.passed ?? '未记录'} />
        <Metric label="leak_type" value={outputData.leak_type ?? '未记录'} />
        <Metric label="action" value={outputData.action ?? '未记录'} />
        <Metric label="retry_count" value={outputData.retry_count ?? '未记录'} />
      </div>
    </section>
  );
}

function SkillCallTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  const error = asRecord(outputData.error);
  return (
    <section style={summaryPanelStyle}>
      <div style={{ ...sectionTitleStyle, justifyContent: 'space-between' }}>
        <span>Skill 执行结果</span>
        <Tag color={error ? 'error' : statusTagColor(String(outputData.status ?? 'success'))}>
          {displayValue(error?.code ?? outputData.status ?? 'success')}
        </Tag>
      </div>
      <div style={metricGridStyle}>
        <Metric label="permission_level" value={outputData.permission_level} />
        <Metric label="operation_risk" value={outputData.operation_risk} />
        <Metric label="legacy_tool_name" value={outputData.legacy_tool_name} />
        <Metric label="resolved_operation" value={outputData.resolved_operation} />
        <Metric label="requires_confirmation" value={outputData.requires_confirmation} />
        <Metric label="recover" value={error?.recover} />
      </div>
      {hasTracePayload(outputData.reply_preview) && (
        <div style={{ ...previewStyle, marginTop: 10 }}>{displayValue(outputData.reply_preview)}</div>
      )}
      {error && <div style={{ ...previewStyle, marginTop: 10, borderColor: '#7c2d12' }}>{displayValue(error.message)}</div>}
    </section>
  );
}

function ToolSelectionTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>工具绑定策略</div>
      <div style={metricGridStyle}>
        <Metric label="tool_choice" value={outputData.tool_choice} />
        <Metric label="reason" value={outputData.reason} />
      </div>
      <div style={{ marginTop: 10 }}>
        <PillRow label="selected_tools" value={outputData.selected_tools} color="blue" />
      </div>
      <div style={{ marginTop: 10 }}>
        <PillRow label="bind_tools" value={outputData.bind_tools} color="geekblue" />
      </div>
      <div style={{ marginTop: 10 }}>
        <PillRow label="forced_skills" value={outputData.forced_skills} color="volcano" />
      </div>
    </section>
  );
}

function PromptBudgetTraceSummary({
  outputData,
  nodeName,
}: {
  outputData: Record<string, unknown>;
  nodeName?: string;
}) {
  const budget = asRecord(outputData.budget) ?? outputData;
  const messages = asRecordList(outputData.messages);
  const compression = asRecord(outputData.compression);
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>{nodeName === 'final_llm_context' ? '最终 LLM 上下文' : 'Prompt 预算'}</div>
      <div style={metricGridStyle}>
        <Metric label="max_tokens" value={budget.max_tokens} />
        <Metric label="total_tokens" value={budget.total_tokens} />
        <Metric label="system_tokens" value={budget.system_tokens} />
        <Metric label="message_tokens" value={budget.message_tokens} />
        <Metric label="tool_result_tokens" value={budget.tool_result_tokens} />
        <Metric label="over_budget" value={budget.over_budget} />
      </div>
      <div style={{ marginTop: 10 }}>
        <PillRow label="context_blocks" value={outputData.context_blocks} color="cyan" />
      </div>
      {messages.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
          {messages.slice(0, 8).map((messageItem, index) => (
            <div key={`${displayValue(messageItem.role)}-${index}`} style={sourceCardStyle}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Tag>{displayValue(messageItem.role)}</Tag>
                <span style={{ color: TEXT_DIM, fontSize: 12 }}>#{displayValue(messageItem.index ?? index)}</span>
              </div>
              <div style={previewStyle}>
                {displayValue(messageItem.content_preview ?? messageItem.content)}
              </div>
            </div>
          ))}
        </div>
      )}
      {compression && (
        <div style={{ ...previewStyle, marginTop: 10 }}>
          compression: {displayValue(compression)}
        </div>
      )}
    </section>
  );
}

function PromptRenderTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>Prompt 渲染</div>
      <div style={metricGridStyle}>
        <Metric label="template" value={outputData.template} />
        <Metric label="prompt_len" value={outputData.prompt_len} />
        <Metric label="prompt_hash" value={outputData.prompt_hash} />
      </div>
      <div style={{ marginTop: 10 }}>
        <PillRow label="context_blocks" value={outputData.context_blocks} color="cyan" />
      </div>
      {hasTracePayload(outputData.prompt_preview ?? outputData) && (
        <div style={{ ...previewStyle, marginTop: 10 }}>
          {displayValue(outputData.prompt_preview ?? outputData)}
        </div>
      )}
    </section>
  );
}

function ResponseTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>回复数据来源</div>
      <div style={metricGridStyle}>
        <Metric label="data_source" value={outputData.data_source} />
        <Metric label="has_tool_results" value={outputData.has_tool_results} />
      </div>
    </section>
  );
}

function AgentResponseTraceSummary({ outputData }: { outputData: Record<string, unknown> }) {
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>最终回复</div>
      <div style={metricGridStyle}>
        <Metric label="reason" value={outputData.reason} />
        <Metric label="reply_len" value={outputData.reply_len} />
        <Metric label="data_source" value={outputData.data_source} />
      </div>
      {hasTracePayload(outputData.reply_preview ?? outputData.reply) && (
        <div style={{ ...previewStyle, marginTop: 10 }}>
          {displayValue(outputData.reply_preview ?? outputData.reply)}
        </div>
      )}
    </section>
  );
}

function GenericPayloadSummary({
  title,
  payload,
}: {
  title: string;
  payload: Record<string, unknown>;
}) {
  const entries = Object.entries(payload).filter(([, value]) => {
    if (Array.isArray(value)) return value.length <= 3;
    return typeof value !== 'object' || value === null;
  });
  const complexEntries = Object.entries(payload).filter(([, value]) => value && typeof value === 'object');
  return (
    <section style={summaryPanelStyle}>
      <div style={sectionTitleStyle}>{title}</div>
      {entries.length > 0 && (
        <div style={metricGridStyle}>
          {entries.slice(0, 12).map(([key, value]) => (
            <Metric key={key} label={key} value={value} />
          ))}
        </div>
      )}
      {complexEntries.slice(0, 3).map(([key, value]) => (
        <div key={key} style={{ ...previewStyle, marginTop: 10 }}>
          {key}: {displayValue(value)}
        </div>
      ))}
    </section>
  );
}

function nodeDetailPayload(node: TraceNodeDetail): Record<string, unknown> {
  return {
    id: node.id,
    request_id: node.request_id,
    round_index: node.round_index,
    node_type: node.node_type,
    node_name: node.node_name,
    status: node.status,
    duration_ms: node.duration_ms,
    start_time: node.start_time,
    end_time: node.end_time,
    token_usage: node.token_usage,
    error_code: node.error_code,
    recover: node.recover,
    error_message: node.error_message,
    input_data: node.input_data,
    output_data: node.output_data,
  };
}

function findTimelineNode(
  timeline: TraceTimeline,
  nodeType: string,
  nodeName?: string,
): GanttNode | null {
  for (const round of timeline.rounds) {
    const matched = round.nodes.find(
      (node) => node.node_type === nodeType && (!nodeName || node.node_name === nodeName),
    );
    if (matched) return matched;
  }
  return null;
}

function outputRecordFromNode(node: GanttNode | null): Record<string, unknown> {
  return payloadRecord(node?.output_data) ?? {};
}

function firstToolResultName(toolResults: unknown): string {
  const results = asRecordList(toolResults);
  if (results.length === 0) return '未记录';
  return results
    .map((result) => {
      const name = displayAuditValue(result.tool_name);
      const status = displayAuditValue(result.status);
      return `${name}(${status})`;
    })
    .join(', ');
}

function formatAuditTraceBlock(item: TraceItem, timeline: TraceTimeline): string {
  const finalContextNode = findTimelineNode(timeline, 'final_context', 'build');
  const outputGuardNode = findTimelineNode(timeline, 'output_guard', 'final_json_leak_check');
  const dataSourceNode = findTimelineNode(timeline, 'response', 'final_reply_data_source');
  const finalReplyNode = findTimelineNode(timeline, 'agent_response');
  const finalContext = outputRecordFromNode(finalContextNode);
  const outputGuard = outputRecordFromNode(outputGuardNode);
  const dataSource = outputRecordFromNode(dataSourceNode);
  const finalReply = outputRecordFromNode(finalReplyNode);
  const duration =
    finalContextNode?.duration_ms ??
    outputGuardNode?.duration_ms ??
    finalReplyNode?.duration_ms ??
    item.total_duration_ms;
  const boundary = finalContextNode || outputGuardNode ? 'AI 可接 / Final Agent 隔离' : '未记录';
  const action = outputGuard.action ?? finalReply.reason ?? item.summary.status;
  const result = finalReply.reply_preview ?? finalReply.reply ?? item.summary.status_reason ?? item.summary.status;

  return [
    `[审计追踪] ${displayAuditValue(item.request_id)} final_response`,
    `工单 ID: ${displayAuditValue(item.session_id ?? item.request_id)}`,
    `Run ID: ${displayAuditValue(item.request_id)}`,
    `Trace ID: ${displayAuditValue(item.request_id)}`,
    `边界: ${boundary}`,
    `SOP: ${outputGuardNode ? 'Output Guard 已记录' : '未记录'}`,
    `工具: ${firstToolResultName(finalContext.tool_results)}`,
    `工具结果: count=${displayAuditValue(finalContext.tool_result_count)} source=${displayAuditValue(dataSource.data_source)}`,
    `最终动作: ${displayAuditValue(action)}`,
    `结果: ${displayAuditValue(result)}`,
    `耗时: ${displayAuditValue(duration)}ms`,
  ].join('\n');
}

async function copyRawTracePayload(value: unknown) {
  try {
    await navigator.clipboard.writeText(formatTracePayload(value));
    message.success('原始 JSON 已复制');
  } catch {
    message.error('复制失败');
  }
}

function RawTraceDetails({
  label,
  value,
  defaultOpen = false,
}: {
  label: string;
  value: unknown;
  defaultOpen?: boolean;
}) {
  return (
    <details open={defaultOpen} style={{ cursor: 'pointer' }}>
      <summary style={{ color: TEXT_DIM, fontSize: 12, userSelect: 'none' }}>
        <span>{label}</span>
        <Button
          size="small"
          type="link"
          icon={<CopyOutlined />}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            void copyRawTracePayload(value);
          }}
          style={{ color: ACCENT, padding: '0 4px', marginLeft: 8 }}
        >
          复制 JSON
        </Button>
      </summary>
      <pre style={{
        backgroundColor: CARD,
        padding: 12,
        borderRadius: 6,
        border: `1px solid ${BORDER}`,
        fontSize: 12,
        margin: '8px 0 0 0',
        maxWidth: '100%',
        maxHeight: 640,
        overflow: 'auto',
        overflowWrap: 'anywhere',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        boxSizing: 'border-box',
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
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
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
  minWidth: 0,
};

const blockMetaGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
  gap: 8,
  minWidth: 0,
};

const blockStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  background: CARD,
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 10,
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
};

const nestedPanelStyle: CSSProperties = {
  background: '#111923',
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 10,
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
};

const sourceCardStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  background: '#0f1720',
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 10,
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
};

const scoreGroupStyle: CSSProperties = {
  background: CARD,
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 10,
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
};

const recallOverviewStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1.4fr) minmax(260px, 0.9fr)',
  gap: 12,
  alignItems: 'stretch',
};

const recallSignalGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
  gap: 8,
};

const recallSignalStyle: CSSProperties = {
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: '8px 10px',
  minWidth: 0,
};

const recallDetailGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
  gap: '10px 14px',
  marginTop: 12,
};

const formulaStyle: CSSProperties = {
  display: 'flex',
  gap: 10,
  alignItems: 'center',
  flexWrap: 'wrap',
  background: '#111923',
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: '8px 10px',
  marginTop: 12,
  fontSize: 12,
};

const scoreTrackStyle: CSSProperties = {
  height: 7,
  width: '100%',
  background: '#21262d',
  borderRadius: 999,
  overflow: 'hidden',
};

const scoreFillStyle: CSSProperties = {
  height: '100%',
  minWidth: 2,
  borderRadius: 999,
};

const previewStyle: CSSProperties = {
  color: TEXT,
  background: '#111923',
  border: `1px solid ${BORDER}`,
  borderRadius: 6,
  padding: 8,
  fontSize: 12,
  lineHeight: 1.6,
  minWidth: 0,
  maxWidth: '100%',
  overflowWrap: 'anywhere',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  boxSizing: 'border-box',
};

const sourceStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
  color: TEXT_DIM,
  fontSize: 12,
  minWidth: 0,
  maxWidth: '100%',
};

const nodeHeroStyle: CSSProperties = {
  background: 'linear-gradient(180deg, #111923 0%, #0d1117 100%)',
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  padding: 14,
  minWidth: 0,
  maxWidth: '100%',
  boxSizing: 'border-box',
};

const containedTextStyle: CSSProperties = {
  minWidth: 0,
  maxWidth: '100%',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
};

const tagWrapStyle: CSSProperties = {
  maxWidth: '100%',
  whiteSpace: 'normal',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
};

const detailStackStyle: CSSProperties = {
  width: '100%',
  maxWidth: '100%',
  minWidth: 0,
};

const traceDrawerBodyStyle: CSSProperties = {
  overflowX: 'hidden',
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

  async function copyAuditTraceBlock(item: TraceItem) {
    if (!item.timeline) {
      message.warning('Timeline 尚未加载');
      return;
    }
    try {
      await navigator.clipboard.writeText(formatAuditTraceBlock(item, item.timeline));
      message.success('审计追踪已复制到剪贴板');
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
                      <>
                        <Button
                          size="small"
                          icon={<CopyOutlined />}
                          onClick={(e) => { e.stopPropagation(); copyAuditTraceBlock(item); }}
                          style={{ background: 'transparent', borderColor: BORDER, color: TEXT_DIM, fontSize: 12 }}
                        >
                          复制审计追踪
                        </Button>
                        <Button
                          size="small"
                          icon={<CopyOutlined />}
                          onClick={(e) => { e.stopPropagation(); copyTimingReport(item.timeline!); }}
                          style={{ background: 'transparent', borderColor: BORDER, color: TEXT_DIM, fontSize: 12 }}
                        >
                          复制耗时
                        </Button>
                      </>
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
        width={760}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        styles={{ body: traceDrawerBodyStyle }}
      >
        {nodeDetail ? (
          <NodeTraceVisualization node={nodeDetail} />
        ) : null}
      </Drawer>
    </div>
  );
}
