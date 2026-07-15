import apiClient from './client';

export interface DashboardSummary {
  farm_count: number;
  user_count: number;
  dau_today: number;
  records_today: number;
}

export interface DashboardTrendItem {
  date: string;
  count: number;
}

export interface DashboardTrend {
  days: DashboardTrendItem[];
}

export interface DashboardActiveUser {
  user_id: string;
  nickname: string;
  phone_masked: string;
  last_active_at: string | null;
  farm_name: string | null;
}

export interface DashboardActiveUsers {
  items: DashboardActiveUser[];
}

export async function getSummary(): Promise<DashboardSummary> {
  const res = await apiClient.get<DashboardSummary>('/admin/dashboard/summary');
  return res.data;
}

export async function getTrend(days = 7): Promise<DashboardTrend> {
  const res = await apiClient.get<DashboardTrend>('/admin/dashboard/trend', {
    params: { days },
  });
  return res.data;
}

export async function getActiveUsers(): Promise<DashboardActiveUsers> {
  const res = await apiClient.get<DashboardActiveUsers>('/admin/dashboard/active-users');
  return res.data;
}
