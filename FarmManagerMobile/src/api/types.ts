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
  created_at?: string;
  createdAt?: string;
}

export interface CycleProfit {
  cycle_id: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
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
