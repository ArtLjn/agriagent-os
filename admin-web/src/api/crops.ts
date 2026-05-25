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

export async function listTemplates(): Promise<CropTemplate[]> {
  const res = await apiClient.get<CropTemplate[]>('/crops/templates');
  return res.data;
}

export async function getTemplate(id: number): Promise<CropTemplate> {
  const res = await apiClient.get<CropTemplate>(`/crops/templates/${id}`);
  return res.data;
}

export async function createTemplate(data: { name: string; variety?: string; stages: GrowthStage[] }): Promise<CropTemplate> {
  const res = await apiClient.post<CropTemplate>('/crops/templates', data);
  return res.data;
}

export async function updateTemplate(id: number, data: Omit<CropTemplate, "id">): Promise<CropTemplate> {
  const res = await apiClient.put<CropTemplate>(`/crops/templates/${id}`, data);
  return res.data;
}

export async function deleteTemplate(id: number): Promise<void> {
  await apiClient.delete(`/crops/templates/${id}`);
}
