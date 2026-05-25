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

export async function listRecords(params?: { cycle_id?: number; category?: string }): Promise<CostRecord[]> {
  const res = await apiClient.get<CostRecord[]>('/costs', { params });
  return res.data;
}

export async function createRecord(data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }): Promise<CostRecord> {
  const res = await apiClient.post<CostRecord>('/costs', data);
  return res.data;
}

export async function updateRecord(id: number, data: Partial<Omit<CostRecord, "id" | "created_at">>): Promise<CostRecord> {
  const res = await apiClient.put<CostRecord>(`/costs/${id}`, data);
  return res.data;
}

export async function deleteRecord(id: number): Promise<void> {
  await apiClient.delete(`/costs/${id}`);
}

export async function getCycleProfit(cycleId: number): Promise<CycleProfit> {
  const res = await apiClient.get<CycleProfit>(`/costs/cycles/${cycleId}/profit`);
  return res.data;
}

export async function getYearlySummary(year: number): Promise<YearlySummary> {
  const res = await apiClient.get<YearlySummary>(`/costs/summary/${year}`);
  return res.data;
}
