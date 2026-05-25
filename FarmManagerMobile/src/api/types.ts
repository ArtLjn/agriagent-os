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
}

export interface CycleProfit {
  cycle_id: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
}

export interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
}

export interface ChatRequest {
  cycle_id?: number;
  message: string;
}

export interface ChatResponse {
  reply: string;
}

export interface DailyAdvice {
  cycle_id: number | null;
  advice: string;
  created_at: string;
}

export interface ReportRequest {
  cycle_id?: number;
  report_type: string;
}

export interface ReportResponse {
  cycle_id: number | null;
  report_type: string;
  content: string;
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
  created_at: string;
}

export interface ReportListResponse {
  items: ReportListItem[];
  total: number;
}
