import apiClient from './client';

export type DataFlywheelLabel =
  | 'good_reply'
  | 'bad_reply'
  | 'wrong_tool_selection'
  | 'tool_parameter_mismatch'
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
  risk_score?: number | null;
  rule_score?: number | null;
  risk_dominant_signal?: 'rule' | 'judge' | string | null;
  risk_severity?: 'P0' | 'P1' | string | null;
  rule_hits?: string[];
  judge_bad_prob?: number | null;
  judge_issue_type?: string | null;
  judge_suggested_label?: DataFlywheelLabel | string | null;
  source_type: string;
  event_log_status?: 'available' | 'missing' | 'unbound' | string;
  chat_record_source?: 'mysql_conversation_messages' | string;
  created_at: string | null;
}

export interface DataFlywheelSampleListParams {
  sample_type?: string;
  label?: DataFlywheelLabel | string;
  unannotated_only?: boolean;
  sort?: 'risk' | 'time';
  sort_by?: 'risk' | 'time';
  min_risk?: number;
  severity?: 'P0' | 'P1' | 'all';
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

export interface DataFlywheelRepairCandidate {
  sample_id: string;
  session_id: string | null;
  turn_id: number | null;
  request_id: string | null;
  labels: DataFlywheelLabel[] | string[];
  fix_target: string;
  priority: number;
  suggested_action: string;
  regression_ready: boolean;
  verification_commands: string[];
  secondary_targets: Array<{
    label: DataFlywheelLabel | string;
    fix_target: string;
    priority: number;
  }>;
}

export interface DataFlywheelRepairCandidateListParams extends DataFlywheelSampleListParams {
  sample_ids?: string[];
  fix_target?: string;
  regression_ready?: boolean;
}

export interface DataFlywheelRepairCandidateListResponse {
  items: DataFlywheelRepairCandidate[];
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

export type ReviewIssueChainStatus =
  | 'ready_for_review'
  | 'needs_evidence'
  | 'accepted'
  | 'rejected'
  | 'not_actionable'
  | string;

export type ReviewIssueChainEvidenceStatus = 'ready_for_review' | 'needs_evidence' | string;

export interface ReviewIssueChain {
  chain_id: string;
  session_id: string;
  trigger_turn_id: number;
  context_turn_ids: number[];
  result_turn_ids: number[];
  status: ReviewIssueChainStatus;
  severity: 'P0' | 'P1' | string;
  dominant_signal: string;
  risk_context?: {
    risk_score?: number | null;
    rule_score?: number | null;
    judge_bad_prob?: number | null;
    dominant_signal?: string | null;
    rule_hits?: string[];
    trigger_reason?: string | null;
    scoring_rule?: string | null;
    [key: string]: unknown;
  };
  diagnosis: {
    title?: string | null;
    summary?: string | null;
    candidate_type?: string | null;
    suggested_labels?: string[];
    [key: string]: unknown;
  };
  ai_judge: {
    bad_prob?: number | null;
    issue_type?: string | null;
    suggested_label?: string | null;
    dominant_signal?: string | null;
    [key: string]: unknown;
  };
  human_review: {
    status?: string;
    labels?: DataFlywheelLabelRecord[] | Array<Record<string, unknown>>;
    quality_labels?: string[];
    expected_behavior?: string | null;
    root_cause?: string | null;
    fix_target?: string | null;
    reviewer_comment?: string | null;
    false_positive_reason?: string | null;
    missing_evidence?: string[];
    [key: string]: unknown;
  };
  regression: {
    needs_regression?: boolean;
    regression_ready?: boolean;
    source_sample_id?: string;
    [key: string]: unknown;
  };
  repair: {
    fix_target?: string;
    regression_ready?: boolean;
    export_blocked_reason?: string | null;
    [key: string]: unknown;
  };
}

export interface DailyReviewSessionCard {
  session_id: string;
  summary: string;
  latest_turn_id: number;
  risk_score: number | null;
  severity: 'P0' | 'P1' | string;
}

export interface DailyReviewInboxItem {
  session_id: string;
  session_card: DailyReviewSessionCard;
  highest_risk_chain: ReviewIssueChain;
  candidate_chain_count: number;
  evidence_status: ReviewIssueChainEvidenceStatus;
  next_action: string;
  status: ReviewIssueChainStatus;
  dominant_signal: string;
  updated_at?: string | null;
}

export interface DailyReviewInboxParams {
  session_id?: string;
  min_risk?: number;
  severity?: 'P0' | 'P1' | 'all';
  status?: string;
  evidence_status?: string;
  dominant_signal?: string;
  limit?: number;
  offset?: number;
}

export interface DailyReviewInboxResponse {
  items: DailyReviewInboxItem[];
  total: number;
}

export interface ReviewIssueChainTimelineTurn {
  turn_id: number;
  request_id: string | null;
  user_input_preview: string | null;
  assistant_reply_preview: string | null;
  messages: DataFlywheelMessage[];
  selected_tools: string[];
  tool_events: Array<Record<string, unknown>>;
  pending_lifecycle: Array<Record<string, unknown>>;
  router_decision: Record<string, unknown>;
  source: DataFlywheelSource;
  event_log_status: string;
  chain_role: 'trigger' | 'context' | 'result' | 'unrelated' | string;
}

export interface ReviewIssueChainEvidenceItem {
  key: string;
  status: 'present' | 'missing' | 'needs_human' | string;
  turn_id?: number | null;
}

export interface ReviewIssueChainDetail {
  chain: ReviewIssueChain;
  session_id: string;
  timeline: ReviewIssueChainTimelineTurn[];
  trigger_turn: ReviewIssueChainTimelineTurn | null;
  context_turns: ReviewIssueChainTimelineTurn[];
  result_turns: ReviewIssueChainTimelineTurn[];
  turn_debug_summaries: Record<string, ReviewIssueChainTimelineTurn | Record<string, unknown>>;
  evidence_checklist: ReviewIssueChainEvidenceItem[];
  evidence_status: ReviewIssueChainEvidenceStatus;
  existing_labels: DataFlywheelLabelRecord[] | Array<Record<string, unknown>>;
  ai_judge: ReviewIssueChain['ai_judge'];
}

export interface ReviewIssueChainReviewRequest {
  status: 'accepted' | 'rejected' | 'not_actionable' | 'needs_evidence' | string;
  context_turn_ids?: number[];
  result_turn_ids?: number[];
  final_labels?: string[];
  root_cause?: string;
  expected_behavior?: string;
  fix_target?: string;
  reviewer_comment?: string;
  false_positive_reason?: string;
  missing_evidence?: string[];
}

export interface ReviewIssueChainReviewResponse {
  chain: ReviewIssueChain;
}

export interface ReviewIssueChainAiJudgeResponse {
  chain: ReviewIssueChain;
}

export interface CreateReviewIssueChainCandidateRequest {
  trigger_turn_id: number;
  context_turn_ids?: number[];
  result_turn_ids?: number[];
  severity?: 'P0' | 'P1' | string;
  dominant_signal?: string;
  suggested_labels?: string[];
  missing_evidence?: string[];
}

export interface CreateReviewIssueChainCandidateResponse {
  chain: ReviewIssueChain;
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
  source_sample_id?: string | null;
  chain_id?: string;
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

export const REPAIR_PACK_STATUS = {
  DRAFT: 'draft',
  EXPORTED: 'exported',
  EXPORT_FAILED: 'export_failed',
  VERIFICATION_FAILED: 'verification_failed',
  RESOLVED: 'resolved',
  DISCARDED: 'discarded',
} as const;
export type RepairPackStatus =
  | 'draft'
  | 'exported'
  | 'export_failed'
  | 'verification_failed'
  | 'resolved'
  | 'discarded';

export interface RepairPackCase {
  sample_id?: string | null;
  session_id?: string | null;
  turn_id?: number | null;
  request_id?: string | null;
  labels?: string[];
  fix_target?: string;
  priority?: number;
  suggested_action?: string | null;
  regression_ready?: boolean;
  observed_failure?: string | null;
  expected_behavior?: string | null;
  evidence?: string | null;
  source_debug_json?: string | null;
  regression_draft?: string | null;
}

export interface DataFlywheelRepairPack {
  id: number;
  pack_id: string;
  fix_target: string;
  labels: string[];
  source_sample_ids: string[];
  source_chain_ids?: string[];
  source_label_ids?: number[];
  dedup_key?: string | null;
  status: RepairPackStatus;
  export_path: string | null;
  manifest: Record<string, unknown>;
  cases?: RepairPackCase[];
  export_error?: string | null;
  repair_note?: string | null;
  verification_summary?: Record<string, unknown> | null;
  created_by?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  deduplicated?: boolean;
  dedup_existing_pack_id?: string;
  payload?: {
    manifest: Record<string, unknown>;
    cases_jsonl: RepairPackCase[];
    readme: string;
    debug_files: Record<string, unknown>;
    regression_drafts: Record<string, unknown>;
  };
}

export interface RepairPackListParams {
  status?: RepairPackStatus;
  fix_target?: string;
  include_discarded?: boolean;
  page?: number;
  page_size?: number;
}

export interface RepairPackListResponse {
  items: DataFlywheelRepairPack[];
  total: number;
  page: number;
  page_size: number;
}

export interface DiscardRepairPackRequest {
  reason?: string | null;
}

export interface CreateRepairPackRequest extends DataFlywheelRepairCandidateListParams {
  sample_ids?: string[];
  fix_target_override?: string;
  min_priority?: number;
  limit?: number;
}

export interface ResolveRepairPackRequest {
  repair_note?: string | null;
  verification_summary?: Record<string, unknown> | null;
}

export interface VerificationFailureRequest {
  verification_summary: Record<string, unknown>;
}

const samplePath = (sampleId: string) => `/admin/data-flywheel/samples/${encodeURIComponent(sampleId)}`;
const reviewIssueChainPath = (chainId: string) =>
  `/admin/data-flywheel/review-issue-chains/${encodeURIComponent(chainId)}`;

export async function listDataFlywheelSamples(
  params?: DataFlywheelSampleListParams
): Promise<DataFlywheelSampleListResponse> {
  const response = await apiClient.get<DataFlywheelSampleListResponse>('/admin/data-flywheel/samples', { params });
  return response.data;
}

export async function listRepairPackCandidates(
  params?: DataFlywheelRepairCandidateListParams
): Promise<DataFlywheelRepairCandidateListResponse> {
  const response = await apiClient.get<DataFlywheelRepairCandidateListResponse>(
    '/admin/data-flywheel/repair-candidates',
    { params, paramsSerializer: { indexes: null } }
  );
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

export async function getDailyReviewInbox(
  params?: DailyReviewInboxParams
): Promise<DailyReviewInboxResponse> {
  const response = await apiClient.get<DailyReviewInboxResponse>(
    '/admin/data-flywheel/daily-review/inbox',
    { params }
  );
  return response.data;
}

export async function getReviewIssueChain(chainId: string): Promise<ReviewIssueChainDetail> {
  const response = await apiClient.get<ReviewIssueChainDetail>(
    reviewIssueChainPath(chainId)
  );
  return response.data;
}

export async function saveReviewIssueChainReview(
  chainId: string,
  body: ReviewIssueChainReviewRequest
): Promise<ReviewIssueChainReviewResponse> {
  const response = await apiClient.post<ReviewIssueChainReviewResponse>(
    `${reviewIssueChainPath(chainId)}/review`,
    body
  );
  return response.data;
}

export async function createReviewIssueChainAiJudge(
  chainId: string
): Promise<ReviewIssueChainAiJudgeResponse> {
  const response = await apiClient.post<ReviewIssueChainAiJudgeResponse>(
    `${reviewIssueChainPath(chainId)}/ai-judge`
  );
  return response.data;
}

export async function createReviewIssueChainCandidate(
  body: CreateReviewIssueChainCandidateRequest
): Promise<CreateReviewIssueChainCandidateResponse> {
  const response = await apiClient.post<CreateReviewIssueChainCandidateResponse>(
    '/admin/data-flywheel/review-issue-chains/candidates',
    body
  );
  return response.data;
}

export async function createReviewIssueChainCaseDraft(
  chainId: string,
  targetType: CaseDraftTargetType
): Promise<CaseDraft> {
  const response = await apiClient.post<CaseDraft>(`${reviewIssueChainPath(chainId)}/case-draft`, {
    target_type: targetType,
  });
  return response.data;
}

export async function createReviewIssueChainRepairPack(chainId: string): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `${reviewIssueChainPath(chainId)}/repair-pack`
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

export async function createRepairPack(
  body: CreateRepairPackRequest
): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    '/admin/data-flywheel/repair-packs',
    body
  );
  return response.data;
}

export async function getRepairPack(packId: string): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.get<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}`
  );
  return response.data;
}

export async function markRepairPackResolved(
  packId: string,
  body: ResolveRepairPackRequest
): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}/resolve`,
    body
  );
  return response.data;
}

export async function recordRepairPackVerificationFailure(
  packId: string,
  body: VerificationFailureRequest
): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}/verification-failed`,
    body
  );
  return response.data;
}

export async function listRepairPacks(
  params?: RepairPackListParams
): Promise<RepairPackListResponse> {
  const response = await apiClient.get<RepairPackListResponse>(
    '/admin/data-flywheel/repair-packs',
    { params }
  );
  return response.data;
}

export async function discardRepairPack(
  packId: string,
  body?: DiscardRepairPackRequest
): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}/discard`,
    body ?? {}
  );
  return response.data;
}

export async function reopenRepairPack(packId: string): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}/reopen`
  );
  return response.data;
}

export async function rebuildRepairPack(packId: string): Promise<DataFlywheelRepairPack> {
  const response = await apiClient.post<DataFlywheelRepairPack>(
    `/admin/data-flywheel/repair-packs/${encodeURIComponent(packId)}/rebuild`
  );
  return response.data;
}
