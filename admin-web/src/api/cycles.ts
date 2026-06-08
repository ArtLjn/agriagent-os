import apiClient from './client';

export interface CropCycle {
  id: number;
  name: string;
  crop_template_id: number;
  start_date: string;
  field_name?: string;
  status: string;
  stages: Array<{
    id: number; name: string; start_date: string; end_date: string;
    order_index: number; key_tasks?: string; is_current: boolean;
  }>;
}

export interface CropCycleListItem {
  id: number;
  name: string;
  crop_template_name: string;
  start_date: string;
  status: string;
  current_stage_name?: string;
}

export interface CycleParseResponse {
  name: string;
  crop_template_id?: number | null;
  start_date: string;
  field_name?: string | null;
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export async function listCycles(params?: { page?: number; size?: number }): Promise<PaginatedList<CropCycleListItem>> {
  const res = await apiClient.get<PaginatedList<CropCycleListItem>>('/cycles', { params });
  return res.data;
}

export async function getCycle(id: number): Promise<CropCycle> {
  const res = await apiClient.get<CropCycle>(`/cycles/${id}`);
  return res.data;
}

export async function createCycle(data: { name: string; crop_template_id: number; start_date: string; field_name?: string }): Promise<CropCycle> {
  const res = await apiClient.post<CropCycle>('/cycles', data);
  return res.data;
}

export async function parseCycle(description: string): Promise<CycleParseResponse> {
  const res = await apiClient.post<CycleParseResponse>('/cycles/parse', { description });
  return res.data;
}

export async function updateCycle(id: number, data: Omit<CropCycle, "id" | "stages">): Promise<CropCycle> {
  const res = await apiClient.put<CropCycle>(`/cycles/${id}`, data);
  return res.data;
}

export async function deleteCycle(id: number): Promise<void> {
  await apiClient.delete(`/cycles/${id}`);
}

export async function advanceStage(id: number): Promise<CropCycle> {
  const res = await apiClient.post<CropCycle>(`/cycles/${id}/advance-stage`);
  return res.data;
}
