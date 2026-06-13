import apiClient from './client';

export type DataFlywheelLabel =
  | 'good_reply'
  | 'bad_reply'
  | 'wrong_tool_selection'
  | 'pending_missed'
  | 'hallucinated_execution'
  | 'off_topic'
  | 'sensitive_info_leak'
  | 'missing_wage'
  | 'disabled_worker_used'
  | 'tool_error_ignored'
  | 'unclear_intent'
  | 'needs_regression'
  | 'not_actionable';

export interface DataFlywheelIssueCandidate {
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  reason: string;
  evidence: string;
  suggested_label: DataFlywheelLabel | string;
}

export type DataFlywheelPrelabelStatus = 'pending' | 'accepted' | 'rejected' | string;
export type DataFlywheelPrelabelSource = 'llm_judge' | string;

export interface DataFlywheelPrelabel {
  id: number;
  sample_id: string;
  sample_type: string;
  session_id: string | null;
  turn_id: number | null;
  request_id: string | null;
  source: DataFlywheelPrelabelSource;
  status: DataFlywheelPrelabelStatus;
  labels: DataFlywheelLabel[];
  root_cause: string | null;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  confidence: number;
  reason: string;
  recommended_fix: string | null;
  judge_model: string;
  prompt_version: string;
  accepted_label_ids?: number[] | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DataFlywheelSample {
  sample_id: string;
  sample_type: string;
  quality_labels: DataFlywheelLabel[];
  annotation_status: string;
  prelabels?: DataFlywheelPrelabel[];
  latest_prelabel?: DataFlywheelPrelabel | null;
  session_quality_labels?: DataFlywheelLabel[];
  session_annotation_status?: string;
  session_labels?: DataFlywheelLabelRecord[];
  session_id: string | null;
  turn_id: number;
  request_id: string | null;
  user_input_preview: string | null;
  assistant_reply_preview: string | null;
  selected_tools: string[];
  actual_tools: string[];
  issue_candidates: DataFlywheelIssueCandidate[];
  token_total: number | null;
  latency_ms: number | null;
  source_type: string;
  event_log_status?: 'available' | 'missing' | 'unbound' | string;
  chat_record_source?: 'mysql_conversation_messages' | string;
  created_at: string | null;
}

export interface DataFlywheelSampleListParams {
  sample_type?: string;
  label?: DataFlywheelLabel | string;
  unannotated_only?: boolean;
  session_id?: string;
  request_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface DataFlywheelSampleListResponse {
  items: DataFlywheelSample[];
  total: number;
}

export interface DataFlywheelLabelRecord {
  id: number;
  sample_id: string;
  label: DataFlywheelLabel;
  comment: string | null;
  annotator_id: string | null;
  sample_type?: string;
  session_id?: string | null;
  turn_id?: number | null;
  request_id?: string | null;
  status?: 'open' | 'resolved' | string;
  created_at?: string;
  updated_at?: string;
}

export interface DataFlywheelMessage {
  id?: number;
  role: string;
  content: string;
}

export interface DataFlywheelSource {
  event_file: string | null;
  event_seq_start: number | null;
  event_seq_end: number | null;
  event_log_status?: 'available' | 'missing' | 'unbound' | string;
  chat_record_source?: 'mysql_conversation_messages' | string;
  missing_event_segments?: unknown[];
}

export interface DataFlywheelDetail {
  sample: DataFlywheelSample;
  quality_labels: DataFlywheelLabel[];
  labels: DataFlywheelLabelRecord[];
  prelabels: DataFlywheelPrelabel[];
  messages: DataFlywheelMessage[];
  turn: Record<string, unknown> | null;
  router_decision: Record<string, unknown> | null;
  tool_events: Array<Record<string, unknown>>;
  pending_lifecycle: Array<Record<string, unknown>>;
  issue_candidates: DataFlywheelIssueCandidate[];
  debug_export: Record<string, unknown> | null;
  source: DataFlywheelSource;
}

export interface DataFlywheelSessionTurnReview {
  sample: DataFlywheelSample;
  messages: DataFlywheelMessage[];
  router_decision: Record<string, unknown> | null;
  tool_events: Array<Record<string, unknown>>;
  pending_lifecycle: Array<Record<string, unknown>>;
  source: DataFlywheelSource;
}

export interface DataFlywheelSessionReview {
  session_id: string;
  turns: DataFlywheelSessionTurnReview[];
}

export interface DataFlywheelSessionAnnotations {
  sample_id: string;
  sample_type: 'session' | string;
  session_id: string;
  quality_labels: DataFlywheelLabel[];
  labels: DataFlywheelLabelRecord[];
}

export interface AddSampleLabelRequest {
  label: DataFlywheelLabel;
  sample_type?: string;
  session_id?: string;
  turn_id?: number;
  request_id?: string;
  comment?: string | null;
}

export interface AcceptPrelabelRequest {
  labels?: DataFlywheelLabel[];
  comment?: string | null;
}

export interface ExportJsonlResponse {
  content: string;
  filename: string;
}

export interface CaseDraft {
  id: number;
  draft_id: string;
  source_sample_id: string;
  target_type: string;
  status: string;
  case_json: Record<string, unknown>;
  created_by: string | null;
  created_at?: string;
  updated_at?: string;
}

export type CaseDraftTargetType = 'simulation' | 'evaluation_replay';

export interface DataFlywheelSyncRequest {
  session_id?: string;
  only_missing?: boolean;
  limit?: number;
}

export interface DataFlywheelSyncJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  mode: 'background' | 'inline' | string;
  session_id?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export interface DataFlywheelPrelabelBatchRequest {
  sample_type?: string;
  label?: DataFlywheelLabel | string;
  session_id?: string;
  request_id?: string;
  q?: string;
  unannotated_only?: boolean;
  limit?: number;
  skip_existing?: boolean;
  run_inline?: boolean;
}

export interface DataFlywheelPrelabelBatchResultItem {
  sample_id: string;
  status: 'created' | 'skipped_existing' | 'failed' | string;
  prelabel_id?: number;
  labels?: DataFlywheelLabel[];
  confidence?: number;
  error?: string;
}

export interface DataFlywheelPrelabelBatchResult {
  total: number;
  created: number;
  skipped_existing: number;
  failed: number;
  items: DataFlywheelPrelabelBatchResultItem[];
}

export interface DataFlywheelPrelabelBatchJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  mode: 'background' | 'inline' | string;
  farm_id?: number;
  result?: DataFlywheelPrelabelBatchResult | Record<string, unknown> | null;
  error?: string | null;
}

export interface DeleteSampleLabelResponse {
  deleted: boolean;
  id: number;
}

const samplePath = (sampleId: string) => `/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}`;

export async function listDataFlywheelSamples(
  params?: DataFlywheelSampleListParams
): Promise<DataFlywheelSampleListResponse> {
  const response = await apiClient.get<DataFlywheelSampleListResponse>('/admin/data-flywheel/samples', { params });
  return response.data;
}

export async function getSampleDetail(sampleId: string): Promise<DataFlywheelDetail> {
  const response = await apiClient.get<DataFlywheelDetail>(samplePath(sampleId));
  return response.data;
}

export async function createSamplePrelabel(sampleId: string): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(`${samplePath(sampleId)}/prelabel`);
  return response.data;
}

export async function acceptSamplePrelabel(
  sampleId: string,
  prelabelId: number,
  body: AcceptPrelabelRequest
): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(
    `${samplePath(sampleId)}/prelabels/${prelabelId}/accept`,
    body
  );
  return response.data;
}

export async function rejectSamplePrelabel(
  sampleId: string,
  prelabelId: number
): Promise<DataFlywheelPrelabel> {
  const response = await apiClient.post<DataFlywheelPrelabel>(
    `${samplePath(sampleId)}/prelabels/${prelabelId}/reject`
  );
  return response.data;
}

export async function getSessionReview(sessionId: string): Promise<DataFlywheelSessionReview> {
  const response = await apiClient.get<DataFlywheelSessionReview>(
    `/admin/data-flywheel/sessions/${encodeURIComponent(sessionId)}/review`
  );
  return response.data;
}

export async function getSessionAnnotations(sessionId: string): Promise<DataFlywheelSessionAnnotations> {
  const response = await apiClient.get<DataFlywheelSessionAnnotations>(
    `/admin/data-flywheel/sessions/${encodeURIComponent(sessionId)}/annotations`
  );
  return response.data;
}

export async function addSampleLabel(
  sampleId: string,
  body: AddSampleLabelRequest
): Promise<DataFlywheelLabelRecord> {
  const response = await apiClient.post<DataFlywheelLabelRecord>(`${samplePath(sampleId)}/labels`, body);
  return response.data;
}

export async function deleteSampleLabel(
  sampleId: string,
  labelId: number
): Promise<DeleteSampleLabelResponse> {
  const response = await apiClient.delete<DeleteSampleLabelResponse>(
    `${samplePath(sampleId)}/labels/${labelId}`
  );
  return response.data;
}

export async function resolveSampleLabel(
  sampleId: string,
  labelId: number
): Promise<DataFlywheelLabelRecord> {
  const response = await apiClient.post<DataFlywheelLabelRecord>(
    `${samplePath(sampleId)}/labels/${labelId}/resolve`
  );
  return response.data;
}

export async function markBadCase(
  sampleId: string,
  body: AddSampleLabelRequest
): Promise<DataFlywheelLabelRecord> {
  const response = await apiClient.post<DataFlywheelLabelRecord>(`${samplePath(sampleId)}/bad-case`, body);
  return response.data;
}

export async function exportSampleJsonl(sampleId: string): Promise<ExportJsonlResponse> {
  const response = await apiClient.post<ExportJsonlResponse>('/admin/data-flywheel/export-jsonl', {
    sample_id: sampleId,
  });
  return response.data;
}

export async function createCaseDraft(sampleId: string, targetType: CaseDraftTargetType): Promise<CaseDraft> {
  const response = await apiClient.post<CaseDraft>(`${samplePath(sampleId)}/case-draft`, {
    target_type: targetType,
  });
  return response.data;
}

export async function syncDataFlywheelSessions(body: DataFlywheelSyncRequest): Promise<DataFlywheelSyncJob> {
  const response = await apiClient.post<DataFlywheelSyncJob>('/admin/data-flywheel/sync-sessions', body);
  return response.data;
}

export async function getDataFlywheelSyncJob(jobId: string): Promise<DataFlywheelSyncJob> {
  const response = await apiClient.get<DataFlywheelSyncJob>(
    `/admin/data-flywheel/sync-sessions/${encodeURIComponent(jobId)}`
  );
  return response.data;
}

export async function createSamplePrelabelBatch(
  body: DataFlywheelPrelabelBatchRequest
): Promise<DataFlywheelPrelabelBatchJob> {
  const response = await apiClient.post<DataFlywheelPrelabelBatchJob>(
    '/admin/data-flywheel/prelabels/batch',
    body
  );
  return response.data;
}

export async function getSamplePrelabelBatchJob(
  jobId: string
): Promise<DataFlywheelPrelabelBatchJob> {
  const response = await apiClient.get<DataFlywheelPrelabelBatchJob>(
    `/admin/data-flywheel/prelabels/batch/${encodeURIComponent(jobId)}`
  );
  return response.data;
}
