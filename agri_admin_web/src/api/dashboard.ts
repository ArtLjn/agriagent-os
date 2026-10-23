import apiClient from './client';

export interface DashboardSummary {
  farm_id: number;
  name: string;
  location: string | null;
  today: string;
  active_cycles: {
    cycle_id: number;
    crop: string;
    area_mu: number | null;
    current_stage: string | null;
    start_date: string | null;
    field_name: string | null;
    status: string;
  }[];
  recent_logs_count: number;
  recent_logs_preview: {
    id: number;
    operation_type: string;
    operation_date: string | null;
    note?: string | null;
  }[];
  weather_today: {
    date: string;
    max_c: number;
    min_c: number;
    precip_mm: number;
    wind_mps: number;
    code: string | null;
    desc: string;
  } | null;
  workers_summary: {
    total: number;
    active: number;
    unsettled_wages: number;
  };
  cost_summary: {
    month_income: number;
    month_cost: number;
    year_profit: number;
  };
}

export async function getSummary(): Promise<DashboardSummary> {
  const res = await apiClient.get<DashboardSummary>('/dashboard');
  return res.data;
}
