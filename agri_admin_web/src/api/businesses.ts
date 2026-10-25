import type { AxiosRequestConfig } from 'axios';
import apiClient from './client';

export interface BusinessRuntimeItem {
  name: string;
  display_name: string | null;
  description: string | null;
  skill_count: number;
  error_code: string | null;
}

export interface BusinessListResponse {
  items: BusinessRuntimeItem[];
  total: number;
  active: string | null;
}

export interface SwitchBusinessResponse {
  active: string;
  display_name: string;
  skill_count: number;
}

export async function listBusinesses(signal?: AbortSignal): Promise<BusinessListResponse> {
  const config = {
    silent: true,
    ...(signal ? { signal } : {}),
  } as AxiosRequestConfig;
  const response = await apiClient.get<BusinessListResponse>(
    '/agent/admin/businesses',
    config,
  );
  return response.data;
}

export async function switchBusiness(name: string): Promise<SwitchBusinessResponse> {
  const response = await apiClient.put<SwitchBusinessResponse>(
    '/agent/admin/businesses/active',
    { name },
    { silent: true } as AxiosRequestConfig,
  );
  return response.data;
}
