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

export const listCycles = () => apiClient.get<CropCycleListItem[]>('/cycles');
export const getCycle = (id: number) => apiClient.get<CropCycle>(`/cycles/${id}`);
export const createCycle = (data: { name: string; crop_template_id: number; start_date: string; field_name?: string }) =>
  apiClient.post<CropCycle>('/cycles', data);
