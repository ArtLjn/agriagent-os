import apiClient from './client';

// ─── Trace API ───────────────────────────────────────────────────────────────

export interface TraceRecord {
  id: number;
  request_id: string;
  session_id: string | null;
  farm_id: number;
  round_index: number;
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  token_usage: string | null;
  error_message: string | null;
  created_at: string;
}

export interface TraceNode {
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  token_usage: Record<string, unknown> | null;
  start_time: string | null;
  error_message: string | null;
  input_data: string | null;
  output_data: string | null;
}

export interface TraceRound {
  round_index: number;
  nodes: TraceNode[];
}

export interface TraceTimeline {
  request_id: string;
  rounds: TraceRound[];
}

export interface TraceNodeDetail {
  id: number;
  request_id: string;
  round_index: number;
  node_type: string;
  node_name: string;
  input_data: string | null;
  output_data: string | null;
  duration_ms: number | null;
  token_usage: string | null;
  status: string;
  error_message: string | null;
  start_time: string | null;
  end_time: string | null;
}

export interface ListTracesParams {
  request_id?: string;
  session_id?: string;
  farm_id?: number;
  limit?: number;
  offset?: number;
}

export interface ListTracesResponse {
  items: TraceRecord[];
  total: number;
}

export interface DeleteTracesResponse {
  deleted: number;
}

export async function listTraces(params?: ListTracesParams): Promise<ListTracesResponse> {
  const res = await apiClient.get<ListTracesResponse>('/admin/traces', { params });
  return res.data;
}

export async function getTimeline(requestId: string): Promise<TraceTimeline> {
  const res = await apiClient.get<TraceTimeline>(`/admin/traces/${requestId}/timeline`);
  return res.data;
}

export async function getNodeDetail(requestId: string, nodeId: string): Promise<TraceNodeDetail> {
  const res = await apiClient.get<TraceNodeDetail>(`/admin/traces/${requestId}/nodes/${nodeId}`);
  return res.data;
}

export async function deleteTracesBefore(before: string): Promise<DeleteTracesResponse> {
  const res = await apiClient.delete<DeleteTracesResponse>('/admin/traces', { params: { before } });
  return res.data;
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

export async function getTokenSummary(days?: number): Promise<TokenSummary> {
  const res = await apiClient.get<TokenSummary>('/admin/stats/tokens', { params: { days } });
  return res.data;
}

export async function getDailyTokenStats(date: string): Promise<DailyTokenStats> {
  const res = await apiClient.get<DailyTokenStats>('/admin/stats/tokens/daily', { params: { date } });
  return res.data;
}

// ─── Skills API ──────────────────────────────────────────────────────────────

export interface SkillItem {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  status: string;
}

export interface ListSkillsResponse {
  items: SkillItem[];
  total: number;
}

export async function listSkills(): Promise<ListSkillsResponse> {
  const res = await apiClient.get<ListSkillsResponse>('/admin/skills');
  return res.data;
}

// ─── Prompts API ─────────────────────────────────────────────────────────────

export interface PromptItem {
  name: string;
  version: string;
  active: boolean;
  content_length: number;
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
}

export interface TraceConfig {
  batch_size: number;
  flush_interval: number;
  trace_ttl_days: number;
}

export interface TokenQuotaConfig {
  daily_limit: number;
  over_quota_action: string;
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
