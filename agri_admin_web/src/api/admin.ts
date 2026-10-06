import apiClient from './client';
import type { TracePayload } from '../utils/tracePayload';

// ─── Trace API（对齐 agri_backend_v2 agent /api/v2/traces*）──────────────────────────────
// vite proxy: /api/agent/traces* → http://localhost:8000/api/v2/traces*

export interface TraceRootError {
  node_id?: number | string | null;
  node_type?: string | null;
  node_name?: string | null;
  code?: string | null;
  message?: string | null;
  recover?: string | null;
}

export interface TraceMetrics {
  total_duration_ms?: number;
  llm_duration_ms?: number;
  tool_duration_ms?: number;
  rag_duration_ms?: number;
  memory_duration_ms?: number;
  planner_duration_ms?: number;
  reflection_duration_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  llm_calls?: number;
  tool_calls?: number;
  skill_calls?: number;
  logical_span_count?: number;
  resource_span_count?: number;
  mcp_calls?: number;
  mcp_duration_ms?: number;
  router_calls?: number;
  context_builds?: number;
  [key: string]: unknown;
}

export interface TraceNodeBreakdownItem {
  node_type: string;
  count: number;
  duration_ms_total: number;
  error_count: number;
  avg_duration_ms?: number;
}

/** agri_backend_v2 agent trace 列表项（请求级 summary）*/
export interface TraceRequestSummary {
  request_id: string;
  trace_id?: string;
  conversation_id?: string;
  turn_id?: string;
  user_id?: string;
  farm_uid?: string;
  /** 旧页面字段，仅用于兼容历史响应。 */
  session_id?: string | null;
  farm_id?: number;
  created_at?: string | null;
  node_count: number;
  total_duration_ms: number;
  status?: string;
  status_reason?: string | null;
  error_count?: number;
  warning_count?: number;
  root_error?: TraceRootError | null;
  metrics?: TraceMetrics;
  started_at?: string | null;
  ended_at?: string | null;
  node_breakdown?: TraceNodeBreakdownItem[];
}

/** agri_backend_v2 agent trace node（get_trace_nodes 返回）*/
export interface TraceNode {
  record_kind?: 'node';
  source?: 'traceRecords';
  id?: number | string | null;
  span_id?: string | null;
  parent_span_id?: string | null;
  span_kind?: 'root' | 'internal' | 'client' | string;
  layer?: 'agent' | 'resource' | string;
  phase?: string | null;
  attempt?: number | null;
  attributes?: Record<string, unknown>;
  resource?: Record<string, unknown>;
  sampling?: Record<string, unknown>;
  trace_id?: string;
  request_id?: string;
  conversation_id?: string;
  turn_id?: string;
  step_index?: number;
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  token_usage: Record<string, unknown> | null;
  start_time: string | null;
  end_time?: string | null;
  error_message?: string | null;
  error_code?: string | null;
  recover?: string | null;
  input_data?: TracePayload;
  output_data?: TracePayload;
}

export interface TraceEvent {
  record_kind: 'event';
  source: 'traceEvents';
  event_id: string;
  trace_id: string;
  turn_id: string;
  span_id?: string | null;
  parent_span_id?: string | null;
  seq: number;
  event_type: string;
  phase?: string | null;
  step_index?: number | null;
  attempt?: number | null;
  status_before?: string | null;
  status_after?: string | null;
  terminal: boolean;
  occurred_at: string | null;
  payload_meta?: Record<string, unknown> | null;
  projection_status?: string | null;
  data?: TracePayload;
}

export type TraceTimelineItem = TraceNode | TraceEvent;

export interface TraceRound {
  round_index: number;
  nodes: TraceNode[];
}

/** 前端统一 timeline 结构：按 Runtime step_index 分组，round_index 仅作为旧组件兼容键。 */
export interface TraceTimeline {
  request_id: string;
  trace_id?: string;
  conversation_id?: string;
  turn_id?: string;
  items?: TraceTimelineItem[];
  events?: TraceEvent[];
  evidence_status?: string;
  evidence?: Record<string, unknown>;
  summary?: TraceRequestSummary | null;
  rounds: TraceRound[];
}

/** 节点详情（前端从 timeline node 派生，用于 Drawer 展示）*/
export interface TraceNodeDetail {
  id: number | string;
  request_id: string;
  round_index: number;
  node_type: string;
  node_name: string;
  input_data: TracePayload;
  output_data: TracePayload;
  duration_ms: number | null;
  token_usage: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  error_code?: string | null;
  recover?: string | null;
  start_time: string | null;
  end_time: string | null;
  trace_id?: string;
  span_id?: string | null;
  parent_span_id?: string | null;
  span_kind?: string;
  layer?: string;
  phase?: string | null;
  attempt?: number | null;
  attributes?: Record<string, unknown>;
  resource?: Record<string, unknown>;
  sampling?: Record<string, unknown>;
}

export interface ListTracesParams {
  conversation_id?: string;
  turn_id?: string;
  limit?: number;
  cursor?: string | null;
}

export interface ListTracesResponse {
  items: TraceRequestSummary[];
  next_cursor?: string | null;
  has_more?: boolean;
  /** 旧分页响应兼容字段，agri_backend_v2 cursor API 不保证返回。 */
  total?: number;
}

interface TraceTimelineResponse {
  trace_id: string;
  request_id: string;
  conversation_id: string;
  turn_id: string;
  items: TraceTimelineItem[];
  count: number;
  has_more: boolean;
  evidence_status?: string;
  evidence?: Record<string, unknown>;
}

/**
 * 列出 trace 请求级 summary（agri_backend_v2 /api/v2/traces）。
 * 兼容旧调用：返回 items + next_cursor + has_more。
 */
export async function listTraces(params?: ListTracesParams): Promise<ListTracesResponse> {
  const res = await apiClient.get<ListTracesResponse>('/agent/traces', { params });
  return res.data;
}

/**
 * 列出 trace 请求级 summary（与 listTraces 同一端点，保留旧 API 名以减少调用方改动）。
 */
export async function listTraceRequests(params?: ListTracesParams): Promise<ListTracesResponse> {
  return listTraces(params);
}

/** 获取正式 agri_backend_v2 Trace timeline；兼容层只负责把 items 适配给旧 Gantt 组件。 */
export async function getTimeline(
  traceId: string,
  params: {
    limit?: number;
    include_payload?: boolean;
    include_resource_spans?: boolean;
  } = {},
): Promise<TraceTimeline> {
  const query: Record<string, unknown> = {
    limit: params.limit ?? 400,
    include_payload: params.include_payload ?? true,
  };
  if (params.include_resource_spans) query.include_resource_spans = true;
  const response = await apiClient.get<TraceTimelineResponse>(
    `/agent/traces/${encodeURIComponent(traceId)}/timeline`,
    { params: query },
  );
  const data = response.data;
  const items = data.items ?? [];
  const nodes = items.filter((item): item is TraceNode => item.record_kind !== 'event');
  const events = items.filter((item): item is TraceEvent => item.record_kind === 'event');
  const [summaryResp] = await Promise.all([
    apiClient.get<TraceRequestSummary | null>(
      `/agent/traces/${encodeURIComponent(traceId)}/summary`,
    ).catch(() => null),
  ]);
  return {
    request_id: data.request_id || data.trace_id,
    trace_id: data.trace_id,
    conversation_id: data.conversation_id,
    turn_id: data.turn_id,
    items,
    events,
    evidence_status: data.evidence_status,
    evidence: data.evidence,
    summary: summaryResp?.data ?? null,
    rounds: groupNodesByExecutionStep(nodes),
  };
}

function groupNodesByExecutionStep(nodes: TraceNode[]): TraceRound[] {
  const groups = new Map<number, TraceNode[]>();
  nodes.forEach((node) => {
    const step = typeof node.step_index === 'number' ? node.step_index : 0;
    const group = groups.get(step) ?? [];
    group.push(node);
    groups.set(step, group);
  });
  return [...groups.entries()]
    .sort(([left], [right]) => left - right)
    .map(([step, stepNodes]) => ({ round_index: step, nodes: stepNodes }));
}

export async function getTraceSummary(traceId: string): Promise<TraceRequestSummary | null> {
  const response = await apiClient.get<TraceRequestSummary | null>(
    `/agent/traces/${encodeURIComponent(traceId)}/summary`,
  );
  return response.data;
}

/** 从 timeline node 派生 TraceNodeDetail（前端不再单独请求 node 详情端点）*/
export function deriveNodeDetail(
  requestId: string,
  roundIndex: number,
  node: TraceNode,
): TraceNodeDetail {
  return {
    id: node.id ?? node.span_id ?? 0,
    request_id: requestId,
    round_index: roundIndex,
    node_type: node.node_type,
    node_name: node.node_name,
    input_data: node.input_data ?? null,
    output_data: node.output_data ?? null,
    duration_ms: node.duration_ms,
    token_usage: node.token_usage,
    status: node.status,
    error_message: node.error_message ?? null,
    error_code: node.error_code,
    recover: node.recover,
    start_time: node.start_time,
    end_time: node.end_time ?? null,
    trace_id: node.trace_id,
    span_id: node.span_id,
    parent_span_id: node.parent_span_id,
    span_kind: node.span_kind,
    layer: node.layer,
    phase: node.phase,
    attempt: node.attempt,
    attributes: node.attributes,
    resource: node.resource,
    sampling: node.sampling,
  };
}

// ─── Token Stats API ─────────────────────────────────────────────────────────

export interface ModelTokenStats {
  model: string;
  call_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface TokenSummary {
  days: number;
  total_tokens: number;
  total_requests: number;
  by_model: Record<string, ModelTokenStats>;
}

export interface DailyTokenItem {
  model: string;
  call_type: string;
  user_id?: string | null;
  farm_id?: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
  estimated_cost_cny?: number;
}

export interface DailyTokenStats {
  date: string;
  items: DailyTokenItem[];
}

export interface HourlyTokenItem {
  date: string;
  hour: string;
  user_id?: string | null;
  farm_id: number;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface HourlyTokenStats {
  start_date: string;
  end_date: string;
  items: HourlyTokenItem[];
  hours: string[];
  total_tokens: number;
  total_requests: number;
}

export interface TokenStatsParams {
  days?: number;
  user_id?: string;
  farm_id?: number;
  model?: string;
  start_date?: string;
  end_date?: string;
}

export async function getTokenSummary(params: TokenStatsParams = {}): Promise<TokenSummary> {
  const res = await apiClient.get<TokenSummary>('/admin/stats/tokens', { params });
  return res.data;
}

export async function getDailyTokenStats(
  date: string,
  params: Omit<TokenStatsParams, 'days'> = {}
): Promise<DailyTokenStats> {
  const res = await apiClient.get<DailyTokenStats>('/admin/stats/tokens/daily', {
    params: { date, ...params },
  });
  return res.data;
}

export async function getHourlyTokenStats(
  params: Pick<TokenStatsParams, 'user_id' | 'farm_id' | 'model' | 'start_date' | 'end_date'> = {}
): Promise<HourlyTokenStats> {
  const res = await apiClient.get<HourlyTokenStats>('/admin/stats/tokens/hourly', { params });
  return res.data;
}

// ─── Skills API ──────────────────────────────────────────────────────────────

export interface SkillItem {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  status: string;
  metadata: {
    enabled: boolean;
    disabled_reason: string | null;
    permission_level: string;
    risk_level: string;
    [key: string]: unknown;
  };
}

export interface SkillSummary {
  total: number;
  enabled: number;
  disabled: number;
  admin_only: number;
}

export interface ListSkillsResponse {
  items: SkillItem[];
  total: number;
  summary: SkillSummary;
}

export async function listSkills(): Promise<ListSkillsResponse> {
  const res = await apiClient.get<ListSkillsResponse>('/agent/admin/skills');
  return res.data;
}

/** agri_backend_v2 尚未提供 trace 清理接口，保留显式入口避免旧页面导入时整站加载失败。 */
export async function deleteTracesBefore(_before: string): Promise<{ deleted: number }> {
  void _before;
  throw new Error('agri_backend_v2 trace cleanup endpoint is not available');
}

/** agri_backend_v2 尚未提供 reflection diagnostics 独立接口。 */
export async function getTraceDiagnostics(_requestId: string): Promise<TraceDiagnostics> {
  void _requestId;
  throw new Error('agri_backend_v2 trace diagnostics endpoint is not available');
}

export interface TraceReflectionIssue {
  code?: string;
  severity?: string;
  message?: string;
}

export interface TraceReflectionCheck {
  trigger: string;
  decision: string;
  reason: string;
  checks: string[];
  issues: TraceReflectionIssue[];
  input?: Record<string, unknown>;
}

export interface TraceDiagnostics {
  request_id: string;
  reflection_checks: TraceReflectionCheck[];
  reflection_diagnostic: {
    blocked: boolean;
    decisions: string[];
    issue_codes: string[];
  };
}

export interface UpdateSkillEnabledRequest {
  enabled: boolean;
  disabled_reason?: string;
}

export async function updateSkillEnabled(
  skillName: string,
  payload: UpdateSkillEnabledRequest
): Promise<SkillItem> {
  const res = await apiClient.put<SkillItem>(
    `/agent/admin/skills/${encodeURIComponent(skillName)}/enabled`,
    payload
  );
  return res.data;
}

export interface SkillRouteRecallCandidate {
  skill: string;
  operation: string | null;
  score: number;
  risk: string;
  operation_risk: string | null;
  evidence: Record<string, unknown>;
}

export interface SkillRouteRecallRequest {
  message: string;
  top_k?: number;
}

export interface SkillRouteRecallResponse {
  message: string;
  top_k: number;
  recall_mode: string;
  vector_index_enabled: boolean;
  recall?: Record<string, unknown>;
  top_candidates?: Record<string, unknown>[];
  candidates: SkillRouteRecallCandidate[];
  skill_router?: Record<string, unknown>;
}

export interface SkillRouteRecallDataset {
  path: string;
  format: string;
  total: number;
}

export interface SkillRouteRecallFailure {
  case_id: string;
  message: string;
  expected: {
    skill: string;
    operation: string | null;
  };
  top_k: Array<{
    skill: string;
    operation: string | null;
  }>;
  scores: Record<string, number>;
}

export interface SkillRouteRouterFailure {
  case_id: string;
  message: string;
  expected: {
    skill: string;
    operation: string | null;
  };
  selected: Array<{
    skill: string;
    operation: string | null;
  }>;
  selected_tools: string[];
  selected_operations: Record<string, string[]>;
  selection_path: string;
  reason: string;
}

export interface SkillRouteRecallReport {
  total: number;
  recall_at_1: number;
  recall_at_k: number;
  operation_recall_at_k: number;
  failures: SkillRouteRecallFailure[];
}

export interface SkillRouteRouterReport {
  total: number;
  route_accuracy: number;
  exact_match_rate: number;
  failures: SkillRouteRouterFailure[];
  strict_failures: SkillRouteRouterFailure[];
}

export interface SkillRouteRecallEvalResponse {
  dataset: SkillRouteRecallDataset;
  top_k: number;
  report: SkillRouteRecallReport;
  recall_report: SkillRouteRecallReport;
  router_report: SkillRouteRouterReport;
}

export async function previewSkillRouteRecall(
  payload: SkillRouteRecallRequest
): Promise<SkillRouteRecallResponse> {
  const res = await apiClient.post<SkillRouteRecallResponse>(
    '/agent/admin/skills/route-recall',
    payload
  );
  return res.data;
}

export async function evaluateSkillRouteRecallDataset(
  payload: { top_k?: number } = {}
): Promise<SkillRouteRecallEvalResponse> {
  const res = await apiClient.post<SkillRouteRecallEvalResponse>(
    '/agent/admin/skills/route-recall/evaluate',
    payload
  );
  return res.data;
}

// ─── Prompts API ─────────────────────────────────────────────────────────────

export interface PromptItem {
  name: string;
  version: string;
  active: boolean;
  content_length: number;
  content: string;
}

export interface ListPromptsResponse {
  items: PromptItem[];
  total: number;
}

export interface ReloadPromptsResponse {
  status: string;
  message: string;
}

export async function listPrompts(): Promise<ListPromptsResponse> {
  const res = await apiClient.get<ListPromptsResponse>('/admin/prompts');
  return res.data;
}

export async function reloadPrompts(): Promise<ReloadPromptsResponse> {
  const res = await apiClient.post<ReloadPromptsResponse>('/admin/prompts/reload');
  return res.data;
}

// ─── Config API ──────────────────────────────────────────────────────────────

export interface AIConfig {
  model: string;
  base_url: string;
  api_key: string;
  enable_thinking: boolean;
  enable_session_summary: boolean;
}

export interface TraceConfig {
  batch_size: number;
  flush_interval: number;
  trace_ttl_days: number;
}

export interface TokenQuotaConfig {
  monthly_limit: number;
  weekly_limit: number;
  over_quota_action: "warn" | "reject";
}

export interface LangsmithConfig {
  enabled: boolean;
  project: string;
}

export interface AdminConfig {
  ai: AIConfig;
  trace: TraceConfig;
  token_quota: TokenQuotaConfig;
  langsmith: LangsmithConfig;
}

export interface ClearCacheResponse {
  cleared: {
    skill_cache: number;
    ttl_cache: number;
  };
}

export async function getConfig(): Promise<AdminConfig> {
  const res = await apiClient.get<AdminConfig>('/admin/config');
  return res.data;
}

export async function clearCache(): Promise<ClearCacheResponse> {
  const res = await apiClient.post<ClearCacheResponse>('/admin/cache/clear');
  return res.data;
}

// ─── Users API ───────────────────────────────────────────────────────────────

export interface AdminUserListItem {
  id: string;
  phone: string;
  nickname: string | null;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
  farm_name: string | null;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total: number;
}

export async function listUsers(params?: { page?: number; page_size?: number; status?: string }): Promise<AdminUserListResponse> {
  const res = await apiClient.get<AdminUserListResponse>('/admin/users', { params });
  return res.data;
}
