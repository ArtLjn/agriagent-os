import apiClient from './client';

export interface FarmLog {
  id: number; cycle_id: number; operation_type: string;
  operation_date: string; operation_time?: string;
  note?: string; photo_urls?: string; created_at: string;
}

export const listLogs = (params?: { cycle_id?: number; operation_type?: string }) =>
  apiClient.get<FarmLog[]>('/logs', { params });
export const createLog = (data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }) =>
  apiClient.post<FarmLog>('/logs', data);
