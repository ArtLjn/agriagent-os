import apiClient from './client';

export type DataFlywheelLabel =
  | 'good_reply'
  | 'bad_reply'
  | 'wrong_tool_selection'
  | 'pending_missed'
  | 'hallucinated_execution'
  | 'missing_wage'
  | 'disabled_worker_used'
  | 'needs_regression'
  | 'not_actionable';

export interface DataFlywheelSample {
  sample_id: string;
  sample_type: string;
  quality_labels: DataFlywheelLabel[];
  annotation_status: string;
  session_id: string | null;
  turn_id: string | null;
  request_id: string | null;
  user_input_preview: string | null;
  assistant_reply_preview: string | null;
  selected_tools: string[];
  actual_tools: string[];
  token_total: number | null;
  latency_ms: number | null;
  source_type: string;
  created_at: string;
}

export interface DataFlywheelSampleListParams {
  sample_type?: string;
  label?: DataFlywheelLabel | string;
  annotation_status?: string;
  session_id?: string;
  request_id?: string;
  limit?: number;
  offset?: number;
}

export interface DataFlywheelSampleListResponse {
  items: DataFlywheelSample[];
  total?: number;
}

export interface DataFlywheelLabelRecord {
  id: number;
  sample_id: string;
  label: DataFlywheelLabel;
  comment: string | null;
  annotator_id: string | null;
  sample_type?: string;
  session_id?: string | null;
  turn_id?: string | null;
  request_id?: string | null;
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
  missing_event_segments?: unknown[];
}

export interface DataFlywheelDetail {
  sample: DataFlywheelSample;
  quality_labels: DataFlywheelLabel[];
  labels: DataFlywheelLabelRecord[];
  messages: DataFlywheelMessage[];
  turn: unknown;
  router_decision: unknown;
  tool_events: unknown[];
  pending_lifecycle: unknown[];
  debug_export: unknown;
  source: DataFlywheelSource;
}

export interface AddSampleLabelRequest {
  label: DataFlywheelLabel;
  comment?: string | null;
  annotator_id?: string | null;
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
  case_json: unknown;
  created_by: string | null;
  created_at?: string;
  updated_at?: string;
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

export async function addSampleLabel(
  sampleId: string,
  body: AddSampleLabelRequest
): Promise<DataFlywheelLabelRecord> {
  const response = await apiClient.post<DataFlywheelLabelRecord>(`${samplePath(sampleId)}/labels`, body);
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

export async function createCaseDraft(sampleId: string, targetType: string): Promise<CaseDraft> {
  const response = await apiClient.post<CaseDraft>(`${samplePath(sampleId)}/case-draft`, {
    target_type: targetType,
  });
  return response.data;
}
