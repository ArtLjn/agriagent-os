import apiClient from './client';

export interface GrowthStage {
  id?: number;
  crop_template_id?: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string;
}

export interface CropTemplate {
  id: number;
  name: string;
  variety?: string;
  category?: string | null;
  already_exists?: boolean;
  stages: GrowthStage[];
}

export interface CropTemplateImportResponse {
  id: number;
  already_exists: boolean;
}

export interface CropTemplateParseResponse {
  name: string;
  variety?: string | null;
  stages: GrowthStage[];
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export async function listTemplates(params?: { page?: number; size?: number }): Promise<PaginatedList<CropTemplate>> {
  const res = await apiClient.get<PaginatedList<CropTemplate>>('/crops/templates', { params });
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

export async function listSystemCropTemplates(category?: string): Promise<CropTemplate[]> {
  const res = await apiClient.get<CropTemplate[]>('/crops/templates/system', {
    params: category ? { category } : undefined,
  });
  return res.data;
}

export async function importSystemCropTemplate(id: number): Promise<CropTemplateImportResponse> {
  const res = await apiClient.post<CropTemplateImportResponse>(`/crops/templates/system/${id}/import`);
  return res.data;
}

export async function createSystemTemplate(
  data: { name: string; variety?: string | null; category?: string | null; stages: GrowthStage[] },
): Promise<CropTemplate> {
  const res = await apiClient.post<CropTemplate>('/crops/templates/system', data);
  return res.data;
}

export async function updateSystemTemplate(
  id: number,
  data: { name: string; variety?: string | null; category?: string | null; stages: GrowthStage[] },
): Promise<CropTemplate> {
  const res = await apiClient.put<CropTemplate>(`/crops/templates/system/${id}`, data);
  return res.data;
}

export async function deleteSystemTemplate(id: number): Promise<void> {
  await apiClient.delete(`/crops/templates/system/${id}`);
}

export async function parseTemplate(description: string): Promise<CropTemplateParseResponse> {
  const res = await apiClient.post<CropTemplateParseResponse>('/crops/templates/parse', { description });
  return res.data;
}

export async function updateTemplate(id: number, data: Omit<CropTemplate, "id">): Promise<CropTemplate> {
  const res = await apiClient.put<CropTemplate>(`/crops/templates/${id}`, data);
  return res.data;
}

export async function deleteTemplate(id: number): Promise<void> {
  await apiClient.delete(`/crops/templates/${id}`);
}
