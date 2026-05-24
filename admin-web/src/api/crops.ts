import apiClient from './client';

export interface GrowthStage {
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string;
}

export interface CropTemplate {
  id: number;
  name: string;
  variety?: string;
  stages: GrowthStage[];
}

export const listTemplates = () => apiClient.get<CropTemplate[]>('/crops/templates');
export const getTemplate = (id: number) => apiClient.get<CropTemplate>(`/crops/templates/${id}`);
export const createTemplate = (data: { name: string; variety?: string; stages: GrowthStage[] }) =>
  apiClient.post<CropTemplate>('/crops/templates', data);
