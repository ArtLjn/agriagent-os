import apiClient from './client';

export interface FarmLog {
  id: number; cycle_id: number; operation_type: string;
  operation_date: string; operation_time?: string;
  note?: string; photo_urls?: string; created_at: string;
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export async function listLogs(params?: { cycle_id?: number; operation_type?: string; page?: number; size?: number }): Promise<PaginatedList<FarmLog>> {
  const res = await apiClient.get<PaginatedList<FarmLog>>('/logs', { params });
  return res.data;
}

export async function createLog(data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }): Promise<FarmLog> {
  const res = await apiClient.post<FarmLog>('/logs', data);
  return res.data;
}

export async function updateLog(id: number, data: Omit<FarmLog, "id" | "created_at">): Promise<FarmLog> {
  const res = await apiClient.put<FarmLog>(`/logs/${id}`, data);
  return res.data;
}

export async function deleteLog(id: number): Promise<void> {
  await apiClient.delete(`/logs/${id}`);
}
