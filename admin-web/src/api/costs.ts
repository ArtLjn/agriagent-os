import apiClient from './client';

export interface CostRecord {
  id: number; cycle_id?: number; record_type: string;
  category: string; amount: string; record_date: string; note?: string;
  record_subtype?: string | null; counterparty?: string | null; due_date?: string | null;
  recorded_at?: string | null; created_at?: string | null;
}

export interface CycleProfit {
  cycle_id: number; total_cost: string; total_income: string; net_profit: string;
}

export interface YearlySummary {
  year: number; total_cost: string; total_income: string;
  net_profit: string; by_category: Record<string, string>;
}

export interface CostParseResponse {
  record_type: string;
  category: string;
  amount: string;
  record_date: string;
  note?: string | null;
  record_subtype?: string | null;
  counterparty?: string | null;
  due_date?: string | null;
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export async function listRecords(params?: { cycle_id?: number; category?: string; page?: number; size?: number }): Promise<PaginatedList<CostRecord>> {
  const res = await apiClient.get<PaginatedList<CostRecord>>('/costs', { params });
  return res.data;
}

export async function createRecord(data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; recorded_at?: string; note?: string; record_subtype?: string; counterparty?: string; due_date?: string }): Promise<CostRecord> {
  const res = await apiClient.post<CostRecord>('/costs', data);
  return res.data;
}

export async function parseCostRecord(description: string): Promise<CostParseResponse> {
  const res = await apiClient.post<CostParseResponse>('/costs/parse', { description });
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
