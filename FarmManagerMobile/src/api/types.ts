export interface CropTemplate {
  id: number;
  name: string;
  variety: string | null;
  stages: GrowthStage[];
}

export interface GrowthStage {
  id: number;
  crop_template_id: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks: string | null;
}

export interface CropCycle {
  id: number;
  name: string;
  crop_template_id: number;
  start_date: string;
  field_name: string | null;
  total_area_mu?: string | null;
  unit_area_mu?: string | null;
  unit_count?: number;
  current_stage_name?: string | null;
  season?: string | null;
  batch_note?: string | null;
  status: string;
  stages: CycleStage[];
}

export interface CycleStage {
  id: number;
  cycle_id: number;
  name: string;
  start_date: string;
  end_date: string;
  order_index: number;
  key_tasks: string | null;
  is_current: boolean;
}

export interface CropCycleListItem {
  id: number;
  name: string;
  crop_template_name: string;
  start_date: string;
  status: string;
  current_stage_name: string | null;
  total_area_mu?: string | null;
  unit_area_mu?: string | null;
  unit_count?: number;
  field_name?: string | null;
  season?: string | null;
}

export interface PlantingUnit {
  id: number;
  farm_id: number;
  cycle_id: number;
  name: string;
  area_mu: string | null;
  planted_date: string | null;
  status: string;
  note: string | null;
}

export interface OperationType {
  name: string;
  crop: string | null;
  is_builtin: boolean;
  sort_order: number;
}

export interface Worker {
  id: number;
  farm_id: number;
  name: string;
  phone: string | null;
  default_pay_type: string;
  default_unit_price: string | null;
  note: string | null;
  status: string;
}

export interface WorkerCreateRequest {
  name: string;
  phone?: string;
  default_pay_type?: string;
  default_unit_price?: string;
  note?: string;
}

export interface WorkerCycleSummary {
  cycle_id: number;
  cycle_name: string;
  total_payable: string;
  total_paid: string;
  total_unpaid: string;
  entry_count: number;
  recent_operation_type?: string | null;
  recent_work_date?: string | null;
}

export interface WorkerSummaryItem {
  id: number;
  name: string;
  phone?: string | null;
  default_pay_type?: string | null;
  default_unit_price?: string | null;
  total_payable: string;
  total_paid: string;
  total_unpaid: string;
  entry_count: number;
  cycle_summaries: WorkerCycleSummary[];
}

export interface WorkerSummaryResponse {
  items: WorkerSummaryItem[];
  total: number;
  total_payable?: string;
  total_paid?: string;
  total_unpaid?: string;
}

export interface UnsettledLaborWorker {
  worker_name: string;
  unpaid_amount: string | number;
  entry_count: number;
}

export interface UnsettledLaborSummary {
  total_unpaid: string | number;
  workers: UnsettledLaborWorker[];
}

export interface LaborEntryCreate {
  worker_id: number;
  pay_type?: string;
  quantity: string;
  unit_price: string;
  paid_amount?: string;
}

export interface WageCreateRequest {
  cycle_id: number;
  operation_type: string;
  worker_id?: number;
  worker_name: string;
  quantity: string;
  unit_price: string;
  paid_amount?: string;
  work_date: string;
  pay_type?: string;
  crop_name?: string;
  note?: string;
  client_request_id: string;
}

export interface WageEntryResponse {
  id: number;
  cycle_id: number;
  worker_id: number;
  worker_name: string;
  operation_type: string;
  pay_type: string;
  quantity: string;
  unit_price: string;
  payable_amount: string;
  paid_amount: string;
  unpaid_amount: string;
  work_date: string;
  note?: string | null;
  cost_record_id?: number | null;
}

export interface OperationWorkOrder {
  id: number;
  farm_id: number;
  cycle_id: number | null;
  cycle_name?: string | null;
  operation_type: string;
  operation_date: string;
  scope_type: string;
  unit_ids: number[];
  unit_names: string[];
  note: string | null;
  labor_cost_record_id: number | null;
  total_payable_amount: string;
  total_paid_amount: string;
  total_unpaid_amount: string;
}

export interface FarmLog {
  id: number;
  cycle_id: number;
  operation_type: string;
  operation_date: string;
  operation_time: string | null;
  note: string | null;
  photo_urls: string | null;
  created_at: string;
}

export interface CostRecord {
  id: number;
  cycle_id: number | null;
  record_type: string;
  category: string;
  amount: string;
  record_date: string;
  note: string | null;
  record_subtype?: string;
  counterparty?: string;
  due_date?: string;
  settled_at?: string;
  parent_record_id?: number;
  source_type?: string | null;
  source_id?: number | null;
  source_label?: string | null;
  created_at?: string;
  createdAt?: string;
}

export interface CycleProfit {
  cycle_id: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
  labor_cost?: string;
  labor_entry_cost?: string;
  operation_labor_cost?: string;
}

export interface AdviceItem {
  title: string;
  detail: string;
  priority: number;
  icon: string;
}

export interface PendingActionContext {
  original_input: string;
  extracted_params: Record<string, unknown>;
  notes: string[];
}

export interface PendingAction {
  action_id: string;
  skill_name: string;
  params: Record<string, any>;
  context?: PendingActionContext | null;
}

export interface ChatMessage {
  role: "user" | "agent";
  content: string;
  pending_action?: PendingAction | null;
  pending_action_handled?: boolean;
  is_streaming?: boolean;
}

export interface ChatRequest {
  cycle_id?: number;
  message: string;
}

export interface ChatResponse {
  reply: string;
  pending_action: PendingAction | null;
}

export interface ConversationListItem {
  id: number;
  session_id: string;
  status: string;
  title?: string;
  preview?: string;
  category?: string;
  created_at: string;
  last_active_at: string;
}

export interface ConversationMessageItem {
  id: number;
  role: "user" | "assistant" | "agent";
  content: string;
  skills?: string[] | null;
  pending_action?: PendingAction | null;
  created_at: string;
}

export interface DailyAdvice {
  cycle_id: number | null;
  preview: string;
  advice: string;
  items: AdviceItem[];
  created_at: string;
}

export interface ReportRequest {
  cycle_id?: number;
  report_type: string;
}

export interface ReportOverviewMetrics {
  active_cycles: number;
  log_count: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
}

export interface ReportCycleItem {
  cycle_id: number;
  name: string;
  field_name: string | null;
  current_stage: string;
  progress_percent: number;
  period_log_count: number;
  total_stages: number;
  current_stage_index: number;
  days_elapsed: number;
}

export interface ReportCostItem {
  category: string;
  amount: string;
  record_type: string;
  record_date: string;
  note: string | null;
}

export interface ReportLogItem {
  operation_type: string;
  operation_date: string;
  note: string | null;
  cycle_name: string | null;
}

export interface ReportAdviceItem {
  title: string;
  detail: string;
  priority: number;
}

export interface StructuredReportData {
  report_type: string;
  period_start: string;
  period_end: string;
  overview: ReportOverviewMetrics;
  cycles: ReportCycleItem[];
  costs: ReportCostItem[];
  logs: ReportLogItem[];
  advice: ReportAdviceItem[];
  summary: string;
}

export interface ReportResponse {
  cycle_id: number | null;
  report_type: string;
  content: string;
  structured_data: StructuredReportData | null;
  created_at: string;
}

export interface WeatherForecast {
  daily: {
    time: string[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_sum: number[];
    windspeed_10m_max: number[];
  };
}

export interface ReportListItem {
  id: number;
  cycle_id: number | null;
  report_type: string;
  content: string;
  structured_data: StructuredReportData | null;
  created_at: string;
}

export interface ReportListResponse {
  items: ReportListItem[];
  total: number;
}

export interface DebtSummary {
  counterparty: string;
  total_debt: string;
  total_settled: string;
  remaining: string;
  record_count: number;
}

export interface DebtListResponse {
  items: CostRecord[];
  total: number;
  summary: DebtSummary[];
}

export interface UserProfile {
  id: string;
  phone: string;
  nickname: string;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface LoginParams {
  phone: string;
  password: string;
}

export interface RegisterParams {
  phone: string;
  password: string;
  nickname?: string;
}

export interface UpdateProfileParams {
  nickname?: string;
  avatar_url?: string;
}

export interface CropTemplateParseResponse {
  name: string;
  variety: string | null;
  stages: {
    name: string;
    duration_days: number;
    order_index: number;
    key_tasks: string | null;
  }[];
}

export interface CreateTemplateRequest {
  name: string;
  variety?: string | null;
  stages: {
    name: string;
    duration_days: number;
    order_index: number;
    key_tasks?: string | null;
  }[];
}

export interface CycleParseResponse {
  name: string;
  crop_template_id: number | null;
  start_date: string;
  field_name: string | null;
}
