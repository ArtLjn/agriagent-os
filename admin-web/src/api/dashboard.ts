import apiClient from './client';

export interface DashboardSummary {
  farm_id: number;
  name: string;
  location: string | null;
  today: string;
  active_cycles: unknown[];
  recent_logs_count: number;
  recent_logs_preview: unknown[];
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
