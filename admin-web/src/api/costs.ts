import apiClient from './client';

export interface CostRecord {
  id: number; cycle_id?: number; record_type: string;
  category: string; amount: string; record_date: string; note?: string;
}

export interface CycleProfit {
  cycle_id: number; total_cost: string; total_income: string; net_profit: string;
}

export interface YearlySummary {
  year: number; total_cost: string; total_income: string;
  net_profit: string; by_category: Record<string, string>;
}

export const listRecords = (params?: { cycle_id?: number; category?: string }) =>
  apiClient.get<CostRecord[]>('/costs', { params });
export const createRecord = (data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }) =>
  apiClient.post<CostRecord>('/costs', data);
export const getCycleProfit = (cycleId: number) =>
  apiClient.get<CycleProfit>(`/costs/cycles/${cycleId}/profit`);
export const getYearlySummary = (year: number) =>
  apiClient.get<YearlySummary>(`/costs/summary/${year}`);
