import apiClient from './client';
import type { TracePayload } from '../utils/tracePayload';

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
  input_data: TracePayload;
  output_data: TracePayload;
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
  input_data: TracePayload;
  output_data: TracePayload;
  duration_ms: number | null;
  token_usage: string | null;
  status: string;
  error_message: string | null;
  start_time: string | null;
  end_time: string | null;
}

export interface TraceReflectionIssue {
  code?: string;
  severity?: string;
  message?: string;
  evidence?: unknown;
}

export interface TraceReflectionCheck {
  trigger: string;
  decision: string;
  reason: string;
  checks: string[];
  issues: TraceReflectionIssue[];
  input: Record<string, unknown>;
}

export interface TraceReflectionDiagnostic {
  blocked: boolean;
  decisions: string[];
  issue_codes: string[];
}

export interface TraceDiagnostics {
  request_id: string;
  reflection_checks: TraceReflectionCheck[];
  reflection_diagnostic: TraceReflectionDiagnostic;
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

export async function getTraceDiagnostics(requestId: string): Promise<TraceDiagnostics> {
  const res = await apiClient.get<TraceDiagnostics>(`/admin/traces/${requestId}/diagnostics`);
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
  const res = await apiClient.get<ListSkillsResponse>('/admin/skills');
  return res.data;
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
    `/admin/skills/${encodeURIComponent(skillName)}/enabled`,
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

export async function listUsers(params?: { page?: number; size?: number; status?: string }): Promise<AdminUserListResponse> {
  const res = await apiClient.get<AdminUserListResponse>('/admin/users', { params });
  return res.data;
}
